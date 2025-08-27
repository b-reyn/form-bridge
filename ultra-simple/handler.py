"""
Ultra-Simple Form Bridge Handler
Single Lambda function handling all form submissions via Function URL

Optimized for minimal cost:
- 128MB memory (lowest cost tier)
- Fast execution (<100ms typical)
- Minimal dependencies (boto3 only)
- WordPress plugin compatible HMAC auth
"""

import json
import boto3
import hmac
import hashlib
import os
from datetime import datetime, timezone
from typing import Dict, Any

# Initialize AWS clients (lazy loading for cost optimization)
dynamodb = None
table = None

def get_table():
    """Lazy load DynamoDB table to optimize cold starts"""
    global dynamodb, table
    if not table:
        dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('TABLE_NAME', 'form-bridge-data')
        table = dynamodb.Table(table_name)
    return table

# Configuration
HMAC_SECRET = os.environ.get('HMAC_SECRET', 'development-secret-change-in-production')
MAX_PAYLOAD_SIZE = 256 * 1024  # 256KB limit (DynamoDB item size limit is 400KB)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for form submissions via Lambda Function URL
    
    Optimized for minimal execution time and cost:
    - CORS preflight requests
    - HMAC authentication (WordPress plugin compatible)
    - Form data storage with TTL
    - Comprehensive error handling
    """
    
    # Handle CORS preflight (fast path)
    method = event.get('requestContext', {}).get('http', {}).get('method')
    if method == 'OPTIONS':
        return create_cors_response()
    
    # Only accept POST requests
    if method != 'POST':
        return create_response(405, {'error': 'Method not allowed'})
    
    try:
        # Fast validation - check size before parsing JSON
        body_str = event.get('body', '')
        if len(body_str) > MAX_PAYLOAD_SIZE:
            return create_response(413, {'error': 'Payload too large'})
        
        if not body_str.strip():
            return create_response(400, {'error': 'Empty request body'})
        
        # Parse JSON
        try:
            body = json.loads(body_str)
        except json.JSONDecodeError as e:
            return create_response(400, {'error': 'Invalid JSON format'})
        
        # Extract headers (case-insensitive)
        headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
        
        # Validate HMAC signature (WordPress plugin compatible)
        if not validate_hmac(headers, body, body_str):
            print(f"HMAC validation failed for timestamp: {headers.get('x-timestamp')}")
            return create_response(401, {'error': 'Authentication failed'})
        
        # Process and store submission
        result = process_submission(body, headers)
        return create_response(200, result)
        
    except Exception as e:
        # Log error but don't expose internal details
        print(f"Handler error: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def validate_hmac(headers: Dict, body: Dict, body_str: str) -> bool:
    """
    Validate HMAC signature for request authentication (WordPress plugin compatible)
    
    Expected headers:
    - x-signature: HMAC-SHA256 hash
    - x-timestamp: Unix timestamp
    
    WordPress plugin sends: HMAC-SHA256(timestamp + ':' + json_body, secret)
    """
    signature = headers.get('x-signature', '').lower()
    timestamp = headers.get('x-timestamp', '')
    
    if not signature or not timestamp:
        print("Missing signature or timestamp")
        return False
    
    # Validate timestamp format and age (prevent replay attacks)
    try:
        request_time = float(timestamp)
        current_time = datetime.now(timezone.utc).timestamp()
        age_seconds = abs(current_time - request_time)
        
        if age_seconds > 300:  # 5 minute window
            print(f"Timestamp too old: {age_seconds:.1f} seconds")
            return False
            
    except (ValueError, TypeError):
        print(f"Invalid timestamp format: {timestamp}")
        return False
    
    # Calculate expected signature using raw JSON body (WordPress compatible)
    message = f"{timestamp}:{body_str}"
    expected = hmac.new(
        HMAC_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().lower()
    
    # Constant-time comparison
    is_valid = hmac.compare_digest(signature, expected)
    if not is_valid:
        print(f"HMAC mismatch. Expected: {expected[:8]}..., Got: {signature[:8]}...")
    
    return is_valid


def process_submission(body: Dict, headers: Dict) -> Dict[str, Any]:
    """
    Process and store form submission in DynamoDB with TTL
    """
    # Generate unique submission ID (time-based for sorting)
    timestamp = datetime.now(timezone.utc)
    submission_id = f"sub_{int(timestamp.timestamp() * 1000)}"  # Millisecond precision
    
    # Extract and validate form data
    form_data = body.get('form_data', {})
    metadata = body.get('metadata', {})
    
    if not form_data and not metadata:
        raise ValueError("No form data or metadata provided")
    
    # Prepare DynamoDB item (optimized for single-table design)
    item = {
        'PK': 'SUBMISSION',
        'SK': submission_id,
        'timestamp': timestamp.isoformat(),
        'submission_id': submission_id,
        'form_data': form_data,
        'metadata': {
            'source': metadata.get('source', 'wordpress'),
            'form_id': metadata.get('form_id', 'unknown'),
            'site_url': metadata.get('site_url', ''),
            'ip_address': headers.get('x-forwarded-for', 'unknown'),
            'user_agent': headers.get('user-agent', 'unknown'),
            **{k: v for k, v in metadata.items() if k not in ['source', 'form_id', 'site_url']}
        },
        'status': 'received',
        'ttl': int(timestamp.timestamp() + (30 * 24 * 3600))  # 30 days TTL
    }
    
    # Store in DynamoDB (use lazy-loaded table)
    try:
        table = get_table()
        table.put_item(Item=item)
        print(f"Stored submission: {submission_id} from {metadata.get('source', 'unknown')}")
        
    except Exception as e:
        print(f"DynamoDB error: {str(e)}")
        raise
    
    # Return success response (WordPress plugin compatible)
    return {
        'success': True,
        'submission_id': submission_id,
        'timestamp': timestamp.isoformat(),
        'message': 'Form submission received successfully'
    }


def create_response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Create HTTP response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Signature, X-Timestamp',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        },
        'body': json.dumps(body, separators=(',', ':'))  # Compact JSON
    }


def create_cors_response() -> Dict[str, Any]:
    """Create CORS preflight response (optimized for speed)"""
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Signature, X-Timestamp',
            'Access-Control-Max-Age': '86400',  # Cache preflight for 24 hours
            'Cache-Control': 'public, max-age=86400'
        },
        'body': ''
    }


# Local testing helper (removed in production deployment)
def create_test_event(form_data: Dict = None) -> Dict[str, Any]:
    """Create a test event for local development"""
    if not form_data:
        form_data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'message': 'Ultra-simple test submission'
        }
    
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    body_data = {
        'form_data': form_data,
        'metadata': {
            'source': 'wordpress',
            'form_id': 'contact-form-1',
            'site_url': 'https://example.com'
        }
    }
    
    body_str = json.dumps(body_data, separators=(',', ':'))
    
    # Generate HMAC signature for testing
    message = f"{timestamp}:{body_str}"
    signature = hmac.new(
        'development-secret-change-in-production'.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return {
        'requestContext': {
            'http': {'method': 'POST'}
        },
        'headers': {
            'content-type': 'application/json',
            'x-signature': signature,
            'x-timestamp': timestamp,
            'user-agent': 'WordPress/6.0 FormBridge/1.0'
        },
        'body': body_str
    }


if __name__ == '__main__':
    # Local testing with proper HMAC signature
    print("Creating test event...")
    test_event = create_test_event()
    
    print("Testing CORS preflight...")
    cors_event = {'requestContext': {'http': {'method': 'OPTIONS'}}}
    cors_result = lambda_handler(cors_event, None)
    print(f"CORS Status: {cors_result['statusCode']}")
    
    print("\nTesting form submission...")
    os.environ['TABLE_NAME'] = 'form-bridge-test'  # Mock for local testing
    
    try:
        result = lambda_handler(test_event, None)
        print(f"Status: {result['statusCode']}")
        print(f"Response: {result['body']}")
    except Exception as e:
        print(f"Error (expected without DynamoDB): {str(e)}")
        print("This is normal when running locally without AWS credentials")
    
    print("\nHandler optimization complete!")
    print("- 128MB memory compatible")
    print("- WordPress plugin HMAC authentication")
    print("- Fast execution path")
    print("- DynamoDB with TTL")
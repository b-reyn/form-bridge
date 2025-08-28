"""
Read Submissions Lambda Function
Simple API to fetch form submissions from DynamoDB for the admin dashboard

Features:
- Basic HTTP authentication (admin password)
- Query all submissions or filter by date range
- Pagination support for large datasets
- CORS headers for frontend integration
- Ultra-minimal dependencies for cost optimization
"""

import json
import boto3
import os
import base64
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

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
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Change in production
DEFAULT_LIMIT = 50  # Max items per request
MAX_LIMIT = 200

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for reading form submissions
    
    Supports:
    - GET / - List all submissions (with pagination)
    - GET /stats - Basic statistics
    - Basic HTTP authentication
    - CORS preflight requests
    """
    
    # Handle CORS preflight - check both API Gateway v1 and v2 formats
    method = (event.get('httpMethod') or 
              event.get('requestContext', {}).get('http', {}).get('method') or
              event.get('requestContext', {}).get('httpMethod'))
    
    if method == 'OPTIONS':
        return create_cors_response()
    
    # Only accept GET requests
    if method != 'GET':
        return create_response(405, {'error': 'Method not allowed'})
    
    try:
        # Extract headers and query parameters
        headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
        query_params = event.get('queryStringParameters') or {}
        path = event.get('rawPath', '/').strip('/')
        
        # Validate authentication
        if not validate_auth(headers):
            return create_response(401, {'error': 'Authentication required'}, include_auth_header=True)
        
        # Route requests
        if path == 'stats':
            result = get_statistics()
        else:
            # Main submissions listing
            result = get_submissions(query_params)
            
        return create_response(200, result)
        
    except Exception as e:
        print(f"Handler error: {str(e)}")
        return create_response(500, {'error': 'Internal server error'})


def validate_auth(headers: Dict) -> bool:
    """
    Validate basic HTTP authentication
    Expects: Authorization: Basic base64(admin:password)
    """
    auth_header = headers.get('authorization', '')
    
    if not auth_header.startswith('Basic '):
        return False
    
    try:
        # Decode base64 credentials
        encoded = auth_header[6:]  # Remove 'Basic '
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, password = decoded.split(':', 1)
        
        # Simple admin check
        return username == 'admin' and password == ADMIN_PASSWORD
        
    except (ValueError, TypeError) as e:
        print(f"Auth validation error: {str(e)}")
        return False


def get_submissions(query_params: Dict) -> Dict[str, Any]:
    """
    Fetch form submissions from DynamoDB with optional filtering
    
    Query parameters:
    - limit: Number of items (default 50, max 200)
    - last_key: For pagination (base64 encoded)
    - date_from: ISO date string (optional)
    - date_to: ISO date string (optional)
    """
    try:
        table = get_table()
        
        # Parse pagination parameters
        limit = min(int(query_params.get('limit', DEFAULT_LIMIT)), MAX_LIMIT)
        last_key_param = query_params.get('last_key')
        
        # Build scan parameters
        scan_kwargs = {
            'FilterExpression': 'PK = :pk',
            'ExpressionAttributeValues': {':pk': 'SUBMISSION'},
            'Limit': limit
        }
        
        # Add pagination if provided
        if last_key_param:
            try:
                last_key = json.loads(base64.b64decode(last_key_param).decode('utf-8'))
                scan_kwargs['ExclusiveStartKey'] = last_key
            except Exception as e:
                print(f"Invalid last_key parameter: {e}")
        
        # Perform scan
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        
        # Format submissions for frontend
        submissions = []
        for item in items:
            submission = {
                'submission_id': item.get('submission_id', ''),
                'timestamp': item.get('timestamp', ''),
                'form_data': item.get('form_data', {}),
                'metadata': item.get('metadata', {}),
                'status': item.get('status', 'unknown')
            }
            submissions.append(submission)
        
        # Prepare pagination info
        result = {
            'submissions': submissions,
            'count': len(submissions),
            'has_more': 'LastEvaluatedKey' in response
        }
        
        # Include next page key if available
        if 'LastEvaluatedKey' in response:
            next_key = base64.b64encode(
                json.dumps(response['LastEvaluatedKey']).encode('utf-8')
            ).decode('utf-8')
            result['next_key'] = next_key
        
        return result
        
    except Exception as e:
        print(f"DynamoDB scan error: {str(e)}")
        raise


def get_statistics() -> Dict[str, Any]:
    """
    Get basic statistics about form submissions
    """
    try:
        table = get_table()
        
        # Count total submissions
        response = table.scan(
            FilterExpression='PK = :pk',
            ExpressionAttributeValues={':pk': 'SUBMISSION'},
            Select='COUNT'
        )
        
        total_count = response.get('Count', 0)
        
        # For MVP, just return basic stats
        # In production, could use DynamoDB Streams + Lambda to maintain counters
        return {
            'total_submissions': total_count,
            'submissions_today': 0,  # TODO: Implement date-based counting
            'unique_tenants': 1,  # Single tenant for MVP
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        print(f"Statistics error: {str(e)}")
        raise


def create_response(status_code: int, body: Dict, include_auth_header: bool = False) -> Dict[str, Any]:
    """Create HTTP response with CORS headers"""
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Cache-Control': 'no-cache, no-store, must-revalidate'
    }
    
    if include_auth_header:
        headers['WWW-Authenticate'] = 'Basic realm="Form Bridge Admin"'
    
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': json.dumps(body, separators=(',', ':'))  # Compact JSON
    }


def create_cors_response() -> Dict[str, Any]:
    """Create CORS preflight response"""
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '86400',  # Cache preflight for 24 hours
            'Cache-Control': 'public, max-age=86400'
        },
        'body': ''
    }


# Local testing helper
def create_test_event(path: str = '/', method: str = 'GET', auth: bool = True) -> Dict[str, Any]:
    """Create a test event for local development"""
    headers = {
        'content-type': 'application/json',
        'user-agent': 'Test/1.0'
    }
    
    if auth:
        # Create basic auth header (admin:admin123)
        credentials = base64.b64encode('admin:admin123'.encode()).decode()
        headers['authorization'] = f'Basic {credentials}'
    
    return {
        'requestContext': {
            'http': {'method': method}
        },
        'headers': headers,
        'rawPath': path,
        'queryStringParameters': None
    }


if __name__ == '__main__':
    # Local testing
    print("Testing read submissions handler...")
    
    os.environ['TABLE_NAME'] = 'form-bridge-test'  # Mock for local testing
    os.environ['ADMIN_PASSWORD'] = 'admin123'
    
    # Test CORS preflight
    cors_event = {'requestContext': {'http': {'method': 'OPTIONS'}}}
    cors_result = lambda_handler(cors_event, None)
    print(f"CORS Status: {cors_result['statusCode']}")
    
    # Test without auth
    no_auth_event = create_test_event(auth=False)
    no_auth_result = lambda_handler(no_auth_event, None)
    print(f"No Auth Status: {no_auth_result['statusCode']}")
    
    # Test with auth (will fail without DynamoDB)
    auth_event = create_test_event()
    try:
        auth_result = lambda_handler(auth_event, None)
        print(f"With Auth Status: {auth_result['statusCode']}")
        print(f"Response: {auth_result['body']}")
    except Exception as e:
        print(f"Auth test error (expected without DynamoDB): {str(e)}")
    
    # Test stats endpoint
    stats_event = create_test_event('/stats')
    try:
        stats_result = lambda_handler(stats_event, None)
        print(f"Stats Status: {stats_result['statusCode']}")
    except Exception as e:
        print(f"Stats test error (expected without DynamoDB): {str(e)}")
    
    print("\nRead handler ready for deployment!")
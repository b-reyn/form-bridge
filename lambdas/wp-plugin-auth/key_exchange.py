"""
Key Exchange Lambda for Form-Bridge WordPress Plugin
Swaps temporary key for permanent site credentials with site ownership validation.
"""

import json
import os
import uuid
import hashlib
import hmac
import secrets
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
import requests
from urllib.parse import urljoin, urlparse

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# AWS clients
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Configuration
VERIFICATION_TIMEOUT = 10  # seconds
API_KEY_LENGTH = 64
SECRET_LENGTH = 32
CHALLENGE_LENGTH = 16

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Exchange temporary key for permanent site credentials
    
    Expected input:
    {
        "temp_key": "temp_abc123...",
        "verification_method": "file|meta", 
        "challenge_response": "challenge_value_from_site"
    }
    """
    try:
        # Parse request body
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            return _error_response(400, "INVALID_JSON", "Invalid JSON in request body")
        
        # Validate required fields
        temp_key = body.get('temp_key', '').strip()
        verification_method = body.get('verification_method', 'file')
        challenge_response = body.get('challenge_response', '').strip()
        
        if not temp_key:
            return _error_response(400, "MISSING_TEMP_KEY", "Temporary key is required")
        
        # Look up registration by temp key
        registration = _get_registration_by_temp_key(temp_key)
        if not registration:
            return _error_response(404, "INVALID_TEMP_KEY", "Temporary key not found or expired")
        
        # Check if already activated
        if registration['status'] == 'active':
            return _error_response(409, "ALREADY_ACTIVE", "Site already activated")
        
        # Verify site ownership
        verification_result = _verify_site_ownership(
            registration['domain'], 
            temp_key,
            verification_method,
            challenge_response
        )
        
        if not verification_result['verified']:
            return _error_response(403, "VERIFICATION_FAILED", verification_result['error'])
        
        # Generate permanent credentials
        credentials = _generate_site_credentials(registration)
        
        # Update registration status to active
        _activate_registration(registration, credentials)
        
        # Store credentials securely
        _store_site_credentials(registration['domain'], credentials)
        
        # Log successful activation
        logger.info("Site activated successfully", extra={
            'registration_id': registration['registration_id'],
            'domain': registration['domain'],
            'verification_method': verification_method
        })
        
        metrics.add_metric(name="SiteActivations", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="domain", value=registration['domain'])
        metrics.add_metadata(key="verification_method", value=verification_method)
        
        return _success_response({
            'site_id': credentials['site_id'],
            'api_key': credentials['api_key'],
            'webhook_secret': credentials['webhook_secret'],
            'endpoints': {
                'webhook': f"https://{os.environ.get('API_DOMAIN', 'api.form-bridge.com')}/v1/webhook/{credentials['site_id']}",
                'status': f"https://{os.environ.get('API_DOMAIN', 'api.form-bridge.com')}/v1/sites/{credentials['site_id']}/status"
            },
            'next_steps': [
                'Store API key and webhook secret securely',
                'Configure webhook endpoint in your forms',
                'Test connection using status endpoint'
            ]
        })
        
    except Exception as e:
        logger.exception("Key exchange error")
        metrics.add_metric(name="KeyExchangeErrors", unit=MetricUnit.Count, value=1)
        return _error_response(500, "INTERNAL_ERROR", "Key exchange temporarily unavailable")

def _get_registration_by_temp_key(temp_key: str) -> Optional[Dict[str, Any]]:
    """Look up registration by temporary key"""
    try:
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression='GSI1PK = :pk',
            ExpressionAttributeValues={':pk': f'TEMP#{temp_key}'},
            Limit=1
        )
        
        items = response.get('Items', [])
        if not items:
            return None
        
        registration = items[0]
        
        # Check if expired
        if _is_expired(registration.get('expires_at')):
            return None
            
        return registration
        
    except Exception as e:
        logger.warning("Failed to lookup temp key", extra={'error': str(e)})
        return None

def _verify_site_ownership(domain: str, temp_key: str, method: str, challenge_response: str) -> Dict[str, Any]:
    """Verify site ownership using specified method"""
    try:
        # Generate unique challenge for this verification attempt
        challenge = _generate_challenge()
        
        if method == 'file':
            return _verify_file_method(domain, temp_key, challenge, challenge_response)
        elif method == 'meta':
            return _verify_meta_method(domain, temp_key, challenge)
        else:
            return {'verified': False, 'error': 'Invalid verification method'}
            
    except Exception as e:
        logger.warning("Site verification failed", extra={
            'domain': domain,
            'method': method,
            'error': str(e)
        })
        return {'verified': False, 'error': 'Verification request failed'}

def _verify_file_method(domain: str, temp_key: str, challenge: str, challenge_response: str) -> Dict[str, Any]:
    """Verify ownership via file upload method"""
    try:
        # Expected file path: /.well-known/form-bridge-verification.txt
        verification_url = f"https://{domain}/.well-known/form-bridge-verification.txt"
        
        # Make HTTP request to verification file
        response = requests.get(
            verification_url,
            timeout=VERIFICATION_TIMEOUT,
            headers={'User-Agent': 'Form-Bridge-Verification/1.0'}
        )
        
        if response.status_code != 200:
            return {'verified': False, 'error': f'Verification file not found (HTTP {response.status_code})'}
        
        # Parse verification file content
        content = response.text.strip()
        lines = content.split('\n')
        
        verification_data = {}
        for line in lines:
            if '=' in line:
                key, value = line.split('=', 1)
                verification_data[key.strip()] = value.strip()
        
        # Validate required fields
        if verification_data.get('temp_key') != temp_key:
            return {'verified': False, 'error': 'Temporary key mismatch in verification file'}
        
        if verification_data.get('domain') != domain:
            return {'verified': False, 'error': 'Domain mismatch in verification file'}
        
        # Check timestamp (must be within last hour)
        try:
            timestamp = int(verification_data.get('timestamp', 0))
            if abs(int(datetime.utcnow().timestamp()) - timestamp) > 3600:
                return {'verified': False, 'error': 'Verification file timestamp too old'}
        except (ValueError, TypeError):
            return {'verified': False, 'error': 'Invalid timestamp in verification file'}
        
        return {'verified': True, 'method': 'file'}
        
    except requests.exceptions.Timeout:
        return {'verified': False, 'error': 'Verification request timed out'}
    except requests.exceptions.RequestException as e:
        return {'verified': False, 'error': f'Failed to fetch verification file: {str(e)}'}

def _verify_meta_method(domain: str, temp_key: str, challenge: str) -> Dict[str, Any]:
    """Verify ownership via meta tag method"""
    try:
        # Check both HTTP and HTTPS
        for protocol in ['https', 'http']:
            verification_url = f"{protocol}://{domain}/"
            
            try:
                response = requests.get(
                    verification_url,
                    timeout=VERIFICATION_TIMEOUT,
                    headers={'User-Agent': 'Form-Bridge-Verification/1.0'}
                )
                
                if response.status_code == 200:
                    # Look for verification meta tag
                    content = response.text.lower()
                    expected_meta = f'<meta name="form-bridge-verification" content="{temp_key}"'
                    
                    if expected_meta.lower() in content:
                        return {'verified': True, 'method': 'meta'}
                        
            except requests.exceptions.RequestException:
                continue  # Try next protocol
        
        return {'verified': False, 'error': 'Verification meta tag not found'}
        
    except Exception as e:
        return {'verified': False, 'error': f'Meta verification failed: {str(e)}'}

def _generate_challenge() -> str:
    """Generate random challenge string"""
    return secrets.token_hex(CHALLENGE_LENGTH)

def _generate_site_credentials(registration: Dict[str, Any]) -> Dict[str, Any]:
    """Generate permanent site credentials"""
    site_id = str(uuid.uuid7())
    api_key = secrets.token_urlsafe(API_KEY_LENGTH)
    webhook_secret = secrets.token_urlsafe(SECRET_LENGTH)
    
    return {
        'site_id': site_id,
        'api_key': api_key,
        'webhook_secret': webhook_secret,
        'domain': registration['domain'],
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }

def _activate_registration(registration: Dict[str, Any], credentials: Dict[str, Any]):
    """Update registration status to active"""
    try:
        table.update_item(
            Key={
                'PK': registration['PK'],
                'SK': registration['SK']
            },
            UpdateExpression='SET #status = :status, site_id = :site_id, activated_at = :activated_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'active',
                ':site_id': credentials['site_id'],
                ':activated_at': datetime.utcnow().isoformat() + 'Z'
            }
        )
    except Exception as e:
        logger.error("Failed to activate registration", extra={'error': str(e)})
        raise

def _store_site_credentials(domain: str, credentials: Dict[str, Any]):
    """Store site credentials in DynamoDB"""
    try:
        # Store main site record
        table.put_item(
            Item={
                'PK': f'SITE#{domain}',
                'SK': f'CREDS#{credentials["site_id"]}',
                'GSI1PK': f'SITE#{credentials["site_id"]}',
                'GSI1SK': 'ACTIVE',
                'site_id': credentials['site_id'],
                'domain': domain,
                'api_key_hash': _hash_api_key(credentials['api_key']),
                'webhook_secret': credentials['webhook_secret'],
                'status': 'active',
                'created_at': credentials['created_at'],
                'last_seen': credentials['created_at'],
                'request_count': 0,
                'rate_limit_remaining': 1000  # Initial rate limit
            }
        )
        
        # Store API key lookup record
        table.put_item(
            Item={
                'PK': f'API#{_hash_api_key(credentials["api_key"])}',
                'SK': 'LOOKUP',
                'site_id': credentials['site_id'],
                'domain': domain,
                'created_at': credentials['created_at']
            }
        )
        
    except Exception as e:
        logger.error("Failed to store credentials", extra={'error': str(e)})
        raise

def _hash_api_key(api_key: str) -> str:
    """Create hash of API key for lookup"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def _is_expired(expires_at: str) -> bool:
    """Check if timestamp is expired"""
    try:
        expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=expires.tzinfo)
        return now > expires
    except Exception:
        return True

def _success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return success response with CORS headers"""
    return {
        'statusCode': 200,
        'headers': _get_cors_headers(),
        'body': json.dumps({
            'success': True,
            'data': data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    }

def _error_response(status_code: int, error_code: str, message: str) -> Dict[str, Any]:
    """Return error response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': _get_cors_headers(),
        'body': json.dumps({
            'success': False,
            'error': {
                'code': error_code,
                'message': message
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    }

def _get_cors_headers() -> Dict[str, str]:
    """Get CORS headers for WordPress plugin requests"""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Cache-Control': 'no-store, no-cache, must-revalidate'
    }
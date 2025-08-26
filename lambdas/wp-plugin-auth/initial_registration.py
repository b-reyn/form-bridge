"""
Initial Registration Lambda for Form-Bridge WordPress Plugin
Handles initial site registration with minimal info collection.
"""

import json
import os
import uuid
import time
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
import validators

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# AWS clients
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Configuration
RATE_LIMIT_WINDOW = 300  # 5 minutes
MAX_REGISTRATIONS_PER_IP = 3
TEMP_KEY_EXPIRY = 3600  # 1 hour
MIN_DOMAIN_LENGTH = 4

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle initial WordPress plugin registration
    
    Expected input:
    {
        "domain": "example.com",
        "wp_version": "6.4.2",
        "plugin_version": "1.0.0",
        "admin_email": "admin@example.com" (optional),
        "agency_id": "agency_123" (optional for bulk registration)
    }
    """
    try:
        # Extract client IP for rate limiting
        client_ip = _get_client_ip(event)
        
        # Parse request body
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            return _error_response(400, "INVALID_JSON", "Invalid JSON in request body")
        
        # Validate required fields
        domain = body.get('domain', '').lower().strip()
        wp_version = body.get('wp_version', '').strip()
        plugin_version = body.get('plugin_version', '').strip()
        
        if not all([domain, wp_version, plugin_version]):
            return _error_response(400, "MISSING_FIELDS", "Required fields: domain, wp_version, plugin_version")
        
        # Validate domain format
        if not _is_valid_domain(domain):
            return _error_response(400, "INVALID_DOMAIN", "Invalid domain format")
        
        # Rate limiting check
        rate_limit_result = _check_rate_limit(client_ip)
        if not rate_limit_result['allowed']:
            return _error_response(429, "RATE_LIMITED", 
                                 f"Too many registration attempts. Try again in {rate_limit_result['retry_after']} seconds")
        
        # Check for existing registration
        existing = _check_existing_registration(domain)
        if existing:
            if existing['status'] == 'active':
                return _error_response(409, "ALREADY_REGISTERED", "Domain already registered and active")
            elif existing['status'] == 'pending' and not _is_expired(existing['created_at'], TEMP_KEY_EXPIRY):
                # Return existing temp key if not expired
                return _success_response({
                    'temp_key': existing['temp_key'],
                    'expires_in': existing['expires_in'],
                    'registration_id': existing['registration_id']
                })
        
        # Generate registration ID and temporary key
        registration_id = str(uuid.uuid7())
        temp_key = _generate_temp_key()
        expires_at = datetime.utcnow() + timedelta(seconds=TEMP_KEY_EXPIRY)
        
        # Prepare registration record
        registration_record = {
            'PK': f'SITE#{domain}',
            'SK': f'REG#{registration_id}',
            'GSI1PK': f'TEMP#{temp_key}',
            'GSI1SK': f'STATUS#pending',
            'registration_id': registration_id,
            'domain': domain,
            'temp_key': temp_key,
            'status': 'pending',
            'wp_version': wp_version,
            'plugin_version': plugin_version,
            'admin_email': body.get('admin_email'),
            'agency_id': body.get('agency_id'),
            'client_ip': client_ip,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'expires_at': expires_at.isoformat() + 'Z',
            'ttl': int(expires_at.timestamp())
        }
        
        # Store registration
        table.put_item(Item=registration_record)
        
        # Update rate limit counter
        _update_rate_limit_counter(client_ip)
        
        # Log metrics
        metrics.add_metric(name="RegistrationAttempts", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="domain", value=domain)
        metrics.add_metadata(key="agency_id", value=body.get('agency_id', 'none'))
        
        logger.info("Registration initiated", extra={
            'registration_id': registration_id,
            'domain': domain,
            'client_ip': client_ip
        })
        
        return _success_response({
            'registration_id': registration_id,
            'temp_key': temp_key,
            'expires_in': TEMP_KEY_EXPIRY,
            'next_step': 'Call key-exchange endpoint with temp_key to complete registration'
        })
        
    except Exception as e:
        logger.exception("Registration error")
        metrics.add_metric(name="RegistrationErrors", unit=MetricUnit.Count, value=1)
        return _error_response(500, "INTERNAL_ERROR", "Registration temporarily unavailable")

def _get_client_ip(event: Dict[str, Any]) -> str:
    """Extract client IP from API Gateway event"""
    # Try various headers in order of preference
    headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
    
    # Check X-Forwarded-For first (most common)
    if 'x-forwarded-for' in headers:
        return headers['x-forwarded-for'].split(',')[0].strip()
    
    # Check other common headers
    for header in ['x-real-ip', 'cf-connecting-ip']:
        if header in headers:
            return headers[header]
    
    # Fall back to source IP
    return event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')

def _is_valid_domain(domain: str) -> bool:
    """Validate domain format and basic checks"""
    if len(domain) < MIN_DOMAIN_LENGTH:
        return False
    
    # Basic domain validation
    if not validators.domain(domain):
        return False
    
    # Block obvious test/local domains
    blocked_domains = ['localhost', 'example.com', 'test.com', '127.0.0.1']
    if domain in blocked_domains or domain.endswith('.local'):
        return False
    
    return True

def _check_rate_limit(client_ip: str) -> Dict[str, Any]:
    """Check if client IP is within rate limits"""
    try:
        current_time = int(time.time())
        window_start = current_time - RATE_LIMIT_WINDOW
        
        # Query rate limit records
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression='GSI1PK = :pk AND GSI1SK BETWEEN :start AND :end',
            ExpressionAttributeValues={
                ':pk': f'RATE#{client_ip}',
                ':start': f'TIME#{window_start}',
                ':end': f'TIME#{current_time}'
            }
        )
        
        count = len(response.get('Items', []))
        
        if count >= MAX_REGISTRATIONS_PER_IP:
            return {
                'allowed': False,
                'retry_after': RATE_LIMIT_WINDOW
            }
        
        return {'allowed': True}
        
    except Exception as e:
        logger.warning("Rate limit check failed", extra={'error': str(e)})
        return {'allowed': True}  # Fail open for availability

def _update_rate_limit_counter(client_ip: str):
    """Update rate limit counter for IP"""
    try:
        current_time = int(time.time())
        
        table.put_item(
            Item={
                'PK': f'RATE#{client_ip}',
                'SK': f'TIME#{current_time}',
                'GSI1PK': f'RATE#{client_ip}',
                'GSI1SK': f'TIME#{current_time}',
                'timestamp': current_time,
                'ttl': current_time + RATE_LIMIT_WINDOW
            }
        )
    except Exception as e:
        logger.warning("Failed to update rate limit", extra={'error': str(e)})

def _check_existing_registration(domain: str) -> Optional[Dict[str, Any]]:
    """Check if domain already has a registration"""
    try:
        response = table.query(
            KeyConditionExpression='PK = :pk',
            ExpressionAttributeValues={':pk': f'SITE#{domain}'},
            ScanIndexForward=False,  # Get latest first
            Limit=1
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
        
    except Exception as e:
        logger.warning("Failed to check existing registration", extra={'error': str(e)})
        return None

def _is_expired(created_at: str, expiry_seconds: int) -> bool:
    """Check if timestamp is expired"""
    try:
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=created.tzinfo)
        return (now - created).total_seconds() > expiry_seconds
    except Exception:
        return True

def _generate_temp_key() -> str:
    """Generate cryptographically secure temporary key"""
    return secrets.token_urlsafe(32)

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
        'Access-Control-Allow-Origin': '*',  # WordPress plugins can call from any domain
        'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Cache-Control': 'no-store, no-cache, must-revalidate'
    }
"""
Authentication Lambda for Form-Bridge WordPress Plugin
API Gateway Custom Authorizer for validating site-specific API keys.
"""

import json
import os
import time
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()
tracer = Tracer()
metrics = Metrics()

# AWS clients
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

# Configuration
RATE_LIMITS = {
    'requests_per_minute': 100,
    'requests_per_hour': 2000,
    'requests_per_day': 10000
}

SUSPICIOUS_PATTERNS = {
    'max_requests_per_second': 20,
    'max_failed_attempts_per_hour': 50
}

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    API Gateway Custom Authorizer for WordPress plugin authentication
    
    Validates API keys and enforces rate limiting per site
    """
    try:
        # Extract authorization details
        auth_header = event.get('authorizationToken', '')
        method_arn = event.get('methodArn', '')
        
        if not auth_header:
            logger.warning("Missing authorization header")
            raise Exception('Unauthorized')  # This will return 401
        
        # Parse API key from Bearer token
        api_key = _extract_api_key(auth_header)
        if not api_key:
            logger.warning("Invalid authorization format")
            raise Exception('Unauthorized')
        
        # Validate API key and get site info
        site_info = _validate_api_key(api_key)
        if not site_info:
            logger.warning("Invalid API key", extra={'api_key_hash': _hash_api_key(api_key)[:16]})
            metrics.add_metric(name="InvalidApiKeyAttempts", unit=MetricUnit.Count, value=1)
            raise Exception('Unauthorized')
        
        # Check rate limits
        rate_limit_result = _check_rate_limits(site_info['site_id'])
        if not rate_limit_result['allowed']:
            logger.warning("Rate limit exceeded", extra={
                'site_id': site_info['site_id'],
                'domain': site_info['domain']
            })
            metrics.add_metric(name="RateLimitExceeded", unit=MetricUnit.Count, value=1)
            raise Exception('Unauthorized')
        
        # Check for suspicious activity
        if _detect_suspicious_activity(site_info['site_id']):
            logger.warning("Suspicious activity detected", extra={
                'site_id': site_info['site_id'],
                'domain': site_info['domain']
            })
            metrics.add_metric(name="SuspiciousActivity", unit=MetricUnit.Count, value=1)
            raise Exception('Unauthorized')
        
        # Update site last seen and request count
        _update_site_activity(site_info)
        
        # Update rate limit counters
        _update_rate_limit_counters(site_info['site_id'])
        
        # Log successful authentication
        logger.info("Authentication successful", extra={
            'site_id': site_info['site_id'],
            'domain': site_info['domain']
        })
        
        metrics.add_metric(name="SuccessfulAuthentications", unit=MetricUnit.Count, value=1)
        
        # Generate allow policy
        policy = _generate_policy('Allow', method_arn, site_info)
        return policy
        
    except Exception as e:
        logger.info("Authentication failed", extra={'error': str(e)})
        metrics.add_metric(name="FailedAuthentications", unit=MetricUnit.Count, value=1)
        
        # Generate deny policy
        policy = _generate_policy('Deny', method_arn)
        return policy

def _extract_api_key(auth_header: str) -> Optional[str]:
    """Extract API key from Authorization header"""
    try:
        # Support both "Bearer" and "ApiKey" prefixes
        if auth_header.startswith('Bearer '):
            return auth_header[7:].strip()
        elif auth_header.startswith('ApiKey '):
            return auth_header[7:].strip()
        elif auth_header.startswith('X-API-Key '):
            return auth_header[10:].strip()
        else:
            # Try to use the header value directly (fallback)
            return auth_header.strip() if len(auth_header) > 16 else None
    except Exception:
        return None

def _validate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Validate API key and return site information"""
    try:
        api_key_hash = _hash_api_key(api_key)
        
        # Look up site by API key hash
        response = table.get_item(
            Key={
                'PK': f'API#{api_key_hash}',
                'SK': 'LOOKUP'
            }
        )
        
        item = response.get('Item')
        if not item:
            return None
        
        site_id = item['site_id']
        domain = item['domain']
        
        # Get full site information
        site_response = table.query(
            IndexName='GSI1',
            KeyConditionExpression='GSI1PK = :pk AND GSI1SK = :sk',
            ExpressionAttributeValues={
                ':pk': f'SITE#{site_id}',
                ':sk': 'ACTIVE'
            },
            Limit=1
        )
        
        site_items = site_response.get('Items', [])
        if not site_items:
            return None
        
        site_info = site_items[0]
        
        # Verify site is active
        if site_info.get('status') != 'active':
            return None
        
        return {
            'site_id': site_id,
            'domain': domain,
            'api_key_hash': api_key_hash,
            'webhook_secret': site_info.get('webhook_secret'),
            'created_at': site_info.get('created_at'),
            'last_seen': site_info.get('last_seen'),
            'request_count': site_info.get('request_count', 0)
        }
        
    except Exception as e:
        logger.warning("API key validation error", extra={'error': str(e)})
        return None

def _check_rate_limits(site_id: str) -> Dict[str, Any]:
    """Check if site is within rate limits"""
    try:
        current_time = int(time.time())
        
        # Define time windows
        windows = {
            'minute': (current_time - 60, RATE_LIMITS['requests_per_minute']),
            'hour': (current_time - 3600, RATE_LIMITS['requests_per_hour']),
            'day': (current_time - 86400, RATE_LIMITS['requests_per_day'])
        }
        
        for window_name, (window_start, limit) in windows.items():
            # Query rate limit records for this window
            response = table.query(
                KeyConditionExpression='PK = :pk AND SK BETWEEN :start AND :end',
                ExpressionAttributeValues={
                    ':pk': f'RATE#{site_id}',
                    ':start': f'TIME#{window_start}',
                    ':end': f'TIME#{current_time}'
                }
            )
            
            count = len(response.get('Items', []))
            if count >= limit:
                return {
                    'allowed': False,
                    'limit_type': window_name,
                    'count': count,
                    'limit': limit
                }
        
        return {'allowed': True}
        
    except Exception as e:
        logger.warning("Rate limit check failed", extra={
            'site_id': site_id,
            'error': str(e)
        })
        return {'allowed': True}  # Fail open for availability

def _detect_suspicious_activity(site_id: str) -> bool:
    """Detect suspicious activity patterns"""
    try:
        current_time = int(time.time())
        
        # Check for burst requests (more than X requests per second)
        burst_start = current_time - 1  # Last second
        response = table.query(
            KeyConditionExpression='PK = :pk AND SK BETWEEN :start AND :end',
            ExpressionAttributeValues={
                ':pk': f'RATE#{site_id}',
                ':start': f'TIME#{burst_start}',
                ':end': f'TIME#{current_time}'
            }
        )
        
        if len(response.get('Items', [])) > SUSPICIOUS_PATTERNS['max_requests_per_second']:
            return True
        
        # Check for failed authentication attempts
        hour_start = current_time - 3600
        failed_response = table.query(
            KeyConditionExpression='PK = :pk AND SK BETWEEN :start AND :end',
            ExpressionAttributeValues={
                ':pk': f'FAILED#{site_id}',
                ':start': f'TIME#{hour_start}',
                ':end': f'TIME#{current_time}'
            }
        )
        
        if len(failed_response.get('Items', [])) > SUSPICIOUS_PATTERNS['max_failed_attempts_per_hour']:
            return True
        
        return False
        
    except Exception as e:
        logger.warning("Suspicious activity check failed", extra={'error': str(e)})
        return False

def _update_site_activity(site_info: Dict[str, Any]):
    """Update site last seen timestamp and request count"""
    try:
        table.update_item(
            Key={
                'PK': f'SITE#{site_info["domain"]}',
                'SK': f'CREDS#{site_info["site_id"]}'
            },
            UpdateExpression='SET last_seen = :timestamp, request_count = request_count + :inc',
            ExpressionAttributeValues={
                ':timestamp': datetime.utcnow().isoformat() + 'Z',
                ':inc': 1
            }
        )
    except Exception as e:
        logger.warning("Failed to update site activity", extra={'error': str(e)})

def _update_rate_limit_counters(site_id: str):
    """Update rate limit counters"""
    try:
        current_time = int(time.time())
        
        # Store rate limit record with TTL
        table.put_item(
            Item={
                'PK': f'RATE#{site_id}',
                'SK': f'TIME#{current_time}',
                'timestamp': current_time,
                'ttl': current_time + 86400  # Keep for 24 hours
            }
        )
    except Exception as e:
        logger.warning("Failed to update rate limit counters", extra={'error': str(e)})

def _hash_api_key(api_key: str) -> str:
    """Create hash of API key for lookup"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def _generate_policy(effect: str, resource: str, site_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate IAM policy for API Gateway"""
    policy = {
        'principalId': site_info['site_id'] if site_info else 'unauthorized',
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }
    
    # Add context for downstream Lambda functions
    if site_info and effect == 'Allow':
        policy['context'] = {
            'site_id': site_info['site_id'],
            'domain': site_info['domain'],
            'webhook_secret': site_info['webhook_secret'],
            'request_count': str(site_info['request_count'])
        }
    
    return policy
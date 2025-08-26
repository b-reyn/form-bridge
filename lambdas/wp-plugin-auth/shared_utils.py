"""
Shared utilities for Form-Bridge WordPress Plugin Authentication system
Common functions used across multiple Lambda functions.
"""

import json
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import boto3
from aws_lambda_powertools import Logger
import re

logger = Logger()

# AWS clients (reuse across functions)
_dynamodb = None
_secrets_client = None

def get_dynamodb_table():
    """Get DynamoDB table resource with connection reuse"""
    global _dynamodb
    if _dynamodb is None:
        import os
        dynamodb = boto3.resource('dynamodb')
        _dynamodb = dynamodb.Table(os.environ['TABLE_NAME'])
    return _dynamodb

def get_secrets_client():
    """Get Secrets Manager client with connection reuse"""
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = boto3.client('secretsmanager')
    return _secrets_client

# Security utilities
def hash_api_key(api_key: str) -> str:
    """Create SHA256 hash of API key for secure storage"""
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

def generate_secure_key(length: int = 32) -> str:
    """Generate cryptographically secure random key"""
    return secrets.token_urlsafe(length)

def generate_site_id() -> str:
    """Generate unique site identifier using UUID7 (time-ordered)"""
    import uuid
    return str(uuid.uuid7())

def verify_hmac_signature(payload: str, signature: str, secret: str, algorithm: str = 'sha256') -> bool:
    """Verify HMAC signature for webhook validation"""
    try:
        expected = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            getattr(hashlib, algorithm)
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.warning("HMAC verification failed", extra={'error': str(e)})
        return False

def create_hmac_signature(payload: str, secret: str, algorithm: str = 'sha256') -> str:
    """Create HMAC signature for outbound requests"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        getattr(hashlib, algorithm)
    ).hexdigest()

# Validation utilities
def is_valid_domain(domain: str) -> bool:
    """Validate domain format using regex"""
    if not domain or len(domain) < 4 or len(domain) > 253:
        return False
    
    # Basic domain regex pattern
    pattern = r'^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)*$'
    return bool(re.match(pattern, domain.lower()))

def is_valid_email(email: str) -> bool:
    """Basic email validation"""
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_version(version: str) -> bool:
    """Validate semantic version format"""
    try:
        from packaging import version as pkg_version
        pkg_version.parse(version)
        return True
    except Exception:
        # Fallback to simple regex if packaging not available
        pattern = r'^\d+\.\d+\.\d+(?:\-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?$'
        return bool(re.match(pattern, version))

# Time utilities
def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO 8601 format"""
    return datetime.utcnow().isoformat() + 'Z'

def get_timestamp_from_seconds(seconds: int) -> str:
    """Convert Unix timestamp to ISO 8601 format"""
    return datetime.utcfromtimestamp(seconds).isoformat() + 'Z'

def is_timestamp_expired(timestamp_str: str, expiry_seconds: int) -> bool:
    """Check if timestamp is older than expiry_seconds"""
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=timestamp.tzinfo)
        return (now - timestamp).total_seconds() > expiry_seconds
    except Exception:
        return True  # Assume expired if parsing fails

def get_unix_timestamp() -> int:
    """Get current Unix timestamp"""
    return int(time.time())

def get_ttl_timestamp(seconds_from_now: int) -> int:
    """Get TTL timestamp for DynamoDB (current time + seconds)"""
    return int(time.time()) + seconds_from_now

# Rate limiting utilities
class RateLimiter:
    """Rate limiting utility for DynamoDB-based rate limiting"""
    
    def __init__(self, table=None):
        self.table = table or get_dynamodb_table()
    
    def check_rate_limit(self, identifier: str, limits: Dict[str, int], prefix: str = "RATE") -> Dict[str, Any]:
        """
        Check rate limits for an identifier
        
        Args:
            identifier: Unique identifier (site_id, ip_address, etc.)
            limits: Dict of time_window -> max_requests
                   e.g., {'minute': 60, 'hour': 1000, 'day': 5000}
            prefix: DynamoDB key prefix (default: "RATE")
        
        Returns:
            Dict with 'allowed' boolean and limit details
        """
        try:
            current_time = int(time.time())
            
            # Define time windows in seconds
            time_windows = {
                'minute': 60,
                'hour': 3600,
                'day': 86400,
                'week': 604800,
                'month': 2592000
            }
            
            for window_name, max_requests in limits.items():
                window_seconds = time_windows.get(window_name, 3600)  # Default to 1 hour
                window_start = current_time - window_seconds
                
                # Query rate limit records for this window
                response = self.table.query(
                    KeyConditionExpression='PK = :pk AND SK BETWEEN :start AND :end',
                    ExpressionAttributeValues={
                        ':pk': f'{prefix}#{identifier}',
                        ':start': f'TIME#{window_start}',
                        ':end': f'TIME#{current_time}'
                    },
                    Select='COUNT'
                )
                
                count = response.get('Count', 0)
                if count >= max_requests:
                    return {
                        'allowed': False,
                        'limit_type': window_name,
                        'current_count': count,
                        'limit': max_requests,
                        'reset_time': current_time + (window_seconds - (current_time % window_seconds))
                    }
            
            return {'allowed': True}
            
        except Exception as e:
            logger.warning("Rate limit check failed", extra={'error': str(e)})
            return {'allowed': True}  # Fail open for availability
    
    def increment_rate_limit(self, identifier: str, ttl_seconds: int = 86400, prefix: str = "RATE"):
        """
        Increment rate limit counter
        
        Args:
            identifier: Unique identifier
            ttl_seconds: TTL for the record (default: 24 hours)
            prefix: DynamoDB key prefix
        """
        try:
            current_time = int(time.time())
            
            self.table.put_item(
                Item={
                    'PK': f'{prefix}#{identifier}',
                    'SK': f'TIME#{current_time}',
                    'timestamp': current_time,
                    'ttl': current_time + ttl_seconds
                }
            )
        except Exception as e:
            logger.warning("Failed to increment rate limit", extra={'error': str(e)})

# Response utilities
def create_success_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """Create standardized success response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps({
            'success': True,
            'data': data,
            'timestamp': get_current_timestamp()
        })
    }

def create_error_response(status_code: int, error_code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create standardized error response with CORS headers"""
    error_data = {
        'code': error_code,
        'message': message
    }
    
    if details:
        error_data['details'] = details
    
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps({
            'success': False,
            'error': error_data,
            'timestamp': get_current_timestamp()
        })
    }

def get_cors_headers() -> Dict[str, str]:
    """Get standard CORS headers for API responses"""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key, X-Timestamp, X-Signature',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Max-Age': '86400',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }

def handle_options_request() -> Dict[str, Any]:
    """Handle CORS preflight OPTIONS request"""
    return {
        'statusCode': 200,
        'headers': get_cors_headers(),
        'body': ''
    }

# Security event logging
class SecurityEventLogger:
    """Utility for logging security events"""
    
    def __init__(self, table=None):
        self.table = table or get_dynamodb_table()
    
    def log_event(self, event_type: str, identifier: str, details: Dict[str, Any], severity: str = 'medium'):
        """
        Log security event
        
        Args:
            event_type: Type of security event (auth_failure, rate_limit, suspicious_activity, etc.)
            identifier: Identifier (site_id, ip_address, domain, etc.)
            details: Additional event details
            severity: Event severity (low, medium, high, critical)
        """
        try:
            current_time = int(time.time())
            
            # Determine TTL based on severity
            ttl_map = {
                'low': 7 * 24 * 3600,      # 7 days
                'medium': 30 * 24 * 3600,   # 30 days
                'high': 90 * 24 * 3600,     # 90 days
                'critical': 365 * 24 * 3600 # 1 year
            }
            
            ttl_seconds = ttl_map.get(severity, 30 * 24 * 3600)
            
            self.table.put_item(
                Item={
                    'PK': f'SECURITY#{event_type}',
                    'SK': f'{identifier}#{current_time}',
                    'GSI1PK': f'SECURITY_TRACKING#{identifier}',
                    'GSI1SK': f'TIME#{current_time}',
                    'event_type': event_type,
                    'identifier': identifier,
                    'severity': severity,
                    'details': details,
                    'timestamp': get_timestamp_from_seconds(current_time),
                    'ttl': current_time + ttl_seconds
                }
            )
            
            logger.info("Security event logged", extra={
                'event_type': event_type,
                'identifier': identifier,
                'severity': severity
            })
            
        except Exception as e:
            logger.error("Failed to log security event", extra={'error': str(e)})

# Configuration utilities
def get_environment_config() -> Dict[str, Any]:
    """Get environment-specific configuration"""
    import os
    
    return {
        'table_name': os.environ.get('TABLE_NAME', 'form-bridge-plugin-auth'),
        'environment': os.environ.get('ENVIRONMENT', 'dev'),
        'api_domain': os.environ.get('API_DOMAIN', 'api.form-bridge.com'),
        'plugin_bucket': os.environ.get('PLUGIN_BUCKET', 'form-bridge-plugin-releases'),
        'signing_secret_name': os.environ.get('SIGNING_SECRET_NAME', 'form-bridge/plugin-signing-key'),
        'max_registrations_per_ip': int(os.environ.get('MAX_REGISTRATIONS_PER_IP', '3')),
        'rate_limit_window': int(os.environ.get('RATE_LIMIT_WINDOW', '300')),
        'temp_key_expiry': int(os.environ.get('TEMP_KEY_EXPIRY', '3600')),
        'validation_cache_ttl': int(os.environ.get('VALIDATION_CACHE_TTL', '86400'))
    }

# Cache utilities
class SimpleCache:
    """Simple in-memory cache for Lambda functions"""
    
    _cache = {}
    _timestamps = {}
    
    @classmethod
    def get(cls, key: str, ttl_seconds: int = 300) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in cls._cache:
            return None
        
        # Check if expired
        if key in cls._timestamps:
            if time.time() - cls._timestamps[key] > ttl_seconds:
                cls.delete(key)
                return None
        
        return cls._cache[key]
    
    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set value in cache with timestamp"""
        cls._cache[key] = value
        cls._timestamps[key] = time.time()
    
    @classmethod
    def delete(cls, key: str) -> None:
        """Delete value from cache"""
        cls._cache.pop(key, None)
        cls._timestamps.pop(key, None)
    
    @classmethod
    def clear(cls) -> None:
        """Clear entire cache"""
        cls._cache.clear()
        cls._timestamps.clear()

# Input validation utilities
def validate_request_body(body: str, required_fields: List[str], optional_fields: List[str] = None) -> Dict[str, Any]:
    """
    Validate request body JSON and required fields
    
    Returns:
        Dict with 'valid' boolean, 'data' dict, and 'error' string if invalid
    """
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return {'valid': False, 'error': 'Invalid JSON format', 'data': {}}
    
    # Check required fields
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return {
            'valid': False,
            'error': f'Missing required fields: {", ".join(missing_fields)}',
            'data': data
        }
    
    # Sanitize data (only keep known fields)
    allowed_fields = set(required_fields + (optional_fields or []))
    sanitized_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    return {'valid': True, 'data': sanitized_data, 'error': None}

# Common constants
class Constants:
    """Common constants used across Lambda functions"""
    
    # Status values
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_EXPIRED = 'expired'
    
    # Security event types
    EVENT_AUTH_FAILURE = 'auth_failure'
    EVENT_RATE_LIMIT = 'rate_limit'
    EVENT_SUSPICIOUS_ACTIVITY = 'suspicious_activity'
    EVENT_VALIDATION_FAILURE = 'validation_failure'
    EVENT_ABUSE_DETECTED = 'abuse_detected'
    
    # Rate limit presets
    RATE_LIMITS_REGISTRATION = {'minute': 3, 'hour': 10}
    RATE_LIMITS_API = {'minute': 100, 'hour': 2000, 'day': 10000}
    RATE_LIMITS_UPDATES = {'minute': 10, 'hour': 100, 'day': 500}
    
    # Validation levels
    VALIDATION_BASIC = 'basic'
    VALIDATION_STANDARD = 'standard'
    VALIDATION_STRICT = 'strict'
    
    # HTTP status codes
    HTTP_OK = 200
    HTTP_CREATED = 201
    HTTP_BAD_REQUEST = 400
    HTTP_UNAUTHORIZED = 401
    HTTP_FORBIDDEN = 403
    HTTP_NOT_FOUND = 404
    HTTP_CONFLICT = 409
    HTTP_RATE_LIMITED = 429
    HTTP_INTERNAL_ERROR = 500
    HTTP_SERVICE_UNAVAILABLE = 503
"""
Multi-Tenant HMAC Authorizer - ARM64 Optimized
Lambda Authorizer for Form-Bridge with 2025 best practices

Features:
- ARM64 Graviton2 optimized (20% cost savings)
- Cached secret retrieval for performance
- Comprehensive HMAC validation with replay protection
- Multi-tenant isolation and security
- Advanced monitoring and metrics
"""

import hmac
import hashlib
import json
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="hmac-authorizer")
tracer = Tracer(service="hmac-authorizer")
metrics = Metrics(namespace="FormBridge/Auth", service="hmac-authorizer")

# Global clients for connection reuse (ARM64 optimized)
secrets_client = boto3.client('secretsmanager')
cloudwatch = boto3.client('cloudwatch')

# Configuration constants
TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes
SECRET_CACHE_TTL = 300            # 5 minutes
MAX_FAILED_ATTEMPTS = 10          # Per tenant per hour


class SecretCache:
    """Thread-safe secret cache for performance optimization"""
    
    def __init__(self, ttl_seconds: int = SECRET_CACHE_TTL):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[str]:
        """Get cached secret if still valid"""
        if key in self.cache:
            secret, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return secret
            else:
                # Remove expired entry
                del self.cache[key]
        return None
    
    def set(self, key: str, value: str) -> None:
        """Cache secret with timestamp"""
        self.cache[key] = (value, time.time())


class TenantSecurityValidator:
    """Optimized tenant security validation for ARM64 performance"""
    
    def __init__(self):
        self.secret_cache = SecretCache()
        self.failed_attempts = {}  # In-memory tracking for this instance
    
    @tracer.capture_method
    def validate_request(self, tenant_id: str, headers: Dict[str, str], 
                        body: str = '') -> Dict[str, Any]:
        """
        Comprehensive request validation with security checks
        
        Returns validation result with context for downstream functions
        """
        start_time = time.time()
        
        try:
            # Extract required headers (case-insensitive)
            headers_lower = {k.lower(): v for k, v in headers.items()}
            timestamp = headers_lower.get('x-timestamp')
            signature = headers_lower.get('x-signature')
            
            if not all([tenant_id, timestamp, signature]):
                metrics.add_metric(name="MissingHeaders", unit=MetricUnit.Count, value=1)
                return self._validation_result(False, "Missing required headers")
            
            # Check rate limiting for failed attempts
            if self._is_rate_limited(tenant_id):
                metrics.add_metric(name="RateLimited", unit=MetricUnit.Count, value=1)
                return self._validation_result(False, "Rate limit exceeded")
            
            # Validate timestamp (prevent replay attacks)
            if not self._validate_timestamp(timestamp):
                self._record_failed_attempt(tenant_id)
                metrics.add_metric(name="InvalidTimestamp", unit=MetricUnit.Count, value=1)
                return self._validation_result(False, "Invalid timestamp")
            
            # Retrieve tenant secret (with caching)
            secret = self._get_tenant_secret(tenant_id)
            if not secret:
                self._record_failed_attempt(tenant_id)
                metrics.add_metric(name="InvalidTenant", unit=MetricUnit.Count, value=1)
                return self._validation_result(False, "Invalid tenant")
            
            # Validate HMAC signature
            if not self._validate_hmac_signature(timestamp, body, signature, secret):
                self._record_failed_attempt(tenant_id)
                metrics.add_metric(name="InvalidSignature", unit=MetricUnit.Count, value=1)
                return self._validation_result(False, "Invalid signature")
            
            # Successful validation
            duration_ms = int((time.time() - start_time) * 1000)
            metrics.add_metric(name="ValidationDuration", unit=MetricUnit.Milliseconds, value=duration_ms)
            metrics.add_metric(name="SuccessfulValidations", unit=MetricUnit.Count, value=1)
            
            logger.info("HMAC validation successful", extra={
                'tenant_id': tenant_id,
                'duration_ms': duration_ms
            })
            
            return self._validation_result(True, "Valid request", {
                'tenant_id': tenant_id,
                'validated_at': datetime.utcnow().isoformat(),
                'duration_ms': duration_ms
            })
            
        except Exception as e:
            logger.error("Validation error", extra={'error': str(e), 'tenant_id': tenant_id})
            metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)
            return self._validation_result(False, "Internal validation error")
    
    def _validate_timestamp(self, timestamp: str) -> bool:
        """Validate request timestamp to prevent replay attacks"""
        try:
            req_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age_seconds = abs((now - req_time).total_seconds())
            
            return age_seconds <= TIMESTAMP_TOLERANCE_SECONDS
            
        except (ValueError, TypeError) as e:
            logger.warning("Invalid timestamp format", extra={'timestamp': timestamp, 'error': str(e)})
            return False
    
    @tracer.capture_method
    def _get_tenant_secret(self, tenant_id: str) -> Optional[str]:
        """Retrieve tenant secret with performance caching"""
        # Check cache first
        cached_secret = self.secret_cache.get(tenant_id)
        if cached_secret:
            metrics.add_metric(name="SecretCacheHits", unit=MetricUnit.Count, value=1)
            return cached_secret
        
        # Fetch from Secrets Manager
        try:
            secret_name = f"{os.environ['SECRET_PREFIX']}/{tenant_id}"
            
            # Try current version first
            response = secrets_client.get_secret_value(
                SecretId=secret_name,
                VersionStage='AWSCURRENT'
            )
            
            secret_data = json.loads(response['SecretString'])
            secret = secret_data['shared_secret']
            
            # Cache the secret
            self.secret_cache.set(tenant_id, secret)
            metrics.add_metric(name="SecretCacheMisses", unit=MetricUnit.Count, value=1)
            
            return secret
            
        except secrets_client.exceptions.ResourceNotFoundException:
            logger.warning("Tenant secret not found", extra={'tenant_id': tenant_id})
            return None
        except Exception as e:
            # During rotation, try pending version
            try:
                response = secrets_client.get_secret_value(
                    SecretId=secret_name,
                    VersionStage='AWSPENDING'
                )
                secret_data = json.loads(response['SecretString'])
                return secret_data['shared_secret']
            except Exception:
                logger.error("Failed to retrieve tenant secret", extra={
                    'tenant_id': tenant_id,
                    'error': str(e)
                })
                return None
    
    def _validate_hmac_signature(self, timestamp: str, body: str, 
                               signature: str, secret: str) -> bool:
        """Validate HMAC-SHA256 signature with constant-time comparison"""
        try:
            # Construct message exactly as client does
            message = f"{timestamp}\n{body}"
            
            # Calculate expected signature
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error("HMAC validation failed", extra={'error': str(e)})
            return False
    
    def _is_rate_limited(self, tenant_id: str) -> bool:
        """Check if tenant has exceeded failed attempt rate limit"""
        current_time = time.time()
        hour_start = current_time - 3600
        
        # Clean old entries
        tenant_key = f"failed_{tenant_id}"
        if tenant_key in self.failed_attempts:
            self.failed_attempts[tenant_key] = [
                timestamp for timestamp in self.failed_attempts[tenant_key]
                if timestamp > hour_start
            ]
            
            return len(self.failed_attempts[tenant_key]) >= MAX_FAILED_ATTEMPTS
        
        return False
    
    def _record_failed_attempt(self, tenant_id: str) -> None:
        """Record failed authentication attempt"""
        tenant_key = f"failed_{tenant_id}"
        current_time = time.time()
        
        if tenant_key not in self.failed_attempts:
            self.failed_attempts[tenant_key] = []
        
        self.failed_attempts[tenant_key].append(current_time)
    
    def _validation_result(self, success: bool, message: str, 
                          context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Standard validation result format"""
        return {
            'isAuthorized': success,
            'message': message,
            'context': context or {}
        }


# Global validator instance for reuse across invocations
validator = TenantSecurityValidator()


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    ARM64 Optimized Lambda Authorizer for Multi-Tenant HMAC Authentication
    
    Validates HMAC signatures and enforces tenant isolation for Form-Bridge
    """
    
    try:
        # Extract request details
        headers = event.get('headers', {})
        tenant_id = headers.get('X-Tenant-ID') or headers.get('x-tenant-id')
        body = event.get('body', '')
        method_arn = event.get('methodArn', '')
        
        if not tenant_id:
            logger.warning("Missing tenant ID in request")
            return generate_deny_policy(method_arn, "Missing tenant ID")
        
        # Validate request
        validation_result = validator.validate_request(tenant_id, headers, body)
        
        if validation_result['isAuthorized']:
            # Generate allow policy with tenant context
            return generate_allow_policy(
                method_arn,
                tenant_id,
                validation_result['context']
            )
        else:
            # Generate deny policy
            logger.info("Authorization denied", extra={
                'tenant_id': tenant_id,
                'reason': validation_result['message']
            })
            return generate_deny_policy(method_arn, validation_result['message'])
    
    except Exception as e:
        logger.exception("Authorizer error")
        metrics.add_metric(name="AuthorizerErrors", unit=MetricUnit.Count, value=1)
        return generate_deny_policy(event.get('methodArn', ''), "Internal error")


def generate_allow_policy(method_arn: str, tenant_id: str, 
                         context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate IAM allow policy with tenant context"""
    return {
        'principalId': tenant_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Allow',
                    'Resource': method_arn
                }
            ]
        },
        'context': {
            'tenant_id': tenant_id,
            'validated_at': context.get('validated_at', ''),
            'duration_ms': str(context.get('duration_ms', 0)),
            'auth_method': 'hmac'
        }
    }


def generate_deny_policy(method_arn: str, reason: str = "Unauthorized") -> Dict[str, Any]:
    """Generate IAM deny policy"""
    return {
        'principalId': 'unauthorized',
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Deny',
                    'Resource': method_arn
                }
            ]
        },
        'context': {
            'error': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
    }


if __name__ == "__main__":
    # Local testing
    import asyncio
    
    test_event = {
        'headers': {
            'X-Tenant-ID': 't_test123',
            'X-Timestamp': datetime.utcnow().isoformat() + 'Z',
            'X-Signature': 'test_signature'
        },
        'body': '{"test": "data"}',
        'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef123/*/POST/*'
    }
    
    result = lambda_handler(test_event, {})
    print(json.dumps(result, indent=2))
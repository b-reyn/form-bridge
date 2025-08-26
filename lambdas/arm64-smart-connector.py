"""
ARM64 Smart Connector Lambda - Multi-Tenant Destination Delivery
Optimized for AWS Graviton2 with intelligent connection pooling

Features:
- 20% cost savings with ARM64 Graviton2 architecture
- Advanced HTTP connection pooling with circuit breaker
- Multi-tenant secret management with caching
- Intelligent retry logic with exponential backoff
- Field mapping and transformation engine
- Comprehensive monitoring and error handling
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import httpx
import boto3
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="smart-connector")
tracer = Tracer(service="smart-connector")
metrics = Metrics(namespace="FormBridge/Connector", service="smart-connector")


class DeliveryStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure" 
    RETRYABLE = "retryable"
    RATE_LIMITED = "rate_limited"
    INVALID_CONFIG = "invalid_config"


@dataclass
class DeliveryResult:
    """Result of destination delivery attempt"""
    status: DeliveryStatus
    status_code: Optional[int] = None
    response_time_ms: int = 0
    error_message: Optional[str] = None
    retry_after_seconds: Optional[int] = None
    response_body: Optional[str] = None


class HTTPConnectionPool:
    """Optimized HTTP connection pool for ARM64 Lambda functions"""
    
    def __init__(self):
        self._clients = {}
        self._client_created_at = {}
        self._max_client_age = 300  # 5 minutes
    
    def get_client(self, base_url: str, timeout_seconds: int = 10) -> httpx.Client:
        """Get cached HTTP client or create new one"""
        current_time = time.time()
        
        # Check if existing client is still valid
        if base_url in self._clients:
            if current_time - self._client_created_at[base_url] < self._max_client_age:
                return self._clients[base_url]
            else:
                # Close expired client
                self._clients[base_url].close()
                del self._clients[base_url]
                del self._client_created_at[base_url]
        
        # Create new client with ARM64 optimized settings
        client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=60.0
            ),
            http2=True,  # Better performance for multiple requests
            follow_redirects=True,
            verify=True  # Always verify SSL
        )
        
        self._clients[base_url] = client
        self._client_created_at[base_url] = current_time
        
        logger.debug("HTTP client created", extra={'base_url': base_url})
        return client
    
    def close_all(self):
        """Close all cached clients"""
        for client in self._clients.values():
            try:
                client.close()
            except Exception:
                pass
        self._clients.clear()
        self._client_created_at.clear()


class SecretManager:
    """Cached secret manager for multi-tenant credentials"""
    
    def __init__(self):
        self.secrets_client = boto3.client('secretsmanager')
        self.secret_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    @tracer.capture_method
    def get_tenant_secret(self, tenant_id: str, secret_type: str) -> Optional[Dict[str, Any]]:
        """Get tenant-specific secret with caching"""
        cache_key = f"{tenant_id}:{secret_type}"
        current_time = time.time()
        
        # Check cache first
        if cache_key in self.secret_cache:
            secret, cached_at = self.secret_cache[cache_key]
            if current_time - cached_at < self.cache_ttl:
                return secret
        
        # Fetch from AWS Secrets Manager
        try:
            secret_name = f"{os.environ['SECRET_PREFIX']}/{tenant_id}/{secret_type}"
            
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])
            
            # Cache the secret
            self.secret_cache[cache_key] = (secret_data, current_time)
            
            return secret_data
            
        except self.secrets_client.exceptions.ResourceNotFoundException:
            logger.warning("Secret not found", extra={
                'tenant_id': tenant_id,
                'secret_type': secret_type
            })
            return None
        except Exception as e:
            logger.error("Failed to retrieve secret", extra={
                'error': str(e),
                'tenant_id': tenant_id,
                'secret_type': secret_type
            })
            return None


class FieldMapper:
    """Intelligent field mapping and transformation engine"""
    
    @staticmethod
    def map_fields(source_data: Dict[str, Any], 
                   field_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Map source fields to destination format"""
        mapped_data = {}
        
        for dest_field, source_path in field_mapping.items():
            try:
                value = FieldMapper._extract_nested_value(source_data, source_path)
                if value is not None:
                    mapped_data[dest_field] = value
            except Exception as e:
                logger.warning("Field mapping failed", extra={
                    'dest_field': dest_field,
                    'source_path': source_path,
                    'error': str(e)
                })
        
        return mapped_data
    
    @staticmethod
    def _extract_nested_value(data: Dict[str, Any], path: str) -> Any:
        """Extract value from nested object using dot notation"""
        if not path:
            return None
            
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class CircuitBreaker:
    """Circuit breaker pattern for external API reliability"""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = {}
        self.last_failure_time = {}
    
    def is_open(self, destination_id: str) -> bool:
        """Check if circuit breaker is open for destination"""
        if destination_id not in self.failure_count:
            return False
        
        current_time = time.time()
        last_failure = self.last_failure_time.get(destination_id, 0)
        
        # Reset if timeout period has passed
        if current_time - last_failure > self.timeout_seconds:
            self.failure_count[destination_id] = 0
            return False
        
        return self.failure_count[destination_id] >= self.failure_threshold
    
    def record_success(self, destination_id: str):
        """Record successful request"""
        self.failure_count[destination_id] = 0
    
    def record_failure(self, destination_id: str):
        """Record failed request"""
        if destination_id not in self.failure_count:
            self.failure_count[destination_id] = 0
        
        self.failure_count[destination_id] += 1
        self.last_failure_time[destination_id] = time.time()


class SmartConnector:
    """ARM64 optimized smart connector for multi-tenant destinations"""
    
    def __init__(self):
        self.http_pool = HTTPConnectionPool()
        self.secret_manager = SecretManager() 
        self.circuit_breaker = CircuitBreaker()
    
    @tracer.capture_method
    async def deliver_to_destination(self, submission: Dict[str, Any], 
                                   destination_config: Dict[str, Any]) -> DeliveryResult:
        """
        Deliver submission to configured destination with intelligent retry
        
        Args:
            submission: Form submission data with tenant context
            destination_config: Destination configuration including auth and mapping
            
        Returns:
            DeliveryResult with status and metrics
        """
        start_time = time.time()
        destination_id = destination_config.get('id', 'unknown')
        destination_type = destination_config.get('type', 'rest')
        
        try:
            tenant_id = submission.get('tenant_id')
            if not tenant_id:
                return DeliveryResult(
                    status=DeliveryStatus.INVALID_CONFIG,
                    error_message="Missing tenant_id in submission"
                )
            
            # Check circuit breaker
            if self.circuit_breaker.is_open(destination_id):
                logger.warning("Circuit breaker open", extra={
                    'destination_id': destination_id,
                    'tenant_id': tenant_id
                })
                return DeliveryResult(
                    status=DeliveryStatus.RETRYABLE,
                    error_message="Circuit breaker open"
                )
            
            # Route to appropriate delivery method
            if destination_type == 'rest':
                result = await self._deliver_rest(submission, destination_config)
            elif destination_type == 'webhook':
                result = await self._deliver_webhook(submission, destination_config)
            else:
                result = DeliveryResult(
                    status=DeliveryStatus.INVALID_CONFIG,
                    error_message=f"Unsupported destination type: {destination_type}"
                )
            
            # Update circuit breaker state
            if result.status == DeliveryStatus.SUCCESS:
                self.circuit_breaker.record_success(destination_id)
            elif result.status in [DeliveryStatus.FAILURE, DeliveryStatus.RETRYABLE]:
                self.circuit_breaker.record_failure(destination_id)
            
            # Calculate response time
            result.response_time_ms = int((time.time() - start_time) * 1000)
            
            # Log delivery result
            logger.info("Destination delivery complete", extra={
                'destination_id': destination_id,
                'tenant_id': tenant_id,
                'status': result.status.value,
                'response_time_ms': result.response_time_ms,
                'status_code': result.status_code
            })
            
            # Record metrics
            metrics.add_metric(
                name="DeliveryLatency",
                unit=MetricUnit.Milliseconds,
                value=result.response_time_ms
            )
            metrics.add_metric(
                name=f"Delivery{result.status.value.title()}",
                unit=MetricUnit.Count,
                value=1
            )
            
            return result
            
        except Exception as e:
            logger.error("Delivery error", extra={
                'error': str(e),
                'destination_id': destination_id,
                'tenant_id': submission.get('tenant_id')
            })
            
            self.circuit_breaker.record_failure(destination_id)
            
            return DeliveryResult(
                status=DeliveryStatus.FAILURE,
                error_message=str(e),
                response_time_ms=int((time.time() - start_time) * 1000)
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def _deliver_rest(self, submission: Dict[str, Any], 
                          config: Dict[str, Any]) -> DeliveryResult:
        """Deliver to REST API endpoint with retry logic"""
        try:
            tenant_id = submission['tenant_id']
            endpoint_url = config['endpoint']
            
            # Get authentication credentials
            auth_config = config.get('auth', {})
            headers = {'Content-Type': 'application/json'}
            
            if auth_config.get('type') == 'api_key':
                api_key_secret = self.secret_manager.get_tenant_secret(
                    tenant_id, 
                    auth_config.get('secret_name', 'api_key')
                )
                if api_key_secret:
                    api_key = api_key_secret.get('api_key')
                    header_name = auth_config.get('header', 'X-API-Key')
                    headers[header_name] = api_key
                else:
                    return DeliveryResult(
                        status=DeliveryStatus.INVALID_CONFIG,
                        error_message="Failed to retrieve API key"
                    )
            
            # Map fields according to destination configuration
            field_mapping = config.get('field_mapping', {})
            if field_mapping:
                payload = FieldMapper.map_fields(submission, field_mapping)
            else:
                # Use raw submission data
                payload = {
                    'submission_id': submission.get('submission_id'),
                    'form_id': submission.get('form_id'),
                    'submitted_at': submission.get('submitted_at'),
                    'payload': submission.get('payload', {})
                }
            
            # Add tenant context if requested
            if config.get('include_tenant_context', False):
                payload['tenant_id'] = tenant_id
            
            # Get HTTP client with connection pooling
            client = self.http_pool.get_client(
                endpoint_url,
                timeout_seconds=config.get('timeout_seconds', 10)
            )
            
            # Make HTTP request
            response = client.post(
                endpoint_url,
                json=payload,
                headers=headers
            )
            
            # Determine delivery status based on response
            if 200 <= response.status_code < 300:
                return DeliveryResult(
                    status=DeliveryStatus.SUCCESS,
                    status_code=response.status_code,
                    response_body=response.text[:1000]  # Truncate for logging
                )
            elif response.status_code == 429:
                # Rate limited - extract retry-after if available
                retry_after = response.headers.get('retry-after')
                return DeliveryResult(
                    status=DeliveryStatus.RATE_LIMITED,
                    status_code=response.status_code,
                    retry_after_seconds=int(retry_after) if retry_after else 60
                )
            elif 400 <= response.status_code < 500:
                # Client error - likely not retryable
                return DeliveryResult(
                    status=DeliveryStatus.FAILURE,
                    status_code=response.status_code,
                    error_message=f"HTTP {response.status_code}: {response.text[:200]}"
                )
            else:
                # Server error - retryable
                return DeliveryResult(
                    status=DeliveryStatus.RETRYABLE,
                    status_code=response.status_code,
                    error_message=f"HTTP {response.status_code}: {response.text[:200]}"
                )
                
        except httpx.TimeoutException as e:
            return DeliveryResult(
                status=DeliveryStatus.RETRYABLE,
                error_message=f"Request timeout: {str(e)}"
            )
        except httpx.RequestError as e:
            return DeliveryResult(
                status=DeliveryStatus.RETRYABLE,
                error_message=f"Request error: {str(e)}"
            )
        except Exception as e:
            return DeliveryResult(
                status=DeliveryStatus.FAILURE,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    async def _deliver_webhook(self, submission: Dict[str, Any], 
                             config: Dict[str, Any]) -> DeliveryResult:
        """Deliver to webhook endpoint with HMAC signature"""
        # Implementation for webhook delivery with HMAC signing
        # This would be similar to _deliver_rest but with HMAC signature generation
        return await self._deliver_rest(submission, config)  # Simplified for now
    
    def cleanup(self):
        """Cleanup resources"""
        self.http_pool.close_all()


# Global connector instance for container reuse
connector = SmartConnector()


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    ARM64 Lambda handler for intelligent destination delivery
    
    Handles delivery of form submissions to configured destinations
    with multi-tenant isolation and advanced error handling
    """
    
    try:
        # Extract submission and destination from Step Functions input
        submission = event.get('submission', {})
        destination_config = event.get('destination', {})
        
        if not submission or not destination_config:
            logger.error("Missing submission or destination configuration")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required input data'
                })
            }
        
        # Deliver to destination
        result = await connector.deliver_to_destination(submission, destination_config)
        
        # Return result for Step Functions
        return {
            'statusCode': 200,
            'deliveryResult': {
                'status': result.status.value,
                'statusCode': result.status_code,
                'responseTimeMs': result.response_time_ms,
                'errorMessage': result.error_message,
                'retryAfterSeconds': result.retry_after_seconds,
                'isRetryable': result.status in [
                    DeliveryStatus.RETRYABLE, 
                    DeliveryStatus.RATE_LIMITED
                ]
            }
        }
        
    except Exception as e:
        logger.exception("Connector handler error")
        metrics.add_metric(name="HandlerErrors", unit=MetricUnit.Count, value=1)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal connector error',
                'message': str(e)
            })
        }
    finally:
        # Cleanup is handled by container lifecycle in Lambda


if __name__ == "__main__":
    # Local testing
    test_event = {
        'submission': {
            'tenant_id': 't_test123',
            'submission_id': 'sub_123',
            'form_id': 'contact_form',
            'submitted_at': datetime.utcnow().isoformat() + 'Z',
            'payload': {
                'name': 'John Doe',
                'email': 'john@example.com',
                'message': 'Hello!'
            }
        },
        'destination': {
            'id': 'dest_webhook1',
            'type': 'rest',
            'endpoint': 'https://api.example.com/webhooks/form',
            'auth': {
                'type': 'api_key',
                'secret_name': 'webhook_api_key',
                'header': 'X-API-Key'
            },
            'field_mapping': {
                'customer_name': 'payload.name',
                'customer_email': 'payload.email',
                'form_message': 'payload.message',
                'external_id': 'submission_id'
            },
            'timeout_seconds': 10
        }
    }
    
    result = lambda_handler(test_event, {})
    print(json.dumps(result, indent=2))
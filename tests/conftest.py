"""
Global pytest configuration and fixtures for Form-Bridge testing
Multi-tenant testing with complete data isolation
"""

import os
import json
import time
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Dict, List, Any, Generator
from uuid import uuid4
from dataclasses import dataclass

import pytest
import boto3
from moto import mock_dynamodb2 as mock_dynamodb, mock_events, mock_lambda, mock_apigateway, mock_secretsmanager
import requests
from unittest.mock import Mock, patch

# LocalStack configuration
LOCALSTACK_ENDPOINT = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

# fake = Faker()  # Removed for Phase 0


@dataclass
class TenantConfig:
    """Configuration for a test tenant"""
    tenant_id: str
    name: str
    api_key: str
    secret_key: str
    dynamodb_prefix: str
    secrets_key: str
    config: Dict[str, Any]
    created_at: datetime
    

@dataclass
class FormSubmission:
    """Test form submission data"""
    submission_id: str
    tenant_id: str
    form_id: str
    submitted_at: datetime
    payload: Dict[str, Any]
    metadata: Dict[str, Any]


class TenantFactory:
    """Factory for creating isolated tenant test data"""
    
    def __init__(self):
        self._created_tenants = []
    
    def create_tenant(self, tenant_id: str = None, config: Dict[str, Any] = None) -> TenantConfig:
        """Create a new test tenant with isolated configuration"""
        if not tenant_id:
            tenant_id = f"test_tenant_{uuid4().hex[:8]}"
        
        tenant_config = TenantConfig(
            tenant_id=f"t_{tenant_id}",
            name=f"Test Tenant {tenant_id}",
            api_key=f"api_key_{uuid4().hex}",
            secret_key=f"secret_key_{uuid4().hex}",
            dynamodb_prefix=f"TENANT#{tenant_id}",
            secrets_key=f"formbridge/tenants/{tenant_id}",
            config=config or self._get_default_tenant_config(),
            created_at=datetime.now(timezone.utc)
        )
        
        self._created_tenants.append(tenant_config)
        return tenant_config
    
    def _get_default_tenant_config(self) -> Dict[str, Any]:
        """Default tenant configuration"""
        return {
            "rate_limit": {
                "requests_per_minute": 100,
                "burst_limit": 10
            },
            "destinations": [
                {
                    "id": "default_webhook",
                    "type": "webhook",
                    "url": "https://httpbin.org/post",
                    "enabled": True
                }
            ],
            "retention_days": 30,
            "features": {
                "wordpress_plugin": True,
                "webhook_delivery": True,
                "analytics": True
            }
        }
    
    def cleanup(self):
        """Cleanup all created tenants"""
        self._created_tenants.clear()


class HMACSignatureHelper:
    """Helper for generating and validating HMAC signatures"""
    
    @staticmethod
    def generate_signature(secret_key: str, timestamp: str, body: str) -> str:
        """Generate HMAC-SHA256 signature for request"""
        message = f"{timestamp}\n{body}"
        signature = hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    @staticmethod
    def create_valid_request_headers(tenant_config: TenantConfig, body: str) -> Dict[str, str]:
        """Create valid request headers with HMAC signature"""
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        signature = HMACSignatureHelper.generate_signature(
            tenant_config.secret_key, 
            timestamp, 
            body
        )
        
        return {
            'Content-Type': 'application/json',
            'X-Tenant-ID': tenant_config.tenant_id,
            'X-Timestamp': timestamp,
            'X-Signature': signature,
            'User-Agent': 'Form-Bridge-Test/1.0'
        }


class MultiTenantTestEnvironment:
    """Complete multi-tenant test environment with data isolation"""
    
    def __init__(self, tenant_count: int = 3):
        self.tenant_factory = TenantFactory()
        self.tenants = []
        self.dynamodb_tables = {}
        self.secrets = {}
        
        # Create test tenants
        for i in range(tenant_count):
            tenant = self.tenant_factory.create_tenant(f"test_{i+1}")
            self.tenants.append(tenant)
    
    def setup_tenant_data(self, dynamodb_resource):
        """Setup isolated test data for each tenant"""
        for tenant in self.tenants:
            # Create tenant-specific test data
            self._create_tenant_submissions(tenant, dynamodb_resource)
            self._store_tenant_secrets(tenant)
    
    def _create_tenant_submissions(self, tenant: TenantConfig, dynamodb_resource):
        """Create sample form submissions for tenant"""
        table = dynamodb_resource.Table('formbridge-test')
        
        for i in range(5):  # Create 5 test submissions per tenant
            submission = FormSubmission(
                submission_id=f"sub_{uuid4().hex[:16]}",
                tenant_id=tenant.tenant_id,
                form_id=f"contact_form_{i}",
                submitted_at=datetime.now(timezone.utc),
                payload={
                    "name": "Test User",
                    "email": "test@example.com",
                    "message": "This is a test message"
                },
                metadata={
                    "source_ip": "192.168.1.100",
                    "user_agent": "Test-Agent/1.0",
                    "form_version": "1.0"
                }
            )
            
            # Store with tenant prefix for complete isolation
            table.put_item(Item={
                'PK': f'{tenant.dynamodb_prefix}#SUBMISSION#{submission.submission_id}',
                'SK': f'META#{submission.submitted_at.isoformat()}',
                'tenant_id': submission.tenant_id,
                'submission_id': submission.submission_id,
                'form_id': submission.form_id,
                'submitted_at': submission.submitted_at.isoformat(),
                'payload': submission.payload,
                'metadata': submission.metadata,
                'GSI1PK': f'{tenant.tenant_id}#FORM#{submission.form_id}',
                'GSI1SK': submission.submitted_at.isoformat(),
                'ttl': int(time.time()) + (30 * 24 * 60 * 60)  # 30 days TTL
            })
    
    def _store_tenant_secrets(self, tenant: TenantConfig):
        """Store tenant secrets in mock Secrets Manager"""
        # This would be implemented with mock_secretsmanager
        self.secrets[tenant.secrets_key] = {
            'api_key': tenant.api_key,
            'secret_key': tenant.secret_key,
            'config': tenant.config
        }
    
    def cleanup_tenant_data(self, dynamodb_resource):
        """Cleanup all tenant data"""
        table = dynamodb_resource.Table('formbridge-test')
        
        # Delete all tenant data
        for tenant in self.tenants:
            # Scan and delete all items with tenant prefix
            response = table.scan(
                FilterExpression='begins_with(PK, :prefix)',
                ExpressionAttributeValues={':prefix': tenant.dynamodb_prefix}
            )
            
            for item in response.get('Items', []):
                table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']}
                )
        
        self.tenant_factory.cleanup()
    
    def verify_tenant_isolation(self, dynamodb_resource) -> bool:
        """Verify complete tenant data isolation"""
        table = dynamodb_resource.Table('formbridge-test')
        
        for tenant in self.tenants:
            # Get tenant data
            tenant_items = table.scan(
                FilterExpression='begins_with(PK, :prefix)',
                ExpressionAttributeValues={':prefix': tenant.dynamodb_prefix}
            )['Items']
            
            # Verify no cross-tenant contamination
            for item in tenant_items:
                if not item['PK'].startswith(tenant.dynamodb_prefix):
                    return False
                if item.get('tenant_id') != tenant.tenant_id:
                    return False
        
        return True


# Global fixtures
@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing"""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = AWS_REGION


@pytest.fixture(scope="session")
def localstack_config():
    """LocalStack configuration"""
    return {
        'endpoint_url': LOCALSTACK_ENDPOINT,
        'region_name': AWS_REGION,
        'aws_access_key_id': 'test',
        'aws_secret_access_key': 'test'
    }


@pytest.fixture
def dynamodb_resource(localstack_config):
    """DynamoDB resource with test table"""
    dynamodb = boto3.resource('dynamodb', **localstack_config)
    
    # Create test table
    table_name = 'formbridge-test'
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Wait for table to be active
        table.wait_until_exists()
        
    except Exception as e:
        # Table might already exist
        table = dynamodb.Table(table_name)
    
    yield table
    
    # Cleanup
    try:
        table.delete()
    except Exception:
        pass  # Table might not exist


@pytest.fixture
def eventbridge_client(localstack_config):
    """EventBridge client for testing"""
    client = boto3.client('events', **localstack_config)
    
    # Create test event bus
    event_bus_name = 'formbridge-test-bus'
    try:
        client.create_event_bus(Name=event_bus_name)
    except Exception:
        pass  # Bus might already exist
    
    yield client
    
    # Cleanup
    try:
        client.delete_event_bus(Name=event_bus_name)
    except Exception:
        pass


@pytest.fixture
def tenant_factory():
    """Tenant factory for creating test tenants"""
    factory = TenantFactory()
    yield factory
    factory.cleanup()


@pytest.fixture
def multi_tenant_test_env():
    """Multi-tenant test environment with complete data isolation"""
    env = MultiTenantTestEnvironment(tenant_count=3)
    yield env


@pytest.fixture
def hmac_helper():
    """HMAC signature helper for authentication tests"""
    return HMACSignatureHelper()


@pytest.fixture
def sample_form_submission():
    """Sample form submission for testing"""
    return {
        "form_id": "contact_form",
        "payload": {
            "name": "Test User",
            "email": "test@example.com",
            "subject": "Test Subject",
            "message": "This is a test message for form submission"
        },
        "metadata": {
            "source_ip": "192.168.1.100",
            "user_agent": "Test-Agent/1.0",
            "referrer": "https://example.com",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test"""
    # Ensure clean state
    if 'PYTEST_CURRENT_TEST' in os.environ:
        # Running in pytest
        yield
    else:
        yield


# Test data generators
def generate_hmac_test_cases():
    """Generate comprehensive HMAC test cases for 100% edge case coverage"""
    base_cases = [
        # Valid cases
        {"name": "valid_signature", "valid": True},
        
        # Invalid timestamp cases
        {"name": "missing_timestamp", "timestamp": None, "valid": False},
        {"name": "empty_timestamp", "timestamp": "", "valid": False},
        {"name": "invalid_timestamp_format", "timestamp": "invalid", "valid": False},
        {"name": "future_timestamp", "timestamp": "2030-01-01T00:00:00Z", "valid": False},
        {"name": "past_timestamp", "timestamp": "2020-01-01T00:00:00Z", "valid": False},
        
        # Invalid body cases
        {"name": "empty_body", "body": "", "valid": False},
        {"name": "missing_body", "body": None, "valid": False},
        {"name": "large_body", "body": "x" * 10000, "valid": True},  # Should work but test limits
        
        # Invalid signature cases
        {"name": "missing_signature", "signature": None, "valid": False},
        {"name": "empty_signature", "signature": "", "valid": False},
        {"name": "invalid_signature", "signature": "invalid_signature", "valid": False},
        {"name": "wrong_algorithm", "signature": "md5_signature", "valid": False},
        
        # Replay attack cases
        {"name": "replayed_request", "replay": True, "valid": False},
        
        # Timing attack cases
        {"name": "timing_attack", "timing_attack": True, "valid": False},
        
        # Encoding cases
        {"name": "utf8_body", "body": '{"message": "Hello 世界"}', "valid": True},
        {"name": "special_chars", "body": '{"data": "!@#$%^&*()"}', "valid": True},
    ]
    
    return base_cases


# Performance testing utilities
@pytest.fixture
def performance_baseline():
    """Performance baseline for regression testing"""
    return {
        "hmac_validation_ms": 5.0,
        "dynamodb_write_ms": 10.0,
        "eventbridge_publish_ms": 15.0,
        "lambda_cold_start_ms": 1000.0,
        "lambda_warm_start_ms": 50.0
    }


@pytest.fixture
def load_test_config():
    """Configuration for load testing"""
    return {
        "target_rps": int(os.getenv('LOAD_TEST_TARGET_RPS', 100)),
        "duration_seconds": int(os.getenv('LOAD_TEST_DURATION', 300)),
        "concurrent_tenants": 10,
        "submissions_per_tenant": 1000
    }


# Security testing fixtures
@pytest.fixture
def security_test_config():
    """Configuration for security testing"""
    return {
        "vulnerability_threshold": os.getenv('VULNERABILITY_THRESHOLD', 'high'),
        "scan_paths": ['lambdas/', 'scripts/', 'tests/'],
        "exclude_patterns": ['*.pyc', '__pycache__', '.git'],
        "required_security_headers": [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security'
        ]
    }
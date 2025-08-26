"""
Simplified pytest configuration for Form-Bridge Phase 0
Basic testing setup without complex dependencies
"""

import os
import pytest


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing"""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


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
        }
    }


@pytest.fixture
def tenant_config():
    """Basic tenant configuration for testing"""
    return {
        "tenant_id": "test_tenant_1",
        "name": "Test Tenant 1",
        "api_key": "test_api_key_123",
        "secret_key": "test_secret_key_456"
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup clean test environment"""
    yield


# Performance baseline for testing
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
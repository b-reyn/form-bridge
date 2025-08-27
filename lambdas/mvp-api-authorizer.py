"""
MVP API Authorizer  
Simple API key validation for quick deployment
No HMAC complexity, just basic tenant validation
"""
import json
import os
from datetime import datetime, timezone
import boto3

# Initialize AWS clients
secrets_client = boto3.client('secretsmanager')

# Configuration
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
SECRET_PREFIX = os.environ.get('SECRET_PREFIX', 'formbridge/tenants')

def lambda_handler(event, context):
    """
    Simple API Key Authorizer for MVP
    - Validates tenant exists in Secrets Manager
    - Basic API key check
    - Fast deployment, no complex HMAC
    """
    print(f"Authorizer invoked for: {event.get('methodArn', 'unknown')}")
    
    try:
        # Extract headers (case-insensitive)
        headers = event.get('headers', {})
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        # Get tenant ID and API key
        tenant_id = headers_lower.get('x-tenant-id')
        api_key = headers_lower.get('x-api-key')
        
        if not tenant_id:
            print("Missing X-Tenant-ID header")
            return generate_deny_policy(event.get('methodArn', ''), "Missing tenant ID")
        
        if not api_key:
            print("Missing X-API-Key header") 
            return generate_deny_policy(event.get('methodArn', ''), "Missing API key")
        
        # Validate tenant and API key
        if validate_tenant_api_key(tenant_id, api_key):
            print(f"Authorization successful for tenant: {tenant_id}")
            return generate_allow_policy(
                event.get('methodArn', ''),
                tenant_id,
                {'tenant_id': tenant_id, 'auth_method': 'api_key'}
            )
        else:
            print(f"Authorization failed for tenant: {tenant_id}")
            return generate_deny_policy(event.get('methodArn', ''), "Invalid credentials")
    
    except Exception as e:
        print(f"Authorizer error: {str(e)}")
        return generate_deny_policy(event.get('methodArn', ''), "Internal error")

def validate_tenant_api_key(tenant_id, provided_api_key):
    """
    Validate tenant API key from Secrets Manager
    Simple validation for MVP - enhance later
    """
    try:
        # Get tenant secret
        secret_name = f"{SECRET_PREFIX}/{tenant_id}"
        
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response['SecretString'])
        
        # Simple API key comparison
        stored_api_key = secret_data.get('api_key')
        if not stored_api_key:
            print(f"No API key found for tenant {tenant_id}")
            return False
        
        # Basic string comparison (enhance with constant-time later)
        return stored_api_key == provided_api_key
        
    except secrets_client.exceptions.ResourceNotFoundException:
        print(f"Tenant {tenant_id} not found in Secrets Manager")
        return False
    except Exception as e:
        print(f"Error validating tenant {tenant_id}: {str(e)}")
        return False

def generate_allow_policy(method_arn, tenant_id, context):
    """Generate IAM allow policy with tenant context"""
    return {
        'principalId': tenant_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': 'Allow',
                'Resource': method_arn
            }]
        },
        'context': {
            'tenant_id': tenant_id,
            'auth_method': context.get('auth_method', 'api_key'),
            'authorized_at': datetime.now(timezone.utc).isoformat()
        }
    }

def generate_deny_policy(method_arn, reason="Unauthorized"):
    """Generate IAM deny policy"""
    return {
        'principalId': 'unauthorized',
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': 'Deny',
                'Resource': method_arn
            }]
        },
        'context': {
            'error': reason,
            'denied_at': datetime.now(timezone.utc).isoformat()
        }
    }
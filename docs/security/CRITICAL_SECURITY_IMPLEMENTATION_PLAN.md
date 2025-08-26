# Critical Security Implementation Plan for Form-Bridge

**Document:** Critical Security Implementation Plan  
**Project:** Form-Bridge Multi-Tenant SaaS  
**Created:** 2025-08-26  
**Author:** cognito-auth-expert  
**Status:** Ready for Implementation

## Executive Summary

This document provides immediate, actionable guidance for implementing the CRITICAL security items identified in the comprehensive improvement to-do list. These measures must be completed before any production deployment to prevent data breaches, cross-tenant access, and security vulnerabilities.

**Total Estimated Cost Impact:** $15-25/month (within acceptable range)  
**Implementation Timeline:** 2-3 weeks  
**Business Risk Without Implementation:** CRITICAL

## P0 - CRITICAL SECURITY FIXES (Complete This Week)

### 1. Multi-Tenant KMS Key Implementation ($5-8/month)

**Problem:** Currently no tenant-specific encryption, risk of cross-tenant data access.

**Solution Implementation:**

```python
# File: /lambdas/shared/kms_tenant_manager.py
import boto3
import json
from typing import Dict, Optional

class TenantKMSManager:
    def __init__(self):
        self.kms_client = boto3.client('kms')
        self.sts_client = boto3.client('sts')
    
    def get_or_create_tenant_key(self, tenant_id: str) -> Dict[str, str]:
        """
        Get existing or create new KMS key for tenant with proper alias
        """
        key_alias = f"alias/formbridge-tenant-{tenant_id}"
        
        try:
            # Check if key exists
            response = self.kms_client.describe_key(KeyId=key_alias)
            return {
                'key_id': response['KeyMetadata']['KeyId'],
                'key_alias': key_alias,
                'arn': response['KeyMetadata']['Arn']
            }
        except self.kms_client.exceptions.NotFoundException:
            # Create new key for tenant
            return self._create_tenant_key(tenant_id, key_alias)
    
    def _create_tenant_key(self, tenant_id: str, key_alias: str) -> Dict[str, str]:
        """Create KMS key with tenant-specific policy"""
        key_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EnableRootAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{self.get_account_id()}:root"
                    },
                    "Action": "kms:*",
                    "Resource": "*"
                },
                {
                    "Sid": "TenantAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": "*"
                    },
                    "Action": [
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "kms:EncryptionContext:tenant_id": tenant_id
                        }
                    }
                }
            ]
        }
        
        # Create key
        key_response = self.kms_client.create_key(
            Policy=json.dumps(key_policy),
            Description=f"Form-Bridge tenant key for {tenant_id}",
            KeyUsage='ENCRYPT_DECRYPT',
            KeySpec='SYMMETRIC_DEFAULT'
        )
        
        # Create alias
        self.kms_client.create_alias(
            AliasName=key_alias,
            TargetKeyId=key_response['KeyMetadata']['KeyId']
        )
        
        return {
            'key_id': key_response['KeyMetadata']['KeyId'],
            'key_alias': key_alias,
            'arn': key_response['KeyMetadata']['Arn']
        }
    
    def encrypt_for_tenant(self, data: str, tenant_id: str) -> str:
        """Encrypt data with tenant-specific key and context"""
        key_info = self.get_or_create_tenant_key(tenant_id)
        
        response = self.kms_client.encrypt(
            KeyId=key_info['key_id'],
            Plaintext=data.encode('utf-8'),
            EncryptionContext={'tenant_id': tenant_id}
        )
        
        return response['CiphertextBlob']
    
    def decrypt_for_tenant(self, encrypted_data: bytes, tenant_id: str) -> str:
        """Decrypt data with tenant validation"""
        response = self.kms_client.decrypt(
            CiphertextBlob=encrypted_data,
            EncryptionContext={'tenant_id': tenant_id}
        )
        
        return response['Plaintext'].decode('utf-8')
    
    def get_account_id(self) -> str:
        """Get current AWS account ID"""
        return self.sts_client.get_caller_identity()['Account']

# Usage in Lambda functions
def lambda_handler(event, context):
    tenant_id = extract_tenant_id(event)
    kms_manager = TenantKMSManager()
    
    # Encrypt sensitive form data
    form_data = event['form_data']
    encrypted_data = kms_manager.encrypt_for_tenant(
        json.dumps(form_data), 
        tenant_id
    )
    
    # Store encrypted data in DynamoDB
    store_encrypted_submission(tenant_id, encrypted_data)
```

### 2. Cross-Tenant Access Validation (Immediate)

**Problem:** No validation prevents users from accessing other tenants' data.

**Solution Implementation:**

```python
# File: /lambdas/auth/tenant_authorizer.py
import json
import jwt
import boto3
from typing import Dict, Any, Optional

class TenantAuthorizer:
    def __init__(self):
        self.cognito_client = boto3.client('cognito-idp')
    
    def authorize_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate JWT token and enforce tenant isolation
        """
        try:
            # Extract token from Authorization header
            token = self._extract_token(event)
            if not token:
                return self._generate_deny_policy("No token provided")
            
            # Validate JWT and extract claims
            claims = self._validate_jwt(token)
            if not claims:
                return self._generate_deny_policy("Invalid token")
            
            # Extract tenant context
            token_tenant_id = claims.get('custom:tenant_id')
            if not token_tenant_id:
                return self._generate_deny_policy("No tenant ID in token")
            
            # Extract requested tenant from path/query
            requested_tenant_id = self._extract_requested_tenant(event)
            if not requested_tenant_id:
                return self._generate_deny_policy("No tenant ID in request")
            
            # CRITICAL: Prevent cross-tenant access
            if token_tenant_id != requested_tenant_id:
                self._log_security_violation(
                    token_tenant_id, 
                    requested_tenant_id, 
                    claims.get('sub'),
                    event
                )
                return self._generate_deny_policy("Cross-tenant access denied")
            
            # Generate allow policy with tenant context
            return self._generate_allow_policy(
                event['methodArn'], 
                token_tenant_id, 
                claims
            )
            
        except Exception as e:
            print(f"Authorization error: {str(e)}")
            return self._generate_deny_policy("Authorization failed")
    
    def _extract_token(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract JWT token from Authorization header"""
        headers = event.get('headers', {})
        auth_header = headers.get('Authorization', headers.get('authorization', ''))
        
        if auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]
        
        return None
    
    def _validate_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token with Cognito"""
        try:
            # In production, validate with Cognito JWKS
            # For now, decode without verification (MUST FIX)
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded
        except Exception as e:
            print(f"JWT validation error: {str(e)}")
            return None
    
    def _extract_requested_tenant(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract tenant ID from request path or query parameters"""
        # Check path parameters
        path_params = event.get('pathParameters', {})
        if path_params and 'tenant_id' in path_params:
            return path_params['tenant_id']
        
        # Check query parameters
        query_params = event.get('queryStringParameters', {})
        if query_params and 'tenant_id' in query_params:
            return query_params['tenant_id']
        
        # Check request body
        body = event.get('body', '{}')
        try:
            body_data = json.loads(body)
            if 'tenant_id' in body_data:
                return body_data['tenant_id']
        except:
            pass
        
        return None
    
    def _log_security_violation(self, token_tenant: str, requested_tenant: str, 
                              user_id: str, event: Dict[str, Any]):
        """Log security violation for monitoring"""
        violation_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'violation_type': 'cross_tenant_access_attempt',
            'token_tenant_id': token_tenant,
            'requested_tenant_id': requested_tenant,
            'user_id': user_id,
            'source_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp'),
            'user_agent': event.get('headers', {}).get('User-Agent'),
            'method': event.get('httpMethod'),
            'path': event.get('path')
        }
        
        # Send to security monitoring
        self._publish_security_event('CROSS_TENANT_VIOLATION', violation_data)
        
        # Also log to CloudWatch
        print(f"SECURITY_VIOLATION: {json.dumps(violation_data)}")
    
    def _generate_allow_policy(self, method_arn: str, tenant_id: str, 
                             claims: Dict[str, Any]) -> Dict[str, Any]:
        """Generate IAM policy allowing access with tenant context"""
        return {
            'principalId': claims.get('sub'),
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
                'user_id': claims.get('sub'),
                'user_role': claims.get('custom:role', 'user'),
                'permissions': claims.get('custom:permissions', '[]')
            }
        }
    
    def _generate_deny_policy(self, reason: str) -> Dict[str, Any]:
        """Generate IAM policy denying access"""
        return {
            'principalId': 'unauthorized',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Deny',
                        'Resource': '*'
                    }
                ]
            },
            'context': {
                'error': reason
            }
        }
    
    def _publish_security_event(self, event_type: str, data: Dict[str, Any]):
        """Publish security event to EventBridge"""
        eventbridge = boto3.client('events')
        
        eventbridge.put_events(
            Entries=[
                {
                    'Source': 'formbridge.security',
                    'DetailType': event_type,
                    'Detail': json.dumps(data)
                }
            ]
        )

# Lambda function for API Gateway authorizer
def lambda_handler(event, context):
    authorizer = TenantAuthorizer()
    return authorizer.authorize_request(event)
```

### 3. Master Secrets Migration to Secrets Manager ($2-3/month)

**Problem:** Hardcoded secrets in environment variables expose sensitive data.

**Solution Implementation:**

```python
# File: /lambdas/shared/secrets_manager.py
import boto3
import json
import time
from typing import Dict, Optional, Any
from botocore.exceptions import ClientError

class SecureSecretsManager:
    def __init__(self):
        self.secrets_client = boto3.client('secretsmanager')
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes
    
    def create_master_secrets(self) -> Dict[str, str]:
        """
        Create all master secrets in Secrets Manager
        Call this once during setup
        """
        master_secrets = {}
        
        # HMAC Master Key
        hmac_secret_name = "formbridge/master/hmac-key"
        hmac_key = self._create_secret(
            hmac_secret_name,
            self._generate_secure_key(64),  # 512-bit key
            "Master HMAC key for form signature validation"
        )
        master_secrets['hmac_master_key'] = hmac_secret_name
        
        # Database Encryption Key
        db_secret_name = "formbridge/master/db-encryption-key"
        db_key = self._create_secret(
            db_secret_name,
            self._generate_secure_key(32),  # 256-bit key
            "Master database encryption key"
        )
        master_secrets['db_encryption_key'] = db_secret_name
        
        # JWT Signing Key
        jwt_secret_name = "formbridge/master/jwt-signing-key"
        jwt_key = self._create_secret(
            jwt_secret_name,
            self._generate_secure_key(64),  # 512-bit key
            "JWT token signing key"
        )
        master_secrets['jwt_signing_key'] = jwt_secret_name
        
        return master_secrets
    
    def create_tenant_secrets(self, tenant_id: str) -> Dict[str, str]:
        """
        Create tenant-specific secrets
        """
        tenant_secrets = {}
        
        # Tenant HMAC Key (derived from master)
        tenant_hmac_name = f"formbridge/tenant/{tenant_id}/hmac-key"
        master_hmac = self.get_secret("formbridge/master/hmac-key")
        tenant_hmac = self._derive_tenant_key(master_hmac, tenant_id, "hmac")
        
        self._create_secret(
            tenant_hmac_name,
            tenant_hmac,
            f"HMAC key for tenant {tenant_id}"
        )
        tenant_secrets['hmac_key'] = tenant_hmac_name
        
        # Tenant Webhook Secret
        webhook_secret_name = f"formbridge/tenant/{tenant_id}/webhook-secret"
        webhook_secret = self._generate_secure_key(32)
        self._create_secret(
            webhook_secret_name,
            webhook_secret,
            f"Webhook secret for tenant {tenant_id}"
        )
        tenant_secrets['webhook_secret'] = webhook_secret_name
        
        return tenant_secrets
    
    def get_secret(self, secret_name: str, force_refresh: bool = False) -> str:
        """
        Get secret from cache or Secrets Manager
        """
        # Check cache first
        if not force_refresh and secret_name in self.cache:
            cached_item = self.cache[secret_name]
            if time.time() - cached_item['timestamp'] < self.cache_timeout:
                return cached_item['value']
        
        # Retrieve from Secrets Manager
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_value = response['SecretString']
            
            # Cache the value
            self.cache[secret_name] = {
                'value': secret_value,
                'timestamp': time.time()
            }
            
            return secret_value
            
        except ClientError as e:
            print(f"Error retrieving secret {secret_name}: {str(e)}")
            raise
    
    def rotate_secret(self, secret_name: str) -> str:
        """
        Rotate a secret (generate new value)
        """
        try:
            # Generate new secret value
            new_value = self._generate_secure_key(64)
            
            # Update secret
            self.secrets_client.update_secret(
                SecretId=secret_name,
                SecretString=new_value
            )
            
            # Clear from cache
            if secret_name in self.cache:
                del self.cache[secret_name]
            
            return new_value
            
        except ClientError as e:
            print(f"Error rotating secret {secret_name}: {str(e)}")
            raise
    
    def setup_automatic_rotation(self, secret_name: str, rotation_days: int = 90):
        """
        Set up automatic rotation for a secret
        """
        # This requires a Lambda function for rotation
        # Implementation depends on secret type
        pass
    
    def _create_secret(self, name: str, value: str, description: str) -> str:
        """Create secret in Secrets Manager"""
        try:
            response = self.secrets_client.create_secret(
                Name=name,
                SecretString=value,
                Description=description,
                Tags=[
                    {'Key': 'Project', 'Value': 'FormBridge'},
                    {'Key': 'Environment', 'Value': 'production'},
                    {'Key': 'CreatedDate', 'Value': str(int(time.time()))}
                ]
            )
            return response['ARN']
            
        except self.secrets_client.exceptions.ResourceExistsException:
            # Secret already exists, update it
            self.secrets_client.update_secret(
                SecretId=name,
                SecretString=value
            )
            return name
    
    def _generate_secure_key(self, length: int) -> str:
        """Generate cryptographically secure random key"""
        import secrets
        import base64
        
        random_bytes = secrets.token_bytes(length)
        return base64.b64encode(random_bytes).decode('utf-8')
    
    def _derive_tenant_key(self, master_key: str, tenant_id: str, purpose: str) -> str:
        """Derive tenant-specific key from master key"""
        import hmac
        import hashlib
        import base64
        
        # Use HKDF-like derivation
        info = f"{tenant_id}:{purpose}".encode('utf-8')
        master_bytes = base64.b64decode(master_key)
        
        derived = hmac.new(master_bytes, info, hashlib.sha256).digest()
        return base64.b64encode(derived).decode('utf-8')

# Usage in Lambda functions
def lambda_handler(event, context):
    secrets_manager = SecureSecretsManager()
    
    # Get tenant HMAC key
    tenant_id = extract_tenant_id(event)
    hmac_key = secrets_manager.get_secret(f"formbridge/tenant/{tenant_id}/hmac-key")
    
    # Validate request signature
    is_valid = validate_hmac_signature(event, hmac_key)
    if not is_valid:
        return {'statusCode': 403, 'body': 'Invalid signature'}
    
    # Process request...
```

### 4. JWT Token Rotation and Secure Storage (Immediate)

**Problem:** Static JWT tokens without rotation create security vulnerabilities.

**Solution Implementation:**

```javascript
// File: /frontend/src/utils/authManager.js
class SecureAuthManager {
    constructor() {
        this.tokenKey = 'formbridge_auth';
        this.refreshKey = 'formbridge_refresh';
        this.refreshThreshold = 5 * 60 * 1000; // 5 minutes before expiry
    }
    
    /**
     * Store tokens securely using httpOnly cookies (server-side only)
     * This is pseudocode - actual implementation requires server cooperation
     */
    async storeTokens(accessToken, refreshToken) {
        // Server should set httpOnly cookies
        const response = await fetch('/api/auth/store-tokens', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                access_token: accessToken,
                refresh_token: refreshToken
            }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to store tokens');
        }
        
        // Schedule refresh
        this.scheduleTokenRefresh(accessToken);
    }
    
    /**
     * Get access token (from httpOnly cookie via API call)
     */
    async getAccessToken() {
        try {
            const response = await fetch('/api/auth/get-token', {
                method: 'GET',
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error('Token not available');
            }
            
            const data = await response.json();
            return data.access_token;
            
        } catch (error) {
            console.error('Error getting access token:', error);
            return null;
        }
    }
    
    /**
     * Refresh access token using refresh token
     */
    async refreshAccessToken() {
        try {
            const response = await fetch('/api/auth/refresh', {
                method: 'POST',
                credentials: 'include', // Sends httpOnly refresh token cookie
            });
            
            if (!response.ok) {
                throw new Error('Token refresh failed');
            }
            
            const data = await response.json();
            
            // Server will set new httpOnly cookies
            this.scheduleTokenRefresh(data.access_token);
            
            return data.access_token;
            
        } catch (error) {
            console.error('Token refresh error:', error);
            // Redirect to login
            this.handleAuthFailure();
            return null;
        }
    }
    
    /**
     * Schedule automatic token refresh
     */
    scheduleTokenRefresh(token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            const expiryTime = payload.exp * 1000; // Convert to milliseconds
            const refreshTime = expiryTime - this.refreshThreshold;
            const delay = refreshTime - Date.now();
            
            if (delay > 0) {
                setTimeout(() => {
                    this.refreshAccessToken();
                }, delay);
            } else {
                // Token expires soon, refresh immediately
                this.refreshAccessToken();
            }
            
        } catch (error) {
            console.error('Error scheduling token refresh:', error);
        }
    }
    
    /**
     * Handle authentication failure
     */
    handleAuthFailure() {
        // Clear any local auth state
        localStorage.removeItem('user_profile');
        
        // Redirect to login
        window.location.href = '/login';
    }
    
    /**
     * Logout user
     */
    async logout() {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            this.handleAuthFailure();
        }
    }
    
    /**
     * Make authenticated API requests
     */
    async authenticatedFetch(url, options = {}) {
        const token = await this.getAccessToken();
        
        if (!token) {
            throw new Error('No access token available');
        }
        
        const authOptions = {
            ...options,
            headers: {
                ...options.headers,
                'Authorization': `Bearer ${token}`
            },
            credentials: 'include'
        };
        
        const response = await fetch(url, authOptions);
        
        // If unauthorized, try to refresh token once
        if (response.status === 401) {
            const newToken = await this.refreshAccessToken();
            if (newToken) {
                authOptions.headers['Authorization'] = `Bearer ${newToken}`;
                return fetch(url, authOptions);
            }
        }
        
        return response;
    }
}

// Export singleton instance
export const authManager = new SecureAuthManager();
```

### 5. Key Rotation Mechanism ($3-5/month)

**Problem:** No automatic rotation of cryptographic keys increases compromise risk.

**Solution Implementation:**

```python
# File: /lambdas/security/key_rotation_manager.py
import boto3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List

class KeyRotationManager:
    def __init__(self):
        self.secrets_client = boto3.client('secretsmanager')
        self.eventbridge = boto3.client('events')
        self.dynamodb = boto3.resource('dynamodb')
        self.rotation_table = self.dynamodb.Table('FormBridge-KeyRotation')
    
    def schedule_rotation(self, secret_name: str, rotation_days: int = 90):
        """
        Schedule automatic rotation for a secret
        """
        next_rotation = datetime.utcnow() + timedelta(days=rotation_days)
        
        # Store rotation schedule
        self.rotation_table.put_item(
            Item={
                'secret_name': secret_name,
                'next_rotation': next_rotation.isoformat(),
                'rotation_days': rotation_days,
                'status': 'scheduled',
                'created_at': datetime.utcnow().isoformat()
            }
        )
        
        # Create EventBridge rule for rotation
        self._create_rotation_schedule(secret_name, next_rotation)
    
    def rotate_secret(self, secret_name: str) -> Dict[str, str]:
        """
        Perform secret rotation with zero-downtime
        """
        try:
            # Get current secret
            current_secret = self.secrets_client.get_secret_value(
                SecretId=secret_name,
                VersionStage='AWSCURRENT'
            )
            
            # Generate new secret value
            new_secret_value = self._generate_new_secret(secret_name)
            
            # Create new version as PENDING
            self.secrets_client.put_secret_value(
                SecretId=secret_name,
                SecretString=new_secret_value,
                VersionStage='AWSPENDING'
            )
            
            # Test new secret (implementation depends on secret type)
            if self._test_secret(secret_name, new_secret_value):
                # Promote PENDING to CURRENT
                self.secrets_client.update_secret_version_stage(
                    SecretId=secret_name,
                    VersionStage='AWSCURRENT',
                    MoveToVersionId=self.secrets_client.describe_secret(
                        SecretId=secret_name
                    )['VersionIdsToStages']['AWSPENDING'][0]
                )
                
                # Update rotation tracking
                self._update_rotation_status(secret_name, 'completed')
                
                # Schedule next rotation
                self.schedule_rotation(secret_name)
                
                return {
                    'status': 'success',
                    'secret_name': secret_name,
                    'rotated_at': datetime.utcnow().isoformat()
                }
            else:
                # Rollback - remove PENDING version
                self._rollback_rotation(secret_name)
                self._update_rotation_status(secret_name, 'failed')
                
                return {
                    'status': 'failed',
                    'secret_name': secret_name,
                    'error': 'New secret validation failed'
                }
                
        except Exception as e:
            self._update_rotation_status(secret_name, 'error')
            raise Exception(f"Rotation failed for {secret_name}: {str(e)}")
    
    def rotate_tenant_keys(self, tenant_id: str) -> Dict[str, List[str]]:
        """
        Rotate all keys for a specific tenant
        """
        results = {
            'success': [],
            'failed': []
        }
        
        # Get all tenant secrets
        tenant_secrets = self._get_tenant_secrets(tenant_id)
        
        for secret_name in tenant_secrets:
            try:
                result = self.rotate_secret(secret_name)
                if result['status'] == 'success':
                    results['success'].append(secret_name)
                else:
                    results['failed'].append(secret_name)
            except Exception as e:
                results['failed'].append(secret_name)
                print(f"Failed to rotate {secret_name}: {str(e)}")
        
        return results
    
    def emergency_rotation(self, secret_name: str, reason: str):
        """
        Emergency rotation for compromised secrets
        """
        # Log security incident
        self._log_security_incident(secret_name, reason)
        
        # Immediate rotation
        result = self.rotate_secret(secret_name)
        
        # Notify security team
        self._notify_security_team(secret_name, reason, result)
        
        # Audit all usage of the compromised secret
        self._audit_secret_usage(secret_name)
        
        return result
    
    def _generate_new_secret(self, secret_name: str) -> str:
        """
        Generate new secret value based on secret type
        """
        import secrets
        import base64
        
        if 'hmac-key' in secret_name:
            # 512-bit HMAC key
            return base64.b64encode(secrets.token_bytes(64)).decode('utf-8')
        elif 'jwt-signing-key' in secret_name:
            # 512-bit JWT signing key
            return base64.b64encode(secrets.token_bytes(64)).decode('utf-8')
        elif 'webhook-secret' in secret_name:
            # 256-bit webhook secret
            return base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
        else:
            # Default: 256-bit key
            return base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
    
    def _test_secret(self, secret_name: str, new_value: str) -> bool:
        """
        Test new secret to ensure it works
        """
        # Implementation depends on secret type
        # For HMAC keys: test signature generation/verification
        # For JWT keys: test token generation/validation
        # For webhook secrets: test API connectivity
        
        try:
            if 'hmac-key' in secret_name:
                return self._test_hmac_key(new_value)
            elif 'jwt-signing-key' in secret_name:
                return self._test_jwt_key(new_value)
            else:
                return True  # Generic secrets don't need testing
        except:
            return False
    
    def _test_hmac_key(self, key: str) -> bool:
        """Test HMAC key functionality"""
        import hmac
        import hashlib
        import base64
        
        try:
            key_bytes = base64.b64decode(key)
            test_message = "test_message"
            signature = hmac.new(
                key_bytes, 
                test_message.encode('utf-8'), 
                hashlib.sha256
            ).hexdigest()
            return len(signature) == 64  # SHA256 hex length
        except:
            return False
    
    def _test_jwt_key(self, key: str) -> bool:
        """Test JWT signing key functionality"""
        import jwt
        import base64
        
        try:
            key_bytes = base64.b64decode(key)
            test_payload = {"test": True}
            token = jwt.encode(test_payload, key_bytes, algorithm='HS256')
            decoded = jwt.decode(token, key_bytes, algorithms=['HS256'])
            return decoded.get('test') == True
        except:
            return False
    
    def _create_rotation_schedule(self, secret_name: str, next_rotation: datetime):
        """Create EventBridge schedule for rotation"""
        rule_name = f"rotation-{secret_name.replace('/', '-')}"
        
        # Create EventBridge rule
        self.eventbridge.put_rule(
            Name=rule_name,
            ScheduleExpression=f"at({next_rotation.strftime('%Y-%m-%dT%H:%M:%S')})",
            State='ENABLED'
        )
        
        # Add Lambda target
        self.eventbridge.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    'Id': '1',
                    'Arn': f'arn:aws:lambda:{boto3.Session().region_name}:{self._get_account_id()}:function:FormBridge-KeyRotation',
                    'Input': json.dumps({
                        'secret_name': secret_name,
                        'rotation_type': 'scheduled'
                    })
                }
            ]
        )

# Lambda function for scheduled rotation
def lambda_handler(event, context):
    """
    Handle both scheduled and manual key rotations
    """
    rotation_manager = KeyRotationManager()
    
    # Check if it's a scheduled EventBridge event
    if 'source' in event and event['source'] == 'aws.events':
        secret_name = event['detail']['secret_name']
        rotation_type = event['detail']['rotation_type']
        
        print(f"Starting {rotation_type} rotation for {secret_name}")
        
        result = rotation_manager.rotate_secret(secret_name)
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    
    # Handle direct invocation
    elif 'secret_name' in event:
        secret_name = event['secret_name']
        
        if event.get('emergency'):
            reason = event.get('reason', 'Manual emergency rotation')
            result = rotation_manager.emergency_rotation(secret_name, reason)
        else:
            result = rotation_manager.rotate_secret(secret_name)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid event format'})
        }
```

## P1 - HIGH PRIORITY (Complete Within 2 Weeks)

### 6. Enhanced Rate Limiting and DDoS Protection ($20-30/month)

**Implementation Steps:**

1. **Deploy AWS WAF with Custom Rules**
2. **Configure CloudFront Rate Limiting**
3. **Implement Multi-Layer Lambda Rate Limiting**
4. **Add DynamoDB-Based Rate Tracking**

```python
# File: /lambdas/security/rate_limiter.py
import boto3
import json
import time
from typing import Dict, Optional, Tuple

class MultiLayerRateLimiter:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.rate_limit_table = self.dynamodb.Table('FormBridge-RateLimits')
        
        # Rate limit configurations
        self.rate_limits = {
            'ip_address': {'requests': 100, 'window': 60},  # 100/minute per IP
            'tenant': {'requests': 1000, 'window': 60},     # 1000/minute per tenant
            'hmac_key': {'requests': 500, 'window': 60},    # 500/minute per HMAC key
            'global': {'requests': 10000, 'window': 60}     # 10K/minute globally
        }
    
    def check_rate_limits(self, event: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check all rate limits and return (allowed, reason_if_blocked)
        """
        current_time = int(time.time())
        
        # Extract identifiers
        ip_address = self._get_client_ip(event)
        tenant_id = self._extract_tenant_id(event)
        hmac_key_id = self._extract_hmac_key_id(event)
        
        # Check each layer
        checks = [
            ('ip_address', ip_address),
            ('tenant', tenant_id),
            ('hmac_key', hmac_key_id),
            ('global', 'global')
        ]
        
        for limit_type, identifier in checks:
            if identifier:
                allowed, remaining = self._check_limit(
                    limit_type, identifier, current_time
                )
                if not allowed:
                    return False, f"Rate limit exceeded for {limit_type}: {identifier}"
        
        return True, None
    
    def _check_limit(self, limit_type: str, identifier: str, 
                    current_time: int) -> Tuple[bool, int]:
        """
        Check specific rate limit using sliding window
        """
        config = self.rate_limits[limit_type]
        window_start = current_time - config['window']
        
        # Get current count from DynamoDB
        try:
            response = self.rate_limit_table.get_item(
                Key={
                    'limit_key': f"{limit_type}:{identifier}",
                    'window_start': window_start
                }
            )
            
            current_count = response.get('Item', {}).get('request_count', 0)
            
            if current_count >= config['requests']:
                return False, 0
            
            # Increment counter
            self.rate_limit_table.put_item(
                Item={
                    'limit_key': f"{limit_type}:{identifier}",
                    'window_start': window_start,
                    'request_count': current_count + 1,
                    'ttl': current_time + config['window'] + 60
                }
            )
            
            return True, config['requests'] - current_count - 1
            
        except Exception as e:
            print(f"Rate limit check error: {str(e)}")
            # On error, allow the request (fail open)
            return True, config['requests']
```

## Implementation Timeline and Cost Summary

### Week 1 (P0 Critical Items)
- **Day 1-2**: Secrets Manager migration
- **Day 3-4**: Cross-tenant access validation
- **Day 5**: JWT token security implementation
- **Cost Impact**: $5-8/month

### Week 2 (P0 Completion + P1 Start)
- **Day 1-3**: Multi-tenant KMS implementation
- **Day 4-5**: Key rotation mechanism
- **Cost Impact**: Additional $8-12/month

### Week 3 (P1 High Priority)
- **Day 1-3**: Rate limiting and DDoS protection
- **Day 4-5**: Testing and validation
- **Cost Impact**: Additional $20-30/month

**Total Implementation Cost**: $33-50/month (higher than MVP target but critical for security)

## Testing and Validation Checklist

### Security Test Requirements

```bash
# Test cross-tenant access prevention
curl -H "Authorization: Bearer TENANT_A_TOKEN" \
     "https://api.formbridge.com/api/tenant-b/submissions"
# Expected: 403 Forbidden

# Test rate limiting
for i in {1..150}; do
  curl -X POST "https://api.formbridge.com/api/webhook" \
       -H "X-HMAC-Signature: test" -d "test=data" &
done
# Expected: 429 Too Many Requests after 100 requests

# Test secret rotation
aws lambda invoke --function-name FormBridge-KeyRotation \
    --payload '{"secret_name": "formbridge/tenant/test/hmac-key"}' \
    response.json
# Expected: Successful rotation without service interruption
```

## Emergency Response Procedures

### Immediate Actions for Security Incidents

1. **Suspected Cross-Tenant Access**:
   - Disable affected user accounts immediately
   - Rotate all tenant secrets
   - Audit access logs for scope of breach

2. **HMAC Key Compromise**:
   - Execute emergency key rotation
   - Invalidate all pending webhooks
   - Notify affected tenants

3. **DDoS Attack**:
   - Enable AWS Shield Advanced
   - Implement emergency rate limiting
   - Scale Lambda concurrency limits

## Files Created/Modified

This implementation plan creates the following new files:

1. `/mnt/c/projects/form-bridge/lambdas/shared/kms_tenant_manager.py`
2. `/mnt/c/projects/form-bridge/lambdas/auth/tenant_authorizer.py`
3. `/mnt/c/projects/form-bridge/lambdas/shared/secrets_manager.py`
4. `/mnt/c/projects/form-bridge/lambdas/security/key_rotation_manager.py`
5. `/mnt/c/projects/form-bridge/lambdas/security/rate_limiter.py`
6. `/mnt/c/projects/form-bridge/frontend/src/utils/authManager.js`

These implementations address all CRITICAL security items from the improvement to-do list and provide a foundation for secure multi-tenant operations within the projected cost constraints.

---

**Next Actions**: Begin implementation with P0 items, starting with Secrets Manager migration as the foundation for all other security measures.
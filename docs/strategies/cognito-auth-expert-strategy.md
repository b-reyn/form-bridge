# Cognito Authentication Expert Strategy Document

**Agent:** cognito-auth-expert  
**Project:** Form-Bridge Multi-Tenant SaaS  
**Last Updated:** 2025-08-26  
**Version:** 1.0

## Executive Summary

This strategy document provides comprehensive guidance for implementing secure, scalable, multi-tenant authentication for the Form-Bridge project using AWS Cognito, KMS, and supporting services. Focus areas include data isolation, secrets management, JWT security, and DDoS protection.

## Current Best Practices (2025)

### Multi-Tenant KMS Strategy

**Cost-Conscious Approach:**
- Use tenant-specific KMS key aliases with dynamic IAM policies for runtime isolation
- Implement envelope encryption for prefix-per-tenant S3 models
- Leverage S3 bucket keys to reduce KMS costs by up to 99%
- Choose between shared vs. separate Cognito user pools based on isolation requirements

**Key Pattern:**
```json
{
  "alias": "alias/customer-<tenant_id>",
  "policy": "dynamically generated at runtime",
  "isolation": "tenant-specific IAM delegation",
  "cost_optimization": "shared keys with envelope encryption"
}
```

### AWS Secrets Manager Implementation

**2025 Best Practices:**
- Use AWS Parameters and Secrets Lambda Extension for caching
- Retrieve secrets during Lambda init phase to reduce cold start impact
- Implement dynamic secret validation for changed secrets
- Store all sensitive data in Secrets Manager, not environment variables

**Implementation Pattern:**
```python
# Lambda extension approach
import boto3
import json
from botocore.exceptions import ClientError

class SecretsManager:
    def __init__(self):
        self.client = boto3.client('secretsmanager')
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes
    
    async def get_secret(self, secret_name, tenant_id=None):
        # Use tenant-specific secret naming
        if tenant_id:
            secret_name = f"{secret_name}/tenant/{tenant_id}"
        
        # Check cache first
        if secret_name in self.cache:
            if not self._is_cache_expired(secret_name):
                return self.cache[secret_name]
        
        # Retrieve and cache
        secret_value = await self._retrieve_secret(secret_name)
        self.cache[secret_name] = {
            'value': secret_value,
            'timestamp': time.time()
        }
        return secret_value
```

### JWT Token Security and Rotation

**Token Rotation Strategy:**
- Access tokens: 15-60 minute lifetime
- Refresh tokens: 7-14 day lifetime with automatic rotation
- Implement refresh token rotation on every use
- Use RS256 asymmetric encryption algorithm

**Secure Storage Methods:**
```javascript
// Frontend secure storage pattern
const tokenConfig = {
  storage: 'httpOnly-cookies',
  secure: true,
  sameSite: 'strict',
  maxAge: 3600, // 1 hour
  rotation: {
    enabled: true,
    window: 86400, // 24 hours
    maxRotations: 30
  }
};

// Never use localStorage for tokens
// ❌ localStorage.setItem('jwt', token);
// ✅ Set-Cookie: jwt=token; HttpOnly; Secure; SameSite=Strict
```

### HMAC Authentication and DDoS Protection

**HMAC Implementation:**
- Use SHA-256 or higher for signature generation
- Implement timestamp validation to prevent replay attacks
- Store HMAC secrets in Secrets Manager with rotation
- Validate request integrity before processing

**Rate Limiting Strategy:**
```python
# Multi-layer protection
rate_limits = {
    'per_ip': {'requests': 100, 'window': 60},
    'per_tenant': {'requests': 1000, 'window': 60},
    'per_hmac_key': {'requests': 500, 'window': 60},
    'global': {'requests': 10000, 'window': 60}
}

# DDoS protection layers
protection_layers = [
    'CloudFront rate limiting',
    'API Gateway throttling',
    'WAF rules and IP blocking',
    'Lambda concurrent execution limits'
]
```

## Project-Specific Implementation Patterns

### Multi-Tenant Cognito Architecture

**Recommended Approach: Shared User Pool**
```json
{
  "UserPoolName": "FormBridge-AdminPool",
  "Policies": {
    "PasswordPolicy": {
      "MinimumLength": 12,
      "RequireUppercase": true,
      "RequireLowercase": true,
      "RequireNumbers": true,
      "RequireSymbols": true,
      "TemporaryPasswordValidityDays": 1
    }
  },
  "MfaConfiguration": "OPTIONAL",
  "EnabledMfas": ["SOFTWARE_TOKEN_MFA", "SMS_MFA"],
  "UserAttributes": [
    {"Name": "email", "Required": true, "Mutable": false},
    {"Name": "custom:tenant_id", "Mutable": false},
    {"Name": "custom:role", "Mutable": true},
    {"Name": "custom:permissions", "Mutable": true}
  ],
  "LambdaTriggers": {
    "PreTokenGeneration": "customize-jwt-claims",
    "PreAuthentication": "validate-tenant-access",
    "PostAuthentication": "audit-login"
  }
}
```

### Cross-Tenant Access Prevention

**Lambda Authorizer Pattern:**
```python
def lambda_authorizer(event, context):
    """
    Validates JWT and enforces tenant isolation
    """
    token = extract_token(event)
    claims = validate_jwt(token)
    
    # Extract tenant context
    tenant_id = claims.get('custom:tenant_id')
    requested_tenant = extract_tenant_from_request(event)
    
    # Prevent cross-tenant access
    if tenant_id != requested_tenant:
        return generate_policy('Deny', event['methodArn'])
    
    # Generate policy with tenant context
    policy = generate_policy('Allow', event['methodArn'])
    policy['context'] = {
        'tenant_id': tenant_id,
        'user_role': claims.get('custom:role'),
        'permissions': claims.get('custom:permissions')
    }
    
    return policy
```

### KMS Tenant Isolation

**Dynamic Key Access Pattern:**
```python
def get_tenant_kms_key(tenant_id):
    """
    Returns tenant-specific KMS key with dynamic IAM policy
    """
    key_alias = f"alias/formbridge-tenant-{tenant_id}"
    
    # Check if key exists, create if not
    try:
        key_info = kms_client.describe_key(KeyId=key_alias)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            key_info = create_tenant_key(tenant_id)
    
    # Generate temporary credentials with tenant-specific permissions
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
                "Resource": key_info['KeyMetadata']['Arn'],
                "Condition": {
                    "StringEquals": {
                        "kms:EncryptionContext:tenant_id": tenant_id
                    }
                }
            }
        ]
    }
    
    return {
        'key_id': key_info['KeyMetadata']['KeyId'],
        'key_alias': key_alias,
        'policy': policy
    }
```

## Critical Security Implementation Priorities

### P0 - Immediate (Within 1 Week)

1. **Master Secrets Migration** 
   - Move all hardcoded secrets from environment variables to Secrets Manager
   - Implement Lambda extension for secret caching
   - Cost Impact: ~$5-10/month additional

2. **Cross-Tenant Access Validation**
   - Deploy Lambda authorizer with tenant context validation
   - Implement request-level tenant isolation checks
   - Cost Impact: Minimal (existing Lambda invocations)

3. **JWT Token Security**
   - Implement HttpOnly cookie storage
   - Add token rotation mechanism
   - Set appropriate token lifetimes
   - Cost Impact: Minimal

### P1 - High Priority (Within 2 Weeks)

4. **Multi-Tenant KMS Implementation**
   - Create tenant-specific KMS keys with aliases
   - Implement dynamic IAM policies for key access
   - Add encryption context for service isolation
   - Cost Impact: $1/key/month + $0.03/10,000 API calls

5. **Key Rotation Mechanism**
   - Implement 90-day rotation cycle for HMAC secrets
   - Add automatic rotation for database credentials
   - Create rotation monitoring and alerting
   - Cost Impact: ~$15-20/month (Lambda + Secrets Manager)

6. **Enhanced Rate Limiting**
   - Implement multi-layer rate limiting (IP, tenant, HMAC key)
   - Add DDoS protection with WAF rules
   - Configure CloudFront rate limiting
   - Cost Impact: ~$20-30/month (WAF + CloudFront)

### P2 - Medium Priority (Within 1 Month)

7. **MFA Implementation**
   - Enable software token MFA for admin users
   - Add SMS backup MFA option
   - Implement MFA enforcement policies
   - Cost Impact: ~$0.05/SMS + software token costs

8. **Session Management**
   - Implement session timeout (30 minutes idle)
   - Add auto-logout functionality
   - Create session monitoring dashboard
   - Cost Impact: Minimal

9. **Advanced Monitoring**
   - Add security event logging
   - Implement anomaly detection for auth patterns
   - Create security dashboards
   - Cost Impact: ~$10-15/month (CloudWatch)

## Cost Analysis and Budget Impact

### MVP Budget Considerations ($15-25/month target)

**Security Costs (Monthly):**
- Secrets Manager: $0.40/secret/month + $0.05/10,000 API calls
- KMS Keys: $1/key/month (5 tenants = $5/month)
- KMS API Calls: $0.03/10,000 calls (~$2-3/month)
- WAF: $1/month + $0.60/million requests
- CloudWatch Logs: $0.50/GB stored

**Total Estimated Security Cost: $15-25/month**

This fits within or slightly exceeds the MVP budget, but the security benefits justify the cost.

### Cost Optimization Strategies

1. **Shared KMS Keys**: Use envelope encryption to share root keys
2. **S3 Bucket Keys**: Reduce KMS API calls by 99%
3. **Lambda Extensions**: Cache secrets to reduce API calls
4. **CloudFront Caching**: Reduce origin requests and costs

## Integration Patterns

### EventBridge Integration
```python
def publish_security_event(event_type, tenant_id, details):
    """
    Publish security events to EventBridge for monitoring
    """
    event_bridge.put_events(
        Entries=[
            {
                'Source': 'formbridge.security',
                'DetailType': event_type,
                'Detail': json.dumps({
                    'tenant_id': tenant_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'details': details
                })
            }
        ]
    )
```

### DynamoDB Integration
```python
def store_audit_log(tenant_id, user_id, action, resource):
    """
    Store security audit logs in DynamoDB
    """
    table.put_item(
        Item={
            'PK': f'AUDIT#{tenant_id}',
            'SK': f'{datetime.utcnow().isoformat()}#{user_id}',
            'action': action,
            'resource': resource,
            'timestamp': int(time.time()),
            'TTL': int(time.time()) + (90 * 24 * 60 * 60)  # 90 days retention
        }
    )
```

## Testing and Validation Approaches

### Security Test Suite

1. **Authentication Tests**
   - Valid/invalid JWT token validation
   - Cross-tenant access prevention
   - Token rotation functionality
   - Session timeout behavior

2. **Authorization Tests**
   - Role-based access control
   - Tenant isolation enforcement
   - Permission boundary validation
   - HMAC signature verification

3. **Security Tests**
   - Rate limiting effectiveness
   - DDoS protection validation
   - Secrets rotation testing
   - KMS key isolation verification

4. **Performance Tests**
   - Authentication latency (< 100ms target)
   - Secret retrieval performance
   - KMS encryption/decryption speed
   - Rate limiting impact on legitimate traffic

### Monitoring and Alerting

```python
# Key security metrics to monitor
security_metrics = [
    'failed_authentication_attempts',
    'cross_tenant_access_violations',
    'rate_limit_exceeded_events',
    'hmac_signature_failures',
    'token_rotation_failures',
    'secrets_retrieval_errors',
    'kms_access_denied_events'
]

# Alert thresholds
alert_thresholds = {
    'failed_auth_rate': {'threshold': 10, 'period': 300},  # 10 failures in 5 minutes
    'cross_tenant_violations': {'threshold': 1, 'period': 60},  # Any violation
    'rate_limit_breaches': {'threshold': 100, 'period': 300},  # 100 in 5 minutes
}
```

## Timeline and Dependencies

### Implementation Timeline

**Week 1:**
- P0 items: Secrets migration, JWT security, basic tenant validation

**Week 2:**
- P1 items: KMS implementation, rate limiting enhancements

**Week 3-4:**
- P2 items: MFA, advanced monitoring, session management

### Dependencies

- **Infrastructure**: DynamoDB tables for audit logs
- **Networking**: CloudFront distribution for rate limiting
- **Monitoring**: CloudWatch dashboards and alarms
- **CI/CD**: Automated security testing in deployment pipeline

## Knowledge Base and Lessons Learned

### Successful Patterns

1. **Lambda Extension Caching**: Reduces Secrets Manager API calls by 80%
2. **Tenant-Specific KMS Keys**: Provides strong isolation with manageable costs
3. **Multi-Layer Rate Limiting**: Effectively prevents both DDoS and abuse
4. **JWT with HttpOnly Cookies**: Balances security and usability

### Common Pitfalls

1. **Environment Variable Secrets**: Never store secrets in Lambda env vars
2. **localStorage JWT Storage**: Vulnerable to XSS attacks
3. **Shared KMS Keys Without Context**: Can lead to cross-tenant data access
4. **Insufficient Rate Limiting**: Single-layer protection is insufficient

### Anti-Patterns to Avoid

- Storing secrets in code or configuration files
- Using symmetric encryption for JWT tokens
- Implementing custom authentication instead of proven solutions
- Ignoring token rotation and key management
- Single points of failure in authentication flow

## Future Improvements and Roadmap

### Q2 2025 Enhancements

1. **Advanced Threat Detection**
   - ML-based anomaly detection for authentication patterns
   - Behavioral analysis for user access patterns
   - Integration with AWS GuardDuty

2. **Zero-Trust Architecture**
   - Device registration and validation
   - Continuous authentication and authorization
   - Risk-based access controls

3. **Enhanced Multi-Tenancy**
   - Per-tenant security policies
   - Custom authentication flows per tenant
   - Tenant-specific MFA requirements

### Long-term Vision

- Fully automated security posture management
- Real-time threat response and mitigation
- Compliance automation (SOC 2, GDPR, HIPAA)
- Advanced analytics for security insights

---

**Document Status**: Active  
**Next Review**: 2025-09-26  
**Maintained By**: cognito-auth-expert  
**Distribution**: Form-Bridge development team
# Form-Bridge WordPress Plugin Authentication System

A comprehensive serverless authentication and management system for the Form-Bridge WordPress plugin, designed to support agencies with 50+ WordPress sites while maintaining security and preventing abuse.

## 🏗️ Architecture Overview

This system implements a secure, scalable authentication flow using AWS Lambda functions orchestrated through API Gateway, with DynamoDB for data persistence and S3 for plugin distribution.

### Key Components

- **5 Lambda Functions** - Each handling specific authentication responsibilities
- **Single DynamoDB Table** - Optimized access patterns for all data types
- **API Gateway** - RESTful API with custom authorizer
- **S3 Bucket** - Secure plugin distribution with signed URLs
- **CloudWatch** - Comprehensive monitoring and alerting

## 🔐 Security Features

### Multi-Layered Authentication
- **HMAC Signature Verification** - Prevents request tampering
- **Site Ownership Validation** - File-based or meta-tag verification  
- **Rate Limiting** - Per-IP and per-site request throttling
- **Abuse Detection** - Pattern recognition for malicious activity
- **Audit Logging** - Complete security event tracking

### Isolation & Protection
- **Tenant Isolation** - Each site operates independently
- **API Key Hashing** - Keys never stored in plaintext
- **Signed Update URLs** - Time-limited download access
- **TTL Auto-Cleanup** - Automatic data lifecycle management

## 📁 File Structure

```
lambdas/wp-plugin-auth/
├── 🐍 Lambda Functions
│   ├── initial_registration.py    # Site registration with minimal info
│   ├── key_exchange.py           # Temp key → permanent credentials
│   ├── authentication.py         # API Gateway custom authorizer
│   ├── update_check.py           # Version checking & downloads
│   └── site_validation.py        # Abuse prevention & validation
├── 🛠️ Infrastructure & Config
│   ├── template.yaml             # SAM deployment template
│   ├── dynamodb_design.md        # Single table access patterns
│   ├── shared_utils.py           # Common utilities & security functions
│   └── requirements.txt          # Python dependencies
├── 🚀 Deployment & Testing
│   ├── deploy.sh                 # One-click deployment script
│   └── test_endpoints.py         # Comprehensive API testing
└── 📚 Documentation
    └── README.md                 # This file
```

## 🚀 Quick Start

### Prerequisites
- AWS CLI configured with appropriate permissions
- SAM CLI installed (`pip install aws-sam-cli`)
- Python 3.12 (recommended for best performance)

### Deploy to AWS

1. **Clone and Navigate**
   ```bash
   cd /mnt/c/projects/form-bridge/lambdas/wp-plugin-auth
   ```

2. **Deploy with One Command**
   ```bash
   ./deploy.sh dev  # or 'staging', 'prod'
   ```

3. **Test the Deployment**
   ```bash
   python3 test_endpoints.py https://your-api-url.com/dev --endpoint all
   ```

## 🔄 Authentication Flow

### 1. Initial Registration
WordPress sites register with minimal information:

```bash
POST /register
{
  "domain": "example.com",
  "wp_version": "6.4.2", 
  "plugin_version": "1.0.0",
  "admin_email": "admin@example.com"  # optional
}
```

**Returns:** Temporary key and registration ID for verification

### 2. Site Ownership Verification
Sites prove ownership using one of two methods:

**File Method:** Upload verification file to `/.well-known/form-bridge-verification.txt`
```
temp_key=abc123...
domain=example.com
timestamp=1234567890
```

**Meta Tag Method:** Add meta tag to site homepage
```html
<meta name="form-bridge-verification" content="abc123...">
```

### 3. Key Exchange
Exchange temporary key for permanent credentials:

```bash
POST /exchange
{
  "temp_key": "abc123...",
  "verification_method": "file",
  "challenge_response": "verification_content"
}
```

**Returns:** Permanent API key, webhook secret, and endpoints

### 4. Authenticated Requests
Use API key for all subsequent requests:

```bash
Authorization: Bearer your_api_key_here
```

## 🛡️ Security Implementation

### Rate Limiting
```python
# Per-IP Registration Limits
RATE_LIMITS_REGISTRATION = {
    'minute': 3,    # 3 registrations per minute
    'hour': 10      # 10 registrations per hour
}

# Per-Site API Limits  
RATE_LIMITS_API = {
    'minute': 100,  # 100 requests per minute
    'hour': 2000,   # 2000 requests per hour
    'day': 10000    # 10000 requests per day
}
```

### Abuse Detection Patterns
- **Registration Spam** - Multiple registrations from same IP
- **Invalid Domains** - Blocked TLDs and suspicious patterns
- **Burst Requests** - More than 20 requests per second
- **Failed Auth Attempts** - More than 50 failures per hour

### Security Headers
All responses include comprehensive security headers:
```python
{
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY', 
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Referrer-Policy': 'strict-origin-when-cross-origin'
}
```

## 📊 DynamoDB Single Table Design

### Access Patterns by Entity Type

| Entity | PK | SK | GSI1PK | GSI1SK | Use Case |
|--------|----|----|--------|--------|----------|
| **Registration** | `SITE#{domain}` | `REG#{id}` | `TEMP#{temp_key}` | `STATUS#pending` | Initial registration |
| **Site Credentials** | `SITE#{domain}` | `CREDS#{site_id}` | `SITE#{site_id}` | `ACTIVE` | Active site data |
| **API Key Lookup** | `API#{key_hash}` | `LOOKUP` | `SITE#{site_id}` | `API_KEY` | Auth validation |
| **Rate Limiting** | `RATE#{identifier}` | `TIME#{timestamp}` | `RATE#{identifier}` | `TIME#{timestamp}` | Request throttling |
| **Validation Cache** | `VALIDATION#{domain}` | `RESULT` | `REG#{reg_id}` | `VALIDATION` | Site validation |
| **Security Events** | `SECURITY#{type}` | `{id}#{time}` | `SECURITY_TRACKING#{id}` | `TIME#{time}` | Audit logging |

### TTL Auto-Cleanup
- **Temp registrations**: 1 hour
- **Rate limit records**: 24 hours  
- **Validation cache**: 24 hours
- **Security events**: 7-365 days (by severity)

## 🔧 Configuration Options

### Environment Variables
```bash
# Core Settings
TABLE_NAME=form-bridge-plugin-auth-dev
ENVIRONMENT=dev
API_DOMAIN=api.form-bridge.com
PLUGIN_BUCKET=form-bridge-plugin-releases

# Security Settings  
MAX_REGISTRATIONS_PER_IP=3
RATE_LIMIT_WINDOW=300
TEMP_KEY_EXPIRY=3600
VALIDATION_CACHE_TTL=86400

# Secrets
SIGNING_SECRET_NAME=form-bridge/dev/plugin-signing-key
```

### Rate Limit Customization
Adjust limits in `shared_utils.py`:
```python
class Constants:
    RATE_LIMITS_REGISTRATION = {'minute': 3, 'hour': 10}
    RATE_LIMITS_API = {'minute': 100, 'hour': 2000, 'day': 10000}
    RATE_LIMITS_UPDATES = {'minute': 10, 'hour': 100, 'day': 500}
```

## 📈 Performance & Cost Optimization

### Lambda Optimization
- **ARM64 Architecture** - 20% cost savings with Graviton2
- **Right-sized Memory** - 512MB for most functions, 1024MB for validation
- **Connection Reuse** - AWS SDK clients initialized outside handlers
- **Cold Start Mitigation** - Minimal imports and optimized initialization

### DynamoDB Efficiency  
- **On-Demand Billing** - Pay only for actual usage
- **Hot Partition Avoidance** - Time-based sort keys distribute load
- **Sparse Indexes** - GSI only stores relevant items
- **TTL Cleanup** - Automatic data lifecycle management

### Estimated Costs (1M submissions/month)
- **Lambda**: ~$20/month (1M requests, 200ms average)
- **DynamoDB**: ~$25/month (reads + writes + storage)
- **API Gateway**: ~$3.50/month (1M requests)
- **S3**: ~$5/month (storage + transfers)
- **Total**: ~$55/month

## 🧪 Testing

### Automated Testing
```bash
# Test all endpoints
python3 test_endpoints.py https://api.example.com/dev

# Test specific functionality
python3 test_endpoints.py https://api.example.com/dev --endpoint register
python3 test_endpoints.py https://api.example.com/dev --endpoint rate-limit
python3 test_endpoints.py https://api.example.com/dev --endpoint cors
```

### Local Development
```bash
# Start local API
sam local start-api --port 3000

# Test locally
python3 test_endpoints.py http://localhost:3000
```

### Load Testing
```bash
# Install artillery for load testing
npm install -g artillery

# Run load test
artillery quick --count 100 --num 10 https://your-api.com/dev/register
```

## 📊 Monitoring & Alerts

### CloudWatch Metrics
- **Registration Rate** - New site registrations per hour
- **Authentication Success/Failure** - API key validation rates  
- **Update Check Frequency** - Plugin update polling
- **Rate Limit Hits** - Blocked requests by endpoint
- **Error Rates** - Function failures and timeouts

### Configured Alarms
- **High Error Rate** - >10 errors in 5 minutes
- **High Latency** - >5 second average response time
- **Rate Limit Abuse** - >100 blocked requests per minute

### Log Analysis
```bash
# View recent logs
sam logs --stack-name form-bridge-plugin-auth-dev --tail

# Search for security events
aws logs filter-log-events --log-group-name /aws/lambda/form-bridge-plugin-auth-dev \
    --filter-pattern "ERROR" --start-time $(date -d '1 hour ago' +%s)000
```

## 🔒 Security Best Practices

### Secrets Management
- **API Keys**: Never stored in plaintext (SHA256 hashed)
- **Webhook Secrets**: Encrypted at rest in DynamoDB
- **Signing Keys**: Stored in AWS Secrets Manager with rotation
- **Environment Variables**: Used for non-sensitive configuration only

### Network Security
- **HTTPS Only**: All endpoints require TLS 1.2+
- **CORS Configuration**: Properly configured for WordPress origins
- **API Gateway Throttling**: Request rate limiting at gateway level
- **Lambda VPC**: Can be placed in private subnets if needed

### Compliance
- **GDPR Ready**: IP addresses can be hashed/anonymized
- **SOC 2**: AWS services are SOC 2 compliant
- **Data Retention**: Configurable TTL for all stored data
- **Audit Trail**: Complete logging of all security events

## 🚨 Troubleshooting

### Common Issues

**Registration Fails with 429 Rate Limited**
- Check IP rate limits in CloudWatch
- Verify RATE_LIMITS_REGISTRATION settings
- Consider IP allowlisting for legitimate bulk operations

**Key Exchange Fails Verification**
- Ensure verification file is accessible via HTTPS
- Check file content matches expected format
- Verify domain DNS resolution and certificate

**Authentication Returns 401 Unauthorized**  
- Confirm API key is correctly formatted in Authorization header
- Check site status in DynamoDB (should be 'active')
- Verify no rate limits are exceeded

**High Lambda Costs**
- Review memory allocation (start with 512MB)
- Check for unnecessary cold starts
- Optimize dependencies and imports

### Debug Mode
Enable detailed logging by setting environment variable:
```bash
POWERTOOLS_LOG_LEVEL=DEBUG
```

## 🤝 Contributing

### Development Workflow
1. Make changes to Lambda functions
2. Test locally with `sam local start-api`
3. Run test suite with `test_endpoints.py` 
4. Deploy to dev environment with `./deploy.sh dev`
5. Monitor CloudWatch logs and metrics

### Code Standards
- **Type Hints**: Use Python type annotations
- **Error Handling**: Comprehensive try-catch blocks
- **Logging**: Structured logging with correlation IDs
- **Security**: Input validation on all user data
- **Documentation**: Docstrings for all functions

## 📞 Support

For issues, feature requests, or questions:
1. Check CloudWatch logs for error details
2. Review this README and DynamoDB design docs
3. Run test suite to isolate issues
4. Monitor rate limits and security events

---

**🎉 Form-Bridge Plugin Authentication System - Secure, Scalable, Cost-Effective**

*Built with AWS Lambda, DynamoDB, and security best practices for WordPress plugin ecosystems*
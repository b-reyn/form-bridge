# Form-Bridge MVP Quick Start Guide

**Deploy a Working Form Ingestion System in Under 10 Minutes**

*Last Updated: January 26, 2025*
*Target Time: < 10 minutes to working deployment*

## Overview

This guide will get you from zero to a working, multi-tenant form ingestion system deployed on AWS. The MVP prioritizes speed and simplicity - you can enhance it later.

## What You'll Deploy

- **API Gateway**: HTTP API with Lambda authorizer
- **3 Lambda Functions**: Ingestion, processing, and authorization  
- **DynamoDB**: Single table for multi-tenant form storage
- **EventBridge**: Event routing between components
- **Secrets Manager**: Secure tenant credential storage
- **Sample Tenant**: Ready-to-test configuration

**Total AWS Resources**: ~8 resources, fully serverless, pay-per-use

## Prerequisites

### Required Tools
```bash
# Check if you have these tools installed:
aws --version          # AWS CLI v2.x
sam --version          # SAM CLI v1.70+
python3 --version      # Python 3.9+
curl --version         # For testing
```

### Install Missing Tools
```bash
# Install AWS CLI (if needed)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Install SAM CLI (if needed)  
pip install aws-sam-cli

# Configure AWS credentials
aws configure
```

### AWS Account Setup
- **Required Permissions**: IAM, Lambda, API Gateway, DynamoDB, EventBridge, Secrets Manager, CloudFormation
- **Estimated Cost**: $2-5 for testing, scales to ~$25/month for 100K submissions
- **Region**: Use `us-east-1` for fastest deployment

## Deployment Options

Choose the method that works best for you:

### Option 1: GitHub Actions (Recommended)

**Setup Time: 2 minutes, Deploy Time: 8 minutes**

1. **Fork or clone the repository**
2. **Set GitHub Secrets** (Repository Settings → Secrets and variables → Actions):
   ```
   AWS_ACCESS_KEY_ID=your_access_key_here
   AWS_SECRET_ACCESS_KEY=your_secret_key_here
   ```
3. **Trigger deployment**:
   - **Automatic**: Push to `main` branch
   - **Manual**: Go to Actions tab → "Deploy MVP - Fast & Reliable" → Run workflow

4. **Monitor deployment**: Check GitHub Actions for progress and outputs

**Advantages**: 
- Automatic deployments on code changes
- Built-in validation and testing
- Clear deployment logs and outputs
- Automatic cleanup on failures

### Option 2: Local Script Deployment

**Setup Time: 1 minute, Deploy Time: 5 minutes**

```bash
# Clone repository (if not done already)
git clone https://github.com/your-org/form-bridge.git
cd form-bridge

# Deploy to development environment
./scripts/quick-deploy.sh

# Deploy to specific environment (dev/staging/prod)
./scripts/quick-deploy.sh staging
```

**The script will**:
1. Validate AWS credentials and permissions
2. Build Lambda functions (x86_64, minimal deps)
3. Deploy CloudFormation stack (~3-5 minutes)
4. Create sample tenant configuration
5. Output API endpoint and test commands

### Option 3: Docker Development Environment

**Setup Time: 3 minutes, Deploy Time: 5 minutes**

```bash
# Start development container
docker compose up -d
docker compose exec app bash

# Inside container - deploy MVP
./scripts/mvp-deploy.sh dev

# Run tests
python3 scripts/test-mvp.py
```

**Advantages**:
- Consistent environment across developers
- All tools pre-installed
- No local dependency conflicts

## Post-Deployment Testing

### 1. Validate Deployment
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name formbridge-mvp-dev \
  --query 'Stacks[0].StackStatus'

# Should return: "CREATE_COMPLETE"
```

### 2. Get API Endpoint
```bash
# Get API Gateway endpoint from stack outputs
aws cloudformation describe-stacks \
  --stack-name formbridge-mvp-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text
```

### 3. Test Form Submission
```bash
# Replace YOUR_API_ENDPOINT with actual endpoint from above
curl -X POST https://YOUR_API_ENDPOINT/submit \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: t_sample" \
  -H "X-API-Key: mvp-test-key-123" \
  -d '{
    "form_data": {
      "name": "Test User",
      "email": "test@example.com",
      "message": "Hello from Form-Bridge MVP!"
    },
    "form_type": "contact"
  }'
```

**Expected Response**:
```json
{
  "status": "success",
  "submission_id": "sub_01234567-89ab-cdef-0123-456789abcdef",
  "message": "Form submission received"
}
```

### 4. Verify Data Storage
```bash
# Check DynamoDB for stored submission
aws dynamodb scan \
  --table-name formbridge-mvp-dev \
  --limit 5

# Check processing logs
aws logs tail /aws/lambda/formbridge-mvp-processor-dev --follow
```

### 5. Monitor Processing
```bash
# Watch EventBridge processing
aws logs tail /aws/lambda/formbridge-mvp-ingest-dev --follow

# In another terminal, send more test submissions
for i in {1..5}; do
  curl -X POST https://YOUR_API_ENDPOINT/submit \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: t_sample" \
    -H "X-API-Key: mvp-test-key-123" \
    -d "{\"test_id\": $i, \"form_data\": {\"email\": \"test$i@example.com\"}}"
  sleep 1
done
```

## Understanding Your Deployment

### What Was Created

**API Gateway HTTP API**:
- Endpoint: `https://{api-id}.execute-api.{region}.amazonaws.com/`
- Authorizer: Lambda function validating tenant API keys
- Routes: `POST /submit` for form ingestion

**Lambda Functions**:
- `formbridge-mvp-ingest-{env}`: Processes form submissions
- `formbridge-mvp-processor-{env}`: Handles EventBridge events
- `formbridge-mvp-authorizer-{env}`: Validates API requests

**DynamoDB Table**:
- `formbridge-mvp-{env}`: Single table storing all form submissions
- Partition Key: `PK` (format: `TENANT#{tenant_id}`)
- Sort Key: `SK` (format: `SUB#{submission_id}#{timestamp}`)

**EventBridge Rule**:
- Routes `submission.received` events to processor Lambda
- Enables decoupled, event-driven processing

**Secrets Manager**:
- `formbridge/tenants/t_sample`: Sample tenant configuration
- Stores API keys and tenant metadata securely

### Data Flow

```
1. Client POST → API Gateway
2. Lambda Authorizer validates tenant & API key
3. Ingest Lambda processes form data
4. Data stored in DynamoDB with tenant prefix
5. Event published to EventBridge
6. Processor Lambda updates submission status
7. Response returned to client
```

### Sample Tenant Configuration

**Tenant ID**: `t_sample`
**API Key**: `mvp-test-key-123`
**Usage**: Testing and development

## Adding Your Own Tenants

### Create New Tenant
```bash
# Create tenant secret
aws secretsmanager create-secret \
  --name "formbridge/tenants/t_mycompany" \
  --secret-string '{
    "api_key": "your-secure-api-key-456",
    "tenant_name": "My Company",
    "created_at": "2025-01-26T12:00:00Z",
    "contact_email": "admin@mycompany.com"
  }'

# Test with new tenant
curl -X POST https://YOUR_API_ENDPOINT/submit \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: t_mycompany" \
  -H "X-API-Key: your-secure-api-key-456" \
  -d '{"form_data": {"email": "customer@example.com"}}'
```

### Best Practices for Tenant IDs
- Format: `t_{company_name}` (lowercase, no spaces)
- Examples: `t_acmecorp`, `t_startup123`, `t_bigcompany`
- Keep under 50 characters
- Use only letters, numbers, and underscores

## Integration Examples

### WordPress Integration
```php
<?php
// Add to your theme's functions.php or custom plugin
function send_form_to_bridge($form_data) {
    $api_endpoint = 'https://YOUR_API_ENDPOINT/submit';
    $tenant_id = 't_mycompany';
    $api_key = 'your-secure-api-key-456';
    
    $response = wp_remote_post($api_endpoint, array(
        'headers' => array(
            'Content-Type' => 'application/json',
            'X-Tenant-ID' => $tenant_id,
            'X-API-Key' => $api_key
        ),
        'body' => json_encode(array(
            'form_data' => $form_data,
            'form_type' => 'contact',
            'source' => 'wordpress'
        )),
        'timeout' => 10
    ));
    
    if (is_wp_error($response)) {
        error_log('Form-Bridge submission failed: ' . $response->get_error_message());
    }
}

// Hook into Contact Form 7 submissions
add_action('wpcf7_mail_sent', function($contact_form) {
    $submission = WPCF7_Submission::get_instance();
    if ($submission) {
        send_form_to_bridge($submission->get_posted_data());
    }
});
?>
```

### JavaScript/HTML Integration
```javascript
// Simple form submission handler
async function submitToFormBridge(formData) {
    try {
        const response = await fetch('https://YOUR_API_ENDPOINT/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Tenant-ID': 't_mycompany',
                'X-API-Key': 'your-secure-api-key-456'
            },
            body: JSON.stringify({
                form_data: formData,
                form_type: 'contact',
                source: 'website'
            })
        });
        
        const result = await response.json();
        console.log('Form submitted successfully:', result.submission_id);
        return result;
    } catch (error) {
        console.error('Form submission failed:', error);
        throw error;
    }
}

// Example usage with a form
document.getElementById('contact-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);
    
    try {
        await submitToFormBridge(data);
        alert('Thank you! Your form has been submitted.');
    } catch (error) {
        alert('Sorry, there was an error submitting your form.');
    }
});
```

## Monitoring Your MVP

### CloudWatch Dashboards
```bash
# View Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=formbridge-mvp-ingest-dev \
  --start-time 2025-01-26T00:00:00Z \
  --end-time 2025-01-26T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

### Essential Metrics to Watch
- **API Gateway 5xx Errors**: Should be < 0.1%
- **Lambda Error Rate**: Should be < 1%
- **DynamoDB Throttling**: Should be 0
- **Average Response Time**: Should be < 500ms

### Log Analysis
```bash
# Search for errors across all functions
aws logs filter-log-events \
  --log-group-name /aws/lambda/formbridge-mvp-ingest-dev \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000

# Monitor form submissions in real-time
aws logs tail /aws/lambda/formbridge-mvp-ingest-dev \
  --follow --filter-pattern "submission_id"
```

## Cost Monitoring

### Set Up Billing Alerts
```bash
# Create SNS topic for billing alerts
aws sns create-topic --name formbridge-billing-alerts

# Subscribe to email notifications
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT:formbridge-billing-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

### Expected Costs (First Month)
- **Free Tier**: Should cover initial testing
- **Light Usage** (1K submissions): ~$2-5
- **Moderate Usage** (10K submissions): ~$8-15
- **Heavy Usage** (100K submissions): ~$25-35

## Next Steps After MVP

### Immediate Improvements (Week 1)
1. **Custom Domain**: Set up Route 53 and API Gateway custom domain
2. **HTTPS Certificates**: Use AWS Certificate Manager
3. **Enhanced Monitoring**: Add CloudWatch alarms
4. **Backup Strategy**: Enable DynamoDB point-in-time recovery

### Short-term Enhancements (Month 1)
1. **HMAC Authentication**: Upgrade from API keys to signed requests
2. **Webhook Delivery**: Add outbound connectors to external systems
3. **Admin Dashboard**: Build React UI for managing submissions
4. **Load Testing**: Validate performance under realistic load

### Medium-term Features (Quarter 1)
1. **ARM64 Migration**: Move to Graviton2 for cost savings
2. **Multi-region**: Deploy in multiple AWS regions
3. **Advanced Analytics**: Add submission analytics and reporting
4. **Enterprise Security**: Implement WAF, enhanced monitoring

## Cleanup (If Needed)

### Delete Everything
```bash
# Delete CloudFormation stack (removes all resources)
aws cloudformation delete-stack --stack-name formbridge-mvp-dev

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete --stack-name formbridge-mvp-dev

# Manually delete Secrets Manager secrets (if desired)
aws secretsmanager delete-secret \
  --secret-id formbridge/tenants/t_sample \
  --force-delete-without-recovery
```

### Partial Cleanup (Keep Data)
```bash
# Scale down to zero (keeps data, minimizes cost)
aws lambda put-provisioned-concurrency-config \
  --function-name formbridge-mvp-ingest-dev \
  --provisioned-concurrency-config ProvisionedConcurrencyValue=0
```

## Getting Help

### Troubleshooting
- [Common Issues](../TROUBLESHOOTING.md)
- [Architecture Details](MVP-ARCHITECTURE.md)
- [Simplification Choices](SIMPLIFIED-CHOICES.md)

### Support Resources
- **AWS Documentation**: [serverless.aws](https://serverless.aws)
- **GitHub Issues**: Report bugs and request features
- **CloudWatch Insights**: Query logs across all functions
- **AWS Support**: For account and billing issues

### Community
- **Discussions**: GitHub Discussions for questions
- **Examples**: [Form-Bridge Examples Repository](../examples/)
- **Integrations**: Community-contributed platform integrations

---

## Summary

You now have a working, serverless form ingestion system that can:
- Accept form submissions from multiple sources
- Validate and authenticate tenants securely
- Store data with multi-tenant isolation
- Process events asynchronously
- Scale automatically with demand
- Cost less than $50/month for most use cases

**Remember**: This is an MVP optimized for deployment speed. You can enhance it incrementally as your needs grow.

**Next Steps**: Test with your real forms, add your tenants, and start processing submissions!
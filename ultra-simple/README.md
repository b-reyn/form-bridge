# Form-Bridge Ultra-Simple Implementation

This is the ultra-simplified, cost-optimized implementation of Form-Bridge designed to run entirely within AWS Free Tier limits for testing and low-volume production use.

## Key Features

- **Zero to minimal cost**: $0.00 - $0.50/month for testing usage
- **Lambda Function URLs**: Direct HTTPS endpoints (no API Gateway costs)
- **Single Lambda function**: Monolithic design for simplicity
- **DynamoDB on-demand**: Pay only for what you use
- **CloudFront + S3**: Static admin UI with global CDN
- **HMAC authentication**: Secure without complexity
- **Auto-cleanup**: TTL-based data expiration

## Cost Breakdown

### Testing (50-200 requests/month)
- **Lambda**: $0.00 (1M free requests)
- **DynamoDB**: $0.00 (25GB free storage)
- **CloudFront**: $0.00 (50GB free transfer)
- **Total**: **$0.00**

### Production (10,000 requests/month)
- **Lambda**: $0.00 (within free tier)
- **DynamoDB**: $0.01 (minimal operations)
- **CloudFront**: $0.00 (within free tier)
- **Total**: **$0.01 - $1.00**

## Quick Start

### Prerequisites
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install SAM CLI
pip install aws-sam-cli

# Configure AWS credentials
aws configure
```

### Deploy in 2 Minutes
```bash
# 1. Clone and navigate to ultra-simple directory
cd form-bridge/ultra-simple

# 2. Make deploy script executable
chmod +x deploy.sh

# 3. Deploy to AWS
./deploy.sh test

# The script will output:
# - Lambda Function URL (for WordPress plugin)
# - CloudFront URL (for admin UI)
# - DynamoDB table name
```

### Test the Deployment
```python
# Use the test client
python test_client.py https://your-function-url.lambda-url.region.on.aws/

# Or test with curl
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "${TIMESTAMP}:{}" | openssl dgst -sha256 -hmac "your-secret" | cut -d' ' -f2)

curl -X POST https://your-function-url.lambda-url.region.on.aws/ \
  -H "Content-Type: application/json" \
  -H "X-Signature: ${SIGNATURE}" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -d '{"form_data":{"name":"Test","email":"test@example.com"}}'
```

## Architecture Components

### 1. Lambda Function URL
- Direct HTTPS endpoint (no API Gateway)
- Built-in CORS support
- No additional costs
- Scales automatically

### 2. Single DynamoDB Table
```
PK: SUBMISSION
SK: sub_20250126_1737934567.123
- form_data: {JSON}
- metadata: {JSON}
- timestamp: ISO8601
- ttl: Unix timestamp (30 days)
```

### 3. CloudFront + S3
- Static React admin UI
- Global CDN distribution
- HTTPS by default
- Cache for performance

## WordPress Plugin Integration

Update your WordPress plugin to use the Lambda Function URL:

```php
// wp-content/plugins/form-bridge/form-bridge.php

define('FORM_BRIDGE_ENDPOINT', 'https://xxxxx.lambda-url.us-east-1.on.aws/');
define('FORM_BRIDGE_SECRET', 'your-shared-secret');

function submit_to_form_bridge($form_data) {
    $timestamp = time();
    $body = json_encode([
        'form_data' => $form_data,
        'metadata' => [
            'source' => 'wordpress',
            'site_url' => get_site_url(),
            'form_id' => 'contact-form-1'
        ]
    ]);
    
    $message = $timestamp . ':' . $body;
    $signature = hash_hmac('sha256', $message, FORM_BRIDGE_SECRET);
    
    $response = wp_remote_post(FORM_BRIDGE_ENDPOINT, [
        'headers' => [
            'Content-Type' => 'application/json',
            'X-Signature' => $signature,
            'X-Timestamp' => $timestamp
        ],
        'body' => $body,
        'timeout' => 10
    ]);
    
    return json_decode(wp_remote_retrieve_body($response), true);
}
```

## Monitoring

### CloudWatch Logs
```bash
# View real-time logs
aws logs tail /aws/lambda/form-bridge-handler-test --follow

# Query recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/form-bridge-handler-test \
  --filter-pattern "ERROR"
```

### DynamoDB Data
```bash
# View all submissions
aws dynamodb query \
  --table-name form-bridge-test \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"SUBMISSION"}}' \
  --scan-index-forward false \
  --limit 10
```

### Cost Monitoring
```bash
# Check current month's costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE
```

## Security Considerations

1. **HMAC Authentication**: All requests must be signed
2. **Timestamp Validation**: 5-minute window to prevent replay
3. **Rate Limiting**: Lambda reserved concurrency
4. **Data Encryption**: At-rest and in-transit
5. **TTL Cleanup**: Automatic data expiration

## Scaling Path

When you outgrow the ultra-simple architecture:

### Phase 1: Current (0-1K requests/month)
- Lambda Function URLs
- Single DynamoDB table
- Cost: $0.00

### Phase 2: Growth (1K-10K requests/month)
- Add CloudWatch dashboards
- Enable DynamoDB backups
- Cost: $1-5/month

### Phase 3: Scale (10K-100K requests/month)
- Add API Gateway for advanced features
- Implement caching layer
- Cost: $10-50/month

### Phase 4: Enterprise (100K+ requests/month)
- Multi-tenant isolation
- EventBridge for async processing
- Step Functions for workflows
- Cost: $100+/month

## Troubleshooting

### Lambda Function URL returns 403
- Check CORS configuration
- Verify HMAC signature generation
- Ensure timestamp is within 5-minute window

### DynamoDB throttling
- Switch to provisioned capacity if consistent load
- Implement exponential backoff in client

### High costs appearing
- Check for Lambda infinite loops
- Review CloudWatch log retention
- Verify TTL is working on DynamoDB

## Clean Up

Remove all resources:
```bash
# Delete the stack
aws cloudformation delete-stack --stack-name form-bridge-ultra-simple-test

# Verify deletion
aws cloudformation wait stack-delete-complete --stack-name form-bridge-ultra-simple-test
```

## Support

This ultra-simple architecture is designed for:
- Individual developers testing ideas
- Small projects with <10K submissions/month
- Learning serverless on AWS
- Proof of concepts

For production use with higher volume, consider the full architecture with proper monitoring, multi-tenancy, and enterprise features.
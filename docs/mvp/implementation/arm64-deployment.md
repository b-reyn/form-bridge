# Form-Bridge ARM64 Deployment Guide
## 20% Cost Savings with Graviton2 Optimization

This guide provides step-by-step instructions for deploying Form-Bridge Lambda functions with ARM64 architecture optimization, achieving 20% cost savings and improved performance.

## Prerequisites

### Required Tools
```bash
# Install AWS SAM CLI
pip install aws-sam-cli

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install Docker for local testing
# Follow instructions at https://docs.docker.com/get-docker/

# Install Python 3.12 for local development
sudo apt update && sudo apt install python3.12 python3.12-venv
```

### AWS Permissions
Ensure your AWS CLI is configured with permissions for:
- Lambda (create, update, delete functions and layers)
- IAM (create roles and policies)
- API Gateway (create and manage APIs)
- EventBridge (create event buses and rules)
- DynamoDB (create and manage tables)
- S3 (create buckets and manage objects)
- CloudWatch (create log groups and metrics)
- Secrets Manager (create and manage secrets)
- Step Functions (create state machines)

## ARM64 Architecture Benefits

### Cost Savings (Verified 2025)
- **20% lower duration charges** compared to x86_64
- **Additional 17% savings** with Compute Savings Plans
- **Total potential savings: 35%** on Lambda compute costs

### Performance Benefits
- **Up to 19% better performance** for compute-intensive workloads
- **Up to 34% price-performance improvement** overall
- **Faster cold start times** with Python 3.12 runtime
- **60% less energy consumption** than x86 equivalents

## Deployment Steps

### Step 1: Environment Setup

Create environment configuration:
```bash
# Set deployment variables
export ENVIRONMENT="dev"  # or staging, prod
export AWS_REGION="us-east-1"
export SECRET_PREFIX="formbridge"
export EVENT_BUS_NAME="form-bridge-bus"
export DYNAMODB_TABLE_NAME="form-bridge-data"

# Configure AWS CLI
aws configure set default.region $AWS_REGION
aws configure set default.output json
```

### Step 2: Build ARM64 Functions

Build all functions with ARM64 architecture:
```bash
# Build with ARM64 target
sam build \
    --template template-arm64-optimized.yaml \
    --build-dir .aws-sam/build \
    --base-dir . \
    --parallel

# Verify ARM64 architecture in build artifacts
find .aws-sam/build -name "*.yaml" -exec grep -l "arm64" {} \;
```

### Step 3: Deploy Infrastructure

#### Development Deployment
```bash
sam deploy \
    --template-file template-arm64-optimized.yaml \
    --stack-name formbridge-arm64-dev \
    --parameter-overrides \
        Environment=dev \
        SecretPrefix=$SECRET_PREFIX \
        EventBusName=$EVENT_BUS_NAME \
        DynamoDBTableName=$DYNAMODB_TABLE_NAME \
    --capabilities CAPABILITY_IAM \
    --region $AWS_REGION \
    --confirm-changeset \
    --resolve-s3
```

#### Production Deployment
```bash
sam deploy \
    --template-file template-arm64-optimized.yaml \
    --stack-name formbridge-arm64-prod \
    --parameter-overrides \
        Environment=prod \
        SecretPrefix=$SECRET_PREFIX \
        EventBusName=$EVENT_BUS_NAME \
        DynamoDBTableName=$DYNAMODB_TABLE_NAME \
    --capabilities CAPABILITY_IAM \
    --region $AWS_REGION \
    --no-confirm-changeset \
    --resolve-s3
```

### Step 4: Configure Tenant Secrets

Create tenant secrets for HMAC authentication:
```bash
# Create tenant secret
TENANT_ID="t_example123"
SHARED_SECRET=$(openssl rand -hex 32)

aws secretsmanager create-secret \
    --name "${SECRET_PREFIX}/${TENANT_ID}" \
    --secret-string "{\"shared_secret\": \"${SHARED_SECRET}\"}" \
    --description "Shared secret for tenant ${TENANT_ID}" \
    --region $AWS_REGION

echo "Tenant ID: ${TENANT_ID}"
echo "Shared Secret: ${SHARED_SECRET}"
```

### Step 5: Test ARM64 Functions

#### Local Testing with SAM
```bash
# Start API locally with ARM64 emulation
sam local start-api \
    --template template-arm64-optimized.yaml \
    --parameter-overrides \
        Environment=dev \
        SecretPrefix=$SECRET_PREFIX \
        EventBusName=$EVENT_BUS_NAME \
    --docker-network host \
    --port 3000

# Test authorization endpoint
curl -X POST http://localhost:3000/submit \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: t_example123" \
    -H "X-Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -H "X-Signature: YOUR_CALCULATED_HMAC" \
    -d '{"form_id": "contact", "payload": {"name": "Test", "email": "test@example.com"}}'
```

#### Production Testing
```bash
# Get API endpoint from CloudFormation output
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name formbridge-arm64-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayEndpoint`].OutputValue' \
    --output text)

echo "API Endpoint: $API_ENDPOINT"

# Test with HMAC signature
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BODY='{"form_id": "test", "payload": {"test": "data"}}'
MESSAGE="${TIMESTAMP}\n${BODY}"
SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$SHARED_SECRET" -binary | xxd -p)

curl -X POST "${API_ENDPOINT}/submit" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: t_example123" \
    -H "X-Timestamp: $TIMESTAMP" \
    -H "X-Signature: $SIGNATURE" \
    -d "$BODY"
```

## ARM64 Performance Optimization

### Memory Optimization by Function Type

#### HMAC Authorizer (512MB - Recommended)
- Optimized for cryptographic operations
- ARM64 provides better SHA-256 performance
- Cold start time: ~800ms with Python 3.12

```bash
# Test authorizer performance
aws lambda invoke \
    --function-name formbridge-hmac-authorizer-dev \
    --payload '{}' \
    --log-type Tail \
    response.json

# Check duration and memory usage in CloudWatch
aws logs filter-log-events \
    --log-group-name /aws/lambda/formbridge-hmac-authorizer-dev \
    --start-time $(date -d '1 hour ago' +%s)000 \
    --filter-pattern "REPORT" \
    --query 'events[*].message'
```

#### Event Processor (768MB - Recommended)
- Handles JSON parsing and DynamoDB operations
- Higher memory improves JSON processing speed
- ARM64 reduces duration costs

```bash
# Monitor processor performance
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=formbridge-event-processor-dev \
    --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --period 300 \
    --statistics Average,Maximum
```

#### Smart Connector (1024MB - Recommended)
- HTTP operations and field transformations
- Higher memory reduces timeout risks
- Connection pooling benefits from persistent containers

### Connection Pooling Verification

Check connection reuse across invocations:
```bash
# Monitor connection pool metrics
aws logs filter-log-events \
    --log-group-name /aws/lambda/formbridge-smart-connector-dev \
    --start-time $(date -d '30 minutes ago' +%s)000 \
    --filter-pattern "HTTP client" \
    --query 'events[*].[eventId, message]' \
    --output table
```

## Cost Analysis and Monitoring

### Expected Cost Savings

Based on 1M monthly function invocations:

| Function Type | x86_64 Monthly Cost | ARM64 Monthly Cost | Savings |
|---------------|-------------------|------------------|---------|
| Authorizer (100ms avg) | $20.83 | $16.67 | $4.16 (20%) |
| Event Processor (200ms avg) | $41.67 | $33.33 | $8.34 (20%) |
| Smart Connector (500ms avg) | $104.17 | $83.33 | $20.84 (20%) |
| **Total Monthly** | **$166.67** | **$133.33** | **$33.34 (20%)** |

*Additional 17% savings available with Compute Savings Plans*

### Cost Monitoring Dashboard

Create CloudWatch dashboard to track costs:
```bash
# Create cost monitoring dashboard
aws cloudwatch put-dashboard \
    --dashboard-name "FormBridge-ARM64-Performance" \
    --dashboard-body file://arm64-dashboard.json
```

### Performance Benchmarking

Run performance tests to validate ARM64 benefits:
```bash
# Install artillery for load testing
npm install -g artillery

# Run load test against ARM64 functions
artillery run --target "$API_ENDPOINT" arm64-load-test.yml
```

Example load test configuration (`arm64-load-test.yml`):
```yaml
config:
  target: '{{ $processEnvironment.API_ENDPOINT }}'
  phases:
    - duration: 300
      arrivalRate: 10
      name: "Warm up"
    - duration: 600  
      arrivalRate: 50
      name: "Load test"
  variables:
    tenantId: "t_example123"
    sharedSecret: "{{ $processEnvironment.SHARED_SECRET }}"

scenarios:
  - name: "Submit form"
    weight: 100
    flow:
      - post:
          url: "/submit"
          beforeRequest: "setHMACHeaders"
          json:
            form_id: "load_test"
            payload:
              name: "Load Test User"
              email: "loadtest@example.com"
              message: "ARM64 performance testing"

functions:
  setHMACHeaders: |
    function(requestParams, context, ee, next) {
      const crypto = require('crypto');
      const timestamp = new Date().toISOString();
      const body = JSON.stringify(requestParams.json);
      const message = timestamp + '\n' + body;
      const signature = crypto.createHmac('sha256', context.vars.sharedSecret)
                             .update(message)
                             .digest('hex');
      
      requestParams.headers = {
        'X-Tenant-ID': context.vars.tenantId,
        'X-Timestamp': timestamp,
        'X-Signature': signature,
        'Content-Type': 'application/json'
      };
      
      return next();
    }
```

## Security and Compliance

### Multi-Tenant Isolation Verification

Test tenant isolation:
```bash
# Test cross-tenant access prevention
INVALID_TENANT="t_invalid999"

curl -X POST "${API_ENDPOINT}/submit" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: $INVALID_TENANT" \
    -H "X-Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -H "X-Signature: invalid_signature" \
    -d '{"test": "cross_tenant_attempt"}' \
    -w "\nHTTP Status: %{http_code}\n"

# Expected: HTTP Status 401 (Unauthorized)
```

### Security Layer Validation

Verify security layer functionality:
```bash
# Check layer deployment
aws lambda list-layers \
    --query 'Layers[?contains(LayerName, `formbridge-mt-security`)]' \
    --output table

# Test HMAC validation functions
python3 -c "
from tenant_auth import HMACValidator, ValidationResult
import json

validator = HMACValidator('formbridge')
result = validator.validate_request(
    tenant_id='t_example123',
    timestamp='$(date -u +%Y-%m-%dT%H:%M:%SZ)',
    signature='test_signature',
    body='{\"test\": \"data\"}'
)
print(f'Validation Status: {result.status.value}')
"
```

## Monitoring and Observability

### ARM64 Performance Metrics

Key metrics to monitor:
1. **Duration** - Should be 15-20% lower than x86_64
2. **Cold Start Time** - Target <1s for Python 3.12
3. **Memory Utilization** - Right-sized per function
4. **Error Rate** - Should remain <0.1%
5. **Cost per Invocation** - 20% reduction

### CloudWatch Alarms

Set up ARM64-specific alarms:
```bash
# Create performance alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "FormBridge-ARM64-HighDuration" \
    --alarm-description "ARM64 function duration exceeding baseline" \
    --metric-name Duration \
    --namespace AWS/Lambda \
    --statistic Average \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 1000 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=formbridge-event-processor-dev \
    --alarm-actions arn:aws:sns:us-east-1:123456789012:formbridge-alerts

# Create cost anomaly alarm  
aws cloudwatch put-metric-alarm \
    --alarm-name "FormBridge-ARM64-UnexpectedCosts" \
    --alarm-description "ARM64 costs higher than expected" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 86400 \
    --evaluation-periods 1 \
    --threshold 100 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=Currency,Value=USD \
    --alarm-actions arn:aws:sns:us-east-1:123456789012:formbridge-cost-alerts
```

### X-Ray Tracing

Enable detailed tracing for ARM64 performance analysis:
```bash
# View traces for performance analysis
aws xray get-trace-summaries \
    --time-range-type TimeRangeByStartTime \
    --start-time $(date -d '1 hour ago' +%s) \
    --end-time $(date +%s) \
    --filter-expression "service(\"formbridge\")" \
    --query 'TraceSummaries[*].[Id, Duration, ResponseTime]' \
    --output table
```

## Troubleshooting

### Common ARM64 Issues

1. **Native Dependencies**
   ```bash
   # Check for x86_64 dependencies in layers
   find .aws-sam/build -name "*.so" -exec file {} \;
   
   # Should show: "ARM aarch64" for ARM64 compatibility
   ```

2. **Cold Start Performance**
   ```bash
   # Monitor cold start metrics
   aws logs filter-log-events \
       --log-group-name /aws/lambda/formbridge-hmac-authorizer-dev \
       --filter-pattern "INIT_START" \
       --query 'events[*].message'
   ```

3. **Memory Optimization**
   ```bash
   # Check memory usage patterns
   aws logs filter-log-events \
       --log-group-name /aws/lambda/formbridge-event-processor-dev \
       --filter-pattern "Max Memory Used" \
       --query 'events[*].message'
   ```

### Performance Testing Commands

```bash
# Compare ARM64 vs x86_64 performance
./scripts/performance-comparison.sh

# Load test ARM64 functions
./scripts/arm64-load-test.sh

# Cost analysis report
./scripts/cost-analysis.sh
```

## Migration from x86_64

If migrating existing x86_64 functions:

1. **Backup Current Configuration**
   ```bash
   aws lambda get-function --function-name your-function > function-backup.json
   ```

2. **Deploy ARM64 Version Alongside**
   ```bash
   # Deploy with different name for testing
   sam deploy --parameter-overrides Environment=arm64-test
   ```

3. **Gradual Traffic Shift**
   ```bash
   # Use Lambda aliases for weighted routing
   aws lambda create-alias \
       --function-name formbridge-processor \
       --name live \
       --function-version $LATEST \
       --routing-config AdditionalVersionWeights={"2"=0.1}
   ```

## Success Metrics

After deployment, verify:
- ✅ 20% cost reduction in Lambda billing
- ✅ Improved performance metrics
- ✅ Sub-1s cold start times
- ✅ Multi-tenant security functioning
- ✅ All integration tests passing
- ✅ Error rates below 0.1%

---

## Support and Resources

- **AWS ARM64 Documentation**: https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html
- **Graviton Performance Guide**: https://github.com/aws/aws-graviton-getting-started
- **Lambda Powertools**: https://docs.powertools.aws.dev/lambda/python/latest/
- **Form-Bridge Documentation**: `/docs/`

For issues or questions, check the troubleshooting section or create an issue in the project repository.
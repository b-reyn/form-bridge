# Form-Bridge MVP Architecture

**Simplified Design for Fast Deployment**

*Last Updated: January 26, 2025*
*Status: MVP Ready for Deployment*

## Overview

This document describes the **simplified MVP architecture** for Form-Bridge, designed to deploy in under 10 minutes with proven reliability. The MVP removes complexity while maintaining core functionality for multi-tenant form ingestion and processing.

## Architecture Principles (MVP)

1. **Deploy First, Optimize Later**: Get working functionality quickly
2. **Proven Technologies**: Use standard AWS services with minimal configuration
3. **Fast Builds**: x86_64 architecture, minimal dependencies
4. **Simple Authentication**: API keys instead of complex HMAC
5. **Basic Monitoring**: CloudWatch logs and basic metrics

## High-Level Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│ API Gateway │───▶│   Lambda    │
│ (WordPress, │    │ + Authorizer│    │   Ingest    │
│  webhooks)  │    │             │    │             │
└─────────────┘    └─────────────┘    └─────┬───────┘
                                             │ Store & Publish
                                             ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ EventBridge │◀───│  DynamoDB   │
                   │   Events    │    │   Storage   │
                   └─────┬───────┘    └─────────────┘
                         │ Route Events
                         ▼
                   ┌─────────────┐
                   │   Lambda    │
                   │  Processor  │
                   │             │
                   └─────────────┘
```

## Core Components

### 1. API Gateway + Lambda Authorizer
**Purpose**: Validate requests and route to ingestion Lambda

**MVP Simplifications**:
- **HTTP API** (not REST API) for lower latency and cost
- **API Key authentication** instead of HMAC-SHA256
- **Simple tenant validation** against Secrets Manager
- **Basic rate limiting** via API Gateway throttling

**Configuration**:
```yaml
HttpApi:
  Auth:
    Authorizers:
      LambdaAuth:
        FunctionArn: !GetAtt ApiAuthorizerFunction.Arn
        AuthorizerPayloadFormatVersion: '2.0'
        EnableSimpleResponses: true
```

### 2. Ingestion Lambda (mvp-ingest-handler.py)
**Purpose**: Process incoming form submissions and publish events

**MVP Features**:
- Validate `X-Tenant-ID` and `X-API-Key` headers
- Generate unique submission ID (UUIDv4)
- Store submission in DynamoDB with tenant prefix
- Publish event to EventBridge for processing
- Return success response with submission ID

**Simplified Processing**:
```python
def lambda_handler(event, context):
    # 1. Extract tenant from authorizer context
    # 2. Parse and validate form data
    # 3. Store in DynamoDB: TENANT#{tenant_id}#SUB#{submission_id}
    # 4. Publish to EventBridge
    # 5. Return submission ID
```

### 3. DynamoDB Table (Single Table Design)
**Purpose**: Store all form submissions with multi-tenant isolation

**MVP Schema**:
- **PK**: `TENANT#{tenant_id}`
- **SK**: `SUB#{submission_id}#{timestamp}`
- **Attributes**: `form_data`, `form_type`, `status`, `created_at`, `processed_at`

**Key Simplifications**:
- **On-demand billing** (no provisioned capacity planning)
- **Simple partition key structure** (no complex access patterns)
- **Basic GSI** for time-based queries (optional)
- **No TTL** initially (can add later)

### 4. EventBridge + Processing Lambda
**Purpose**: Route submission events to processors

**MVP Event Flow**:
1. Ingestion Lambda publishes `submission.received` event
2. EventBridge routes to processing Lambda
3. Processing Lambda updates submission status to `processed`

**Event Schema** (Simplified):
```json
{
  "source": "form-bridge.ingest",
  "detail-type": "submission.received",
  "detail": {
    "tenant_id": "t_sample",
    "submission_id": "sub_xxxxxxxxxx",
    "form_type": "contact",
    "timestamp": "2025-01-26T12:00:00Z"
  }
}
```

## Removed Complexities (Full Version)

### What We Simplified Away
1. **HMAC Authentication**: Replaced with API keys for faster implementation
2. **ARM64 Architecture**: Using x86_64 for faster builds and compatibility
3. **Step Functions**: Direct Lambda processing instead of orchestration
4. **Complex IAM**: Minimal permissions, no cross-account complexity  
5. **PowerTools Integration**: Basic logging instead of structured observability
6. **Multiple Connectors**: Single processor Lambda instead of connector framework
7. **Advanced Monitoring**: CloudWatch logs instead of X-Ray and custom metrics
8. **Schema Validation**: Basic validation instead of JSON Schema
9. **Rate Limiting**: API Gateway limits instead of per-tenant quotas
10. **Dead Letter Queues**: Basic error handling instead of DLQ processing

### What We Kept Essential
- Multi-tenant data isolation
- Event-driven architecture  
- Serverless scaling
- Basic monitoring
- Error logging
- Secure credential storage

## Deployment Components

### SAM Template (template-mvp-fast-deploy.yaml)
```yaml
# Simplified SAM template with:
- HttpApi with Lambda Authorizer
- 3 Lambda Functions (minimal dependencies)
- DynamoDB Table (on-demand)
- EventBridge Rule
- Secrets Manager for tenant config
- CloudWatch Log Groups
- Basic IAM Roles
```

### Lambda Functions (x86_64, Python 3.12)
1. **mvp-api-authorizer.py**: API key validation (128MB memory)
2. **mvp-ingest-handler.py**: Form processing (256MB memory)  
3. **mvp-event-processor.py**: Event handling (256MB memory)

### Dependencies (Minimal)
- **boto3**: AWS SDK (included in Lambda runtime)
- **json**: JSON processing (Python standard library)
- **uuid**: ID generation (Python standard library)
- **datetime**: Timestamp handling (Python standard library)

## Performance Characteristics

### Expected Performance (MVP)
- **Cold Start**: < 2 seconds (x86_64, minimal deps)
- **Warm Response**: < 200ms
- **Throughput**: ~1000 requests/minute per Lambda
- **Cost**: ~$20-50/month for 100K submissions

### Scaling Limits (MVP)
- **API Gateway**: 10,000 requests/second
- **Lambda Concurrent Executions**: 3000 (default)
- **DynamoDB**: 40,000 read/write units on-demand
- **EventBridge**: 2,400 events/second per rule

## Monitoring (Basic)

### CloudWatch Logs
- **API Gateway**: Access logs enabled
- **Lambda Functions**: DEBUG level logging
- **Authorizer**: Authentication success/failure logs

### CloudWatch Metrics (Automatic)
- Lambda invocation count, errors, duration
- API Gateway 4xx/5xx errors, latency
- DynamoDB consumed capacity, throttling

### Basic Alarms
- Lambda error rate > 1%
- API Gateway 5xx rate > 0.1%
- DynamoDB throttling events

## Security Model (MVP)

### Authentication Flow
1. Client sends request with `X-Tenant-ID` and `X-API-Key` headers
2. API Gateway invokes Lambda Authorizer
3. Authorizer validates tenant exists in Secrets Manager
4. Authorizer compares API key with stored value
5. On success, passes tenant context to ingestion Lambda

### Multi-Tenant Isolation
- All DynamoDB keys prefixed with `TENANT#{tenant_id}`
- Authorizer validates tenant access before processing
- Each tenant has unique API key in Secrets Manager
- No cross-tenant data access possible

### Stored Credentials
```json
// In AWS Secrets Manager: formbridge/tenants/{tenant_id}
{
  "api_key": "mvp-test-key-123",
  "tenant_name": "Sample Tenant",
  "created_at": "2025-01-26T12:00:00Z"
}
```

## Cost Estimation (MVP Usage)

### Monthly Costs (100K submissions)
- **API Gateway**: ~$0.35 (100K requests)
- **Lambda**: ~$8.40 (compute time)
- **DynamoDB**: ~$12.50 (on-demand)
- **EventBridge**: ~$0.10 (100K events)
- **CloudWatch**: ~$2.00 (logs)
- **Secrets Manager**: ~$0.40 (1 secret)
- **Total**: ~$23.75/month

### Scaling Cost (1M submissions)
- **Total**: ~$95/month (roughly 4x scaling)

## Upgrade Path to Full Architecture

### Phase 2: Enhanced Security
1. Implement HMAC-SHA256 authentication
2. Add request signing validation
3. Implement per-tenant rate limiting
4. Add API key rotation capability

### Phase 3: Performance Optimization
1. Migrate to ARM64 Graviton2 processors
2. Implement connection pooling
3. Add DynamoDB provisioned capacity optimization
4. Implement payload compression

### Phase 4: Advanced Features  
1. Add Step Functions orchestration
2. Implement webhook delivery connectors
3. Add dead letter queue processing
4. Build admin UI dashboard

### Phase 5: Enterprise Features
1. Multi-region deployment
2. Advanced monitoring with X-Ray
3. Automated backup and disaster recovery
4. Compliance and audit logging

## Testing Strategy (MVP)

### Deployment Validation
```bash
# 1. Deploy stack
./scripts/quick-deploy.sh

# 2. Test ingestion endpoint
curl -X POST $API_ENDPOINT/submit \
  -H "X-Tenant-ID: t_sample" \
  -H "X-API-Key: mvp-test-key-123" \
  -d '{"form_data": {"email": "test@example.com"}}'

# 3. Verify data in DynamoDB
aws dynamodb scan --table-name formbridge-mvp-dev

# 4. Check processing logs
aws logs tail /aws/lambda/formbridge-mvp-processor-dev
```

### Load Testing (Basic)
```bash
# Simple load test with curl
for i in {1..100}; do
  curl -X POST $API_ENDPOINT/submit \
    -H "X-Tenant-ID: t_sample" \
    -H "X-API-Key: mvp-test-key-123" \
    -d "{\"test_id\": $i}" &
done
```

## Operational Runbook (MVP)

### Common Operations

**Add New Tenant**:
```bash
aws secretsmanager create-secret \
  --name "formbridge/tenants/t_new_tenant" \
  --secret-string '{"api_key": "new-api-key-456", "tenant_name": "New Tenant"}'
```

**View Submissions**:
```bash
aws dynamodb query \
  --table-name formbridge-mvp-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "TENANT#t_sample"}}'
```

**Monitor Errors**:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/formbridge-mvp-ingest-dev \
  --filter-pattern "ERROR"
```

### Troubleshooting

**403 Unauthorized Errors**:
1. Check tenant exists in Secrets Manager
2. Verify API key matches stored value  
3. Check Lambda authorizer logs

**500 Internal Server Errors**:
1. Check Lambda function logs
2. Verify DynamoDB table exists and has correct permissions
3. Check EventBridge rule configuration

**High Latency**:
1. Monitor CloudWatch metrics for Lambda cold starts
2. Check DynamoDB throttling metrics
3. Review API Gateway caching settings

## Conclusion

This MVP architecture prioritizes deployment speed and operational simplicity over advanced features. It provides a solid foundation for form ingestion that can be incrementally enhanced as requirements grow.

**Next Steps**:
1. Deploy using the [Quick Start Guide](QUICK-START.md)
2. Test with sample tenant configuration
3. Monitor basic metrics and logs
4. Plan incremental feature additions based on usage patterns

The simplified design removes complexity barriers while maintaining essential functionality for multi-tenant form processing at scale.
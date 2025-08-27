# Form-Bridge MVP - Quick Deploy

Simplified Lambda functions for fast deployment, prioritizing "working first, optimize later".

## What's Different in MVP

### ✅ Simplified for Speed
- **x86_64 architecture** (no ARM64 build delays)
- **Minimal dependencies** (just boto3)
- **Basic API key auth** (no complex HMAC)
- **Simple error handling** (no PowerTools)
- **Fast builds** (< 2 minutes)

### 🚀 Quick Deployment

```bash
# Deploy MVP stack
./scripts/mvp-deploy.sh dev

# Test the deployment
python3 scripts/test-mvp.py https://your-api-id.execute-api.region.amazonaws.com/dev
```

## MVP Lambda Functions

### 1. `mvp-ingest-handler.py`
- Accepts form submissions via POST /submit
- Validates X-Tenant-ID and X-API-Key headers
- Stores in DynamoDB with simple schema
- Publishes to EventBridge
- Returns submission ID

### 2. `mvp-event-processor.py` 
- Processes EventBridge events
- Updates submission status to "processed"
- Simple logging and error handling
- Ready for webhook/connector expansion

### 3. `mvp-api-authorizer.py`
- Lambda authorizer for API Gateway
- Validates tenant exists in Secrets Manager
- Simple API key comparison
- Returns tenant context for downstream functions

## Quick Test

```bash
# Test form submission
curl -X POST https://your-api.execute-api.region.amazonaws.com/dev/submit \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: t_sample" \
  -H "X-API-Key: mvp-test-key-123" \
  -d '{
    "form_data": {
      "name": "Test User", 
      "email": "test@example.com"
    },
    "form_type": "contact"
  }'
```

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│ API Gateway │───▶│   Lambda    │
│             │    │ + Authorizer│    │   Ingest    │
└─────────────┘    └─────────────┘    └─────┬───────┘
                                             │
                   ┌─────────────┐           ▼
                   │ EventBridge │◀──────────────────
                   │   Events    │           │
                   └─────┬───────┘           ▼
                         │            ┌─────────────┐
                         ▼            │  DynamoDB   │
                   ┌─────────────┐    │   Storage   │
                   │   Lambda    │    └─────────────┘
                   │  Processor  │
                   └─────────────┘
```

## Cost Estimate (MVP)
- **Lambda**: ~$0.20 per million requests
- **DynamoDB**: On-demand pricing
- **API Gateway**: $3.50 per million requests
- **Total**: < $10/month for light testing

## What's Missing (Future)
- HMAC authentication
- ARM64 optimization
- Comprehensive monitoring
- Input validation
- Rate limiting
- Webhook connectors
- Admin UI

## Troubleshooting

### Build Timeouts
MVP uses x86_64 and minimal dependencies to avoid build issues.

### Authorization Errors
Check that tenant secret exists:
```bash
aws secretsmanager get-secret-value --secret-id formbridge/tenants/t_sample
```

### DynamoDB Access
Verify Lambda has DynamoDB permissions and table exists:
```bash
aws dynamodb describe-table --table-name formbridge-mvp-dev
```

### Logs
Monitor Lambda logs:
```bash
aws logs tail /aws/lambda/formbridge-mvp-ingest-dev --follow
aws logs tail /aws/lambda/formbridge-mvp-processor-dev --follow
```

## Next Steps After MVP Works

1. **Add HMAC Authentication**: Replace API key with HMAC-SHA256
2. **ARM64 Migration**: Switch to Graviton2 for cost savings
3. **PowerTools Integration**: Add structured logging and metrics
4. **Input Validation**: Add JSON schema validation
5. **Webhook Connectors**: Add delivery to external systems
6. **Admin UI**: Build management dashboard
7. **Load Testing**: Validate performance at scale

---

**Remember**: This is MVP - prioritize deployment success over perfection!
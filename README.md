# Form-Bridge

**Cost-Optimized Serverless Form Ingestion Platform**

**Start with $0/month deployment, scale when needed.**

## Choose Your Approach

Form-Bridge offers two architectures to match your needs and budget:

### 🚀 Ultra-Simple Architecture (RECOMMENDED)
**Perfect for testing, learning, and small projects**
- **Cost**: $0.00/month (AWS Free Tier)
- **Deploy time**: 2 minutes  
- **Complexity**: Single Lambda function
- **Best for**: Testing ideas, personal projects, <1K requests/month

[**→ Get Started with Ultra-Simple ($0/month)**](architectures/ultra-simple/README.md)

### 🏢 Enterprise Architecture
**Full-featured for production and growth**
- **Cost**: $25-55/month
- **Deploy time**: 10+ minutes
- **Complexity**: Multi-tenant, EventBridge, Step Functions
- **Best for**: Production apps, >10K requests/month, complex workflows

[**→ Enterprise Architecture Guide**](architectures/enterprise/README.md)

## Overview

Form-Bridge ingests form submissions from WordPress, webhooks, and other sources, then reliably delivers them to configured destinations. Choose the architecture that matches your current needs - you can always migrate from ultra-simple to enterprise when you're ready to scale.

## Architecture Comparison

| Feature | Ultra-Simple | Enterprise |
|---------|-------------|------------|
| **Monthly Cost** | $0.00 (free tier) | $25-55 |
| **Deploy Time** | 2 minutes | 10+ minutes |
| **Complexity** | Single function | Multi-service |
| **Request Limit** | ~1M/month (free) | Unlimited |
| **Multi-tenant** | No | Yes |
| **Event Processing** | Synchronous | Asynchronous |
| **Monitoring** | Basic CloudWatch | Advanced dashboards |
| **Best For** | Testing, learning | Production, scale |

**New to Form-Bridge?** Start with ultra-simple → migrate when needed.

**Need production features now?** Jump to enterprise architecture.

### Ultra-Simple Architecture
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  WordPress  │───▶│ Lambda URL   │───▶│  DynamoDB   │
│   Plugin    │    │ (Free)       │    │ (Free Tier) │
└─────────────┘    └──────────────┘    └─────────────┘
```

### Enterprise Architecture  
```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  WordPress  │───▶│ API Gateway │───▶│ EventBridge  │───▶│ Step Functions
│   Plugin    │    │             │    │              │    │ + DynamoDB  │
└─────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
```

## Quick Start

### 🚀 Ultra-Simple Deployment (Recommended for New Users)
```bash
# 2-minute deployment to AWS Free Tier
cd architectures/ultra-simple
./deploy.sh test

# Test the deployment
python test_client.py https://your-function-url.lambda-url.region.on.aws/
```
**→ Complete guide**: [Ultra-Simple Setup](architectures/ultra-simple/README.md)

### 🏢 Enterprise Deployment (Production Ready)
```bash
# Full-featured deployment
cd architectures/enterprise  
sam build && sam deploy --guided

# Validate deployment
cd ../../tools/testing
python integration-test.py
```
**→ Complete guide**: [Enterprise Setup](architectures/enterprise/README.md)

### 🔄 Migration Path
Started with ultra-simple and need more features?

**→ Migration guide**: [Ultra-Simple to Enterprise](docs/getting-started/migration-guide.md)

## Repository Structure

```
form-bridge/
├── architectures/              # Architecture-specific implementations
│   ├── ultra-simple/          # $0/month architecture (RECOMMENDED START)
│   │   ├── README.md          # 2-minute setup guide
│   │   ├── handler.py         # Single Lambda function  
│   │   ├── template.yaml      # Free tier optimized
│   │   ├── deploy.sh          # One-command deployment
│   │   └── test_client.py     # Cost calculator + testing
│   └── enterprise/            # Production architecture
│       ├── infrastructure/    # CDK/SAM templates
│       ├── services/         # Multi-tenant Lambda functions
│       ├── shared/           # Common libraries
│       └── dashboard/        # Admin UI
├── plugins/                   # Platform integrations
│   └── wordpress/            # WordPress plugin (both architectures)
├── tools/                     # Development utilities  
│   ├── deployment/           # Deployment scripts
│   ├── testing/              # Test utilities
│   └── monitoring/           # Cost monitoring
├── docs/                      # Comprehensive documentation
│   ├── getting-started/      # Quick start guides
│   ├── architecture/         # Design documentation
│   └── strategies/           # Implementation strategies
└── tests/                     # Cross-architecture tests
```

## Essential Documentation

### 🚀 New to Form-Bridge? Start Here:
- [**Ultra-Simple Guide**](architectures/ultra-simple/README.md) - $0/month, 2-minute deploy
- [**Cost Comparison**](docs/architecture/cost-analysis.md) - Detailed cost breakdown  
- [**WordPress Integration**](plugins/wordpress/README.md) - Works with both architectures

### 🏢 Ready for Production?
- [**Enterprise Architecture**](architectures/enterprise/README.md) - Full features
- [**Migration Guide**](docs/getting-started/migration-guide.md) - Scale from ultra-simple
- [**Multi-Tenant Setup**](docs/security/README.md) - Enterprise security

### 📚 Complete Documentation
- [**Documentation Hub**](docs/README.md) - All guides organized
- [**Architecture Decisions**](docs/architecture/decisions/) - Why we built it this way
- [**Troubleshooting**](docs/TROUBLESHOOTING.md) - Common issues

### 🛠️ Development Resources  
- [**Repository Strategy**](docs/strategies/repo_strategy.md) - File organization
- [**Testing Guide**](docs/testing/README.md) - Quality assurance
- [**Contributing**](docs/guides/README.md) - Development workflow

## Current Status

### 🚀 Ultra-Simple Architecture (Ready)
- **Single Lambda function** ✅ - Zero complexity
- **Lambda Function URLs** ✅ - No API Gateway costs  
- **Free tier optimized** ✅ - $0.00/month for testing
- **2-minute deployment** ✅ - One command setup
- **WordPress integration** ✅ - Drop-in plugin compatibility

### 🏢 Enterprise Architecture (Ready)
- **Multi-tenant isolation** ✅ - Production security
- **EventBridge routing** ✅ - Async processing
- **Step Functions workflows** ✅ - Complex orchestration
- **Advanced monitoring** ✅ - Full observability
- **Auto-scaling** ✅ - Handle any load

**→ Next: Choose your architecture and deploy!**

## Feature Comparison

### Ultra-Simple Features
✅ **Single-tenant** - Perfect for personal/small projects  
✅ **HMAC authentication** - Secure without complexity  
✅ **Direct Lambda URLs** - No API Gateway costs  
✅ **DynamoDB on-demand** - Pay only for what you use  
✅ **CloudWatch basics** - Essential monitoring included  
✅ **TTL auto-cleanup** - Automatic data expiration  

### Enterprise Features (All ultra-simple features plus...)
✅ **Multi-tenant isolation** - Data separation per customer  
✅ **EventBridge routing** - Asynchronous event processing  
✅ **Step Functions** - Complex workflow orchestration  
✅ **API Gateway** - Advanced rate limiting, caching  
✅ **Advanced monitoring** - X-Ray tracing, custom metrics  
✅ **Admin dashboard** - Full management UI  
✅ **Webhook connectors** - Integrate with external systems  
✅ **Load balancing** - Handle high traffic automatically  

### Security (Both Architectures)
✅ **HTTPS encryption** - All data encrypted in transit  
✅ **IAM roles** - Minimal permissions principle  
✅ **Secrets Manager** - No hardcoded credentials  
✅ **Request validation** - Input sanitization included  

## Performance Benchmarks

### Ultra-Simple Architecture
- **API Response**: < 200ms (direct Lambda)
- **Deployment Time**: 2 minutes
- **Cold Start**: < 1 second  
- **Monthly Cost**: $0.00 (up to 1M requests in free tier)
- **Scalability**: 1M requests/month max (free tier limit)

### Enterprise Architecture  
- **API Response**: < 200ms p99 (with API Gateway caching)
- **Deployment Time**: 10-15 minutes (full stack)
- **Cold Start**: < 1 second (provisioned concurrency available)
- **Monthly Cost**: $25-55 for 100K submissions
- **Scalability**: Unlimited (auto-scaling)

### When to Migrate
Move from ultra-simple to enterprise when you need:
- More than 1M requests/month consistently
- Multi-tenant customer isolation 
- Complex workflow orchestration
- Advanced monitoring and alerting
- Integration with multiple external systems

## Migration Path: Ultra-Simple → Enterprise

Ready to scale? Here's your upgrade path:

### Phase 1: Data Migration (Zero Downtime)
1. **Export data** from ultra-simple DynamoDB table
2. **Import data** into enterprise multi-tenant structure  
3. **Run both systems** in parallel during transition
4. **Switch traffic** gradually to enterprise endpoints

### Phase 2: Feature Activation
1. **Multi-tenant setup**: Configure customer isolation
2. **EventBridge routing**: Enable asynchronous processing
3. **Step Functions**: Add complex workflow orchestration
4. **Advanced monitoring**: Activate X-Ray tracing and dashboards

### Phase 3: Enterprise Features
1. **Admin dashboard**: Deploy management UI
2. **Webhook connectors**: Integrate external systems
3. **Rate limiting**: Configure API Gateway policies
4. **Custom domains**: Set up branded endpoints

**→ Detailed migration guide**: [docs/getting-started/migration-guide.md](docs/getting-started/migration-guide.md)

## Testing Your Deployment

### Ultra-Simple Testing
```bash
# Use the built-in test client
cd architectures/ultra-simple
python test_client.py https://your-function-url.lambda-url.region.on.aws/

# Or test with curl (HMAC signature required)
TIMESTAMP=$(date +%s)
BODY='{"form_data":{"name":"Test","email":"test@example.com"}}'
SIGNATURE=$(echo -n "${TIMESTAMP}:${BODY}" | openssl dgst -sha256 -hmac "your-secret" | cut -d' ' -f2)

curl -X POST https://your-function-url.lambda-url.region.on.aws/ \
  -H "Content-Type: application/json" \
  -H "X-Signature: ${SIGNATURE}" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -d "${BODY}"
```

### Enterprise Testing
```bash
# Multi-tenant API testing
curl -X POST https://YOUR_API_ENDPOINT/submit \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: t_sample" \
  -H "X-API-Key: enterprise-key-123" \
  -d '{"form_data": {"name": "Test User", "email": "test@example.com"}, "form_type": "contact"}'

# Expected response:
# {"status": "success", "submission_id": "sub_xxxxxxxxxx", "tenant_id": "t_sample"}
```

## Development Workflow

### For New Projects (Recommended)
1. **Start ultra-simple**: Deploy $0/month architecture in 2 minutes
2. **Integrate WordPress**: Configure plugin with Lambda URL
3. **Test thoroughly**: Validate form submission flow works
4. **Monitor usage**: Track requests and costs
5. **Scale when ready**: Migrate to enterprise when you need advanced features

### For Production Projects
1. **Deploy enterprise**: Full-featured architecture from start
2. **Configure tenants**: Set up multi-tenant isolation
3. **Enable monitoring**: Activate advanced CloudWatch dashboards
4. **Load test**: Validate performance under expected traffic
5. **Go live**: Switch DNS to production endpoints

### Development Best Practices
- **Version control**: All deployments through git
- **Testing**: Both unit and integration tests
- **Monitoring**: Set up alerts before going live
- **Documentation**: Keep architecture decisions documented
- **Cost tracking**: Monitor AWS billing closely

## Troubleshooting

**Common deployment issues:**
- AWS credentials not configured → Run `aws configure`
- SAM CLI not installed → Run `pip install aws-sam-cli`
- Stack deployment timeout → Check CloudFormation events
- API returns 403 → Verify tenant configuration in Secrets Manager

See [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for complete solutions.

## Next Steps

### 🚀 New Users: Start Ultra-Simple
1. **Deploy in 2 minutes**: `cd architectures/ultra-simple && ./deploy.sh test`
2. **Test with client**: `python test_client.py [your-lambda-url]`
3. **Integrate WordPress**: Update plugin with your Lambda URL
4. **Monitor costs**: Check AWS Free Tier usage
5. **Scale when ready**: Follow migration guide to enterprise

### 🏢 Production Users: Enterprise Setup
1. **Plan architecture**: Review [enterprise architecture guide](architectures/enterprise/README.md)
2. **Configure tenants**: Set up multi-tenant isolation
3. **Deploy full stack**: `cd architectures/enterprise && sam deploy --guided`
4. **Enable monitoring**: Activate CloudWatch dashboards
5. **Load test**: Validate performance expectations

### 🔄 Migration Users: Scale Up
1. **Read migration guide**: [docs/getting-started/migration-guide.md](docs/getting-started/migration-guide.md)
2. **Export existing data**: Backup ultra-simple submissions
3. **Deploy enterprise**: Run both systems in parallel
4. **Switch traffic**: Gradual cutover to enterprise endpoints
5. **Decommission**: Remove ultra-simple stack

### 📞 Support
- **Documentation**: [docs/](docs/) - Comprehensive guides
- **Issues**: GitHub Issues - Bug reports and feature requests
- **Architecture Questions**: [docs/architecture/decisions/](docs/architecture/decisions/) - Design rationale
- **Cost Questions**: [docs/architecture/cost-analysis.md](docs/architecture/cost-analysis.md) - Detailed cost breakdown

---

## Architecture Philosophy

**Start Simple**: Ultra-simple architecture gets you running in 2 minutes at $0/month  
**Scale Intentionally**: Enterprise architecture when you need advanced features  
**Preserve Optionality**: Easy migration path preserves your investment  

**Choose the right architecture for your current needs, not your future aspirations.**

---

*Form-Bridge: Cost-optimized serverless form processing that scales from $0 to enterprise.*
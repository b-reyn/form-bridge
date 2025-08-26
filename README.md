# Form-Bridge

**Multi-Tenant Serverless Form Ingestion & Fan-Out System**

## Overview

Form-Bridge is a serverless platform that ingests form submissions from multiple sources (WordPress, Shopify, webhooks) and reliably delivers them to configured destinations (webhooks, CRMs, databases) with enterprise-grade security and multi-tenant isolation.

## Architecture

Built on AWS using EventBridge-centric architecture:
- **Ingestion**: API Gateway + Lambda with HMAC authentication
- **Processing**: EventBridge for routing and orchestration
- **Storage**: DynamoDB with single-table design for multi-tenancy
- **Delivery**: Step Functions orchestrating connector Lambdas
- **Management**: React dashboard with Cognito authentication

See [Architecture Documentation](docs/mvp/architecture.md) for details.

## Quick Start

### Prerequisites
- AWS Account with appropriate permissions
- Node.js 18+ and Python 3.11+
- Docker for local development
- AWS CLI configured

### Development Setup

```bash
# Clone repository
git clone https://github.com/your-org/form-bridge.git
cd form-bridge

# Run in Docker (recommended)
docker compose up -d
docker compose exec app bash

# Install dependencies
npm install
pip install -r requirements.txt

# Run tests
npm test
pytest tests/

# Deploy to AWS
sam build
sam deploy --guided
```

## Project Structure

```
form-bridge/
├── services/           # Lambda functions by domain
├── dashboard/          # React admin interface  
├── plugins/           # Platform integrations (WordPress, etc.)
├── infrastructure/    # IaC templates (SAM/CDK)
├── shared/           # Shared libraries
├── tests/            # Integration & E2E tests
└── docs/             # Documentation
```

See [Repository Strategy](docs/strategies/repo_strategy.md) for detailed structure.

## Documentation

- [**Documentation Index**](docs/README.md) - Complete documentation map
- [**MVP Documentation**](docs/mvp/README.md) - Current implementation
- [**Agent Strategies**](docs/strategies/) - Domain-specific knowledge
- [**CLAUDE.md**](CLAUDE.md) - AI assistant context

## Current Status

**Phase 1: Foundation & Infrastructure** (In Progress)
- Core Lambda functions ✅
- EventBridge setup ✅
- DynamoDB design 🔧
- Security implementation 🔴

See [Implementation Phases](docs/mvp/phases.md) for roadmap.

## Key Features

### Multi-Tenant Architecture
- Complete data isolation between tenants
- Per-tenant configuration and secrets
- Tenant-specific rate limiting
- Audit logging per tenant

### Reliability
- Built-in retry logic with exponential backoff
- Dead letter queues for failed deliveries
- Event replay capability
- Comprehensive monitoring

### Security
- HMAC signature validation
- JWT authentication for admin access
- Encryption at rest and in transit
- Least-privilege IAM roles

### Scalability
- Serverless auto-scaling
- Event-driven architecture
- Cost-optimized for 0 to millions of events
- Multi-region ready

## Performance Targets

- **API Response**: < 200ms p99
- **End-to-end Processing**: < 5 seconds
- **Availability**: 99.9% uptime
- **Cost**: < $100/month for 1M submissions

## Security

See [Security Documentation](docs/CRITICAL_SECURITY_IMPLEMENTATION_PLAN.md) for security implementation details and [Security Audit](docs/comprehensive-security-audit-jan-2025.md) for latest assessment.

**Report Security Issues**: security@your-org.com

## Contributing

This project uses AI-assisted development with Claude Code. Each specialist maintains their domain strategy in `docs/strategies/`.

### Development Workflow
1. Check relevant strategy documents
2. Research current best practices
3. Implement with test-first approach
4. Update strategy documents with learnings

## Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests  
pytest tests/integration/

# Load tests
npm run test:load

# Security scan
npm audit
safety check
```

## Deployment

### Development
```bash
sam deploy --stack-name form-bridge-dev --parameter-overrides Environment=dev
```

### Production
```bash
sam deploy --stack-name form-bridge-prod --parameter-overrides Environment=prod
```

See [Deployment Guide](docs/mvp/implementation/arm64-deployment.md) for ARM64 optimization.

## Support

- Documentation: [docs/](docs/)
- Issues: GitHub Issues
- Slack: #form-bridge-support

## License

Copyright (c) 2025 Your Organization. All rights reserved.

---

*Built with ❤️ using serverless AWS services and AI-assisted development*
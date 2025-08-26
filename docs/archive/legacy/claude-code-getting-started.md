# Getting Started with Claude Code - Form-Bridge MVP

*Version: 1.0 | Date: January 26, 2025*  
*Goal: Zero to Deployed MVP with WordPress Plugin Integration*

## 🎯 MVP Success Criteria
- WordPress plugin installed and capturing forms
- Forms posting to EventBridge successfully  
- Admin user can log in to dashboard
- View form submission metrics and status
- S3 destination receiving form data
- Complete end-to-end flow working

---

## 📚 Essential Documents (Latest Versions Only)

### Core Implementation Docs
1. **[Form-Bridge Onboarding Workflow v3](docs/form-bridge-onboarding-workflow-v3.md)** *(Aug 26, 07:50)*
   - Final cost-optimized architecture ($4.50/month)
   - Security decisions and trade-offs
   - Universal plugin approach

2. **[MVP Implementation Phases](docs/mvp-implementation-phases.md)** *(Aug 26, 08:45)*
   - Phase-based development approach optimized for Claude Code
   - Context management strategy
   - Clear handoff procedures between phases

3. **[Form-Bridge User Stories](docs/form-bridge-user-stories.md)** *(Aug 26, 07:05)*
   - Complete user requirements
   - Acceptance criteria for all features
   - MVP scope definition

### Technical Specifications
4. **[MVP v1 Frontend Specification](docs/mvp-v1-frontend-specification.md)** *(Aug 26, 06:30)*
   - React dashboard architecture
   - Component specifications
   - API integration patterns

5. **[Form-Bridge TDD Plan](docs/form-bridge-tdd-plan.md)** *(Aug 26, 07:47)*
   - Test-driven development strategy
   - Testing framework setup
   - Coverage requirements

### Repository & Development Setup
6. **[Repository Strategy](docs/strategies/repo_strategy.md)** *(Aug 26, 07:47)*
   - Optimized directory structure
   - File naming conventions
   - Claude Code optimization

7. **[Hooks Configuration Recommendations](docs/hooks-configuration-recommendations.md)** *(Aug 26, 07:47)*
   - Claude Code hooks.json setup
   - Development workflow automation
   - Security and quality checks

### Agent Strategies (For Reference)
8. **[Principal Engineer Strategy](docs/strategies/principal-engineer-strategy.md)**
9. **[DynamoDB Architect Strategy](docs/strategies/dynamodb-architect-strategy.md)**
10. **[Test QA Engineer Strategy](docs/strategies/test-qa-engineer-strategy.md)**

---

## 📋 Master TODO List: Zero to MVP Deployed

### Phase 1: Foundation & Infrastructure
```markdown
## Repository Setup
- [ ] Apply optimized directory structure from repo_strategy.md
- [ ] Configure Claude Code hooks.json from recommendations
- [ ] Set up Python virtual environment 
- [ ] Install testing frameworks (pytest, black, safety)
- [ ] Initialize SAM CLI for AWS deployment

## DynamoDB Foundation
- [ ] Create DynamoDB table 'FormBridge' with single-table design
- [ ] Configure AWS-owned key encryption (free tier)
- [ ] Implement core access patterns from v3 workflow
- [ ] Create shared/python/dynamodb.py utility
- [ ] Test all PK/SK patterns for multi-tenancy

## Security & Encryption
- [ ] Build AES-256-GCM encryption utilities (no KMS)
- [ ] Create HMAC authentication functions
- [ ] Implement tenant-specific key derivation
- [ ] Set up rate limiting with DynamoDB counters
- [ ] Create Lambda authorizer structure

## Cost-Optimized Infrastructure  
- [ ] Configure CloudWatch with smart sampling
- [ ] Set up API Gateway with built-in throttling
- [ ] Implement cost monitoring hooks
- [ ] Validate $4.50/month target costs

## Testing Foundation
- [ ] Set up pytest with coverage reporting
- [ ] Create test database for local development
- [ ] Implement TDD patterns from tdd-plan.md
- [ ] Achieve 90% coverage for utilities

## Exit Criteria
- [ ] All shared utilities working and tested
- [ ] DynamoDB table operational with encryption
- [ ] Authentication patterns functional
- [ ] Rate limiting working in isolation
- [ ] Cost tracking active
```

### Phase 2: Ingestion Service
```markdown
## Webhook Handler Lambda
- [ ] Create services/ingestion/webhook_handler/
- [ ] Implement HMAC signature validation
- [ ] Add request parsing and sanitization
- [ ] Build error handling with friendly messages
- [ ] Add CloudWatch logging with sampling

## EventBridge Integration
- [ ] Configure EventBridge client in Lambda
- [ ] Standardize event structure for form submissions
- [ ] Implement tenant isolation in events
- [ ] Add retry logic for failed publishes
- [ ] Create monitoring for event throughput

## API Gateway Setup
- [ ] Deploy Lambda authorizer using Phase 1 utilities
- [ ] Configure API Gateway with webhook endpoint
- [ ] Enable dynamic CORS headers from DynamoDB
- [ ] Set up throttling (1000 RPS, 2000 burst)
- [ ] Test rate limiting blocks excessive requests

## Security Implementation
- [ ] Validate HMAC signatures reject invalid requests
- [ ] Implement IP-based rate limiting
- [ ] Add request size limits (1MB max)
- [ ] Configure security headers in responses
- [ ] Test attack vector protections

## Exit Criteria
- [ ] /api/webhook endpoint accepts valid POST requests
- [ ] Invalid HMAC signatures properly rejected
- [ ] Events successfully published to EventBridge
- [ ] Rate limiting functional and tested
- [ ] API Gateway costs under $1/month
```

### Phase 3: Processing & Routing  
```markdown
## Event Router Lambda
- [ ] Create services/processing/event_router/
- [ ] Subscribe to EventBridge 'submission.received' events
- [ ] Implement destination lookup from DynamoDB
- [ ] Build multi-destination fan-out logic
- [ ] Add dead letter queue for failed processing

## Data Transformation
- [ ] Create field mapping engine for destinations
- [ ] Add data validation and sanitization
- [ ] Implement format conversion (JSON, form-encoded)
- [ ] Build template substitution system
- [ ] Test transformation with sample data

## S3 Destination Connector (MVP Target)
- [ ] Create services/delivery/s3_sender/
- [ ] Implement S3 client with proper permissions
- [ ] Add file naming conventions (tenant/date/submission.json)
- [ ] Configure S3 bucket with lifecycle policies
- [ ] Test S3 delivery end-to-end

## Error Handling & Retry
- [ ] Implement exponential backoff for failures
- [ ] Configure SQS dead letter queues
- [ ] Add manual retry capability via API
- [ ] Create audit logging for delivery attempts
- [ ] Test recovery scenarios

## Exit Criteria
- [ ] Events route from EventBridge to S3 successfully
- [ ] Failed deliveries handled gracefully
- [ ] S3 bucket receiving JSON form submissions
- [ ] Retry logic working with exponential backoff
- [ ] Processing costs under $1/month
```

### Phase 4: Storage & Monitoring
```markdown
## Submission Storage
- [ ] Create services/storage/dynamodb_writer/
- [ ] Implement submission persistence with TTL (30 days MVP)
- [ ] Add compression for large payloads (>1KB)
- [ ] Create indexing for efficient queries
- [ ] Test storage with high volume

## Query & Retrieval API
- [ ] Build services/storage/query_handler/  
- [ ] Implement GET /api/submissions endpoint
- [ ] Add filtering by tenant, date range, status
- [ ] Create pagination with cursor-based approach
- [ ] Build aggregation queries for metrics

## Metrics & Health Monitoring
- [ ] Store submission counts by tenant/day
- [ ] Track success/failure rates
- [ ] Monitor API response times
- [ ] Create health check endpoints
- [ ] Implement cost tracking per tenant

## Admin API Endpoints
- [ ] POST /api/auth/login (admin user)
- [ ] GET /api/dashboard/metrics
- [ ] GET /api/sites (WordPress sites registered)
- [ ] GET /api/destinations (S3 config)
- [ ] POST /api/test/s3 (test S3 connection)

## Exit Criteria
- [ ] Submissions stored and retrievable via API
- [ ] Admin login working (env var or hardcoded)
- [ ] Dashboard metrics API returning data
- [ ] Query performance under 200ms
- [ ] Storage costs optimized with TTL
```

### Phase 5: WordPress Plugin
```markdown
## Plugin Structure & Core
- [ ] Create plugins/wordpress/ directory
- [ ] Build universal plugin core (platform detection)
- [ ] Implement WordPress adapter for WP-specific hooks
- [ ] Create plugin header and activation logic
- [ ] Add settings page in WordPress admin

## Form Integration
- [ ] Contact Form 7 integration hook
- [ ] Gravity Forms support
- [ ] WooCommerce form capture
- [ ] Generic $_POST form detection
- [ ] Test with multiple form types

## Authentication & Security  
- [ ] Implement HMAC signature generation
- [ ] Add tenant ID and API key configuration
- [ ] Create secure storage in wp_options
- [ ] Build site registration flow
- [ ] Test authentication with backend

## Auto-Update Mechanism
- [ ] Weekly update check to backend API
- [ ] SHA256 checksum validation
- [ ] Automatic plugin update installation
- [ ] Rollback capability for failed updates
- [ ] Version compatibility checking

## Plugin Settings UI
- [ ] WordPress admin settings page
- [ ] API endpoint configuration
- [ ] Form integration toggles
- [ ] Connection status display
- [ ] Test form submission button

## Exit Criteria
- [ ] Plugin activates without errors
- [ ] Forms captured and sent to webhook endpoint
- [ ] HMAC authentication working
- [ ] Settings UI functional
- [ ] Auto-update checking working
```

### Phase 6: React Dashboard
```markdown
## Dashboard Foundation
- [ ] Create dashboard/ React app with Vite
- [ ] Set up TypeScript and testing (Jest/RTL)
- [ ] Configure routing with React Router
- [ ] Add Tailwind CSS + shadcn/ui components
- [ ] Implement authentication context

## Authentication Flow
- [ ] Login page with email/password
- [ ] JWT token storage and management
- [ ] Protected route components
- [ ] Auto-logout on token expiry
- [ ] Admin user login (hardcoded for MVP)

## Site Management Interface
- [ ] Sites listing page with status indicators
- [ ] WordPress plugin download generation
- [ ] Site registration monitoring
- [ ] Bulk operations interface (future)
- [ ] Site health monitoring dashboard

## Form Submission Monitoring
- [ ] Real-time submission feed (5-second polling)
- [ ] Submission details modal/page
- [ ] Filtering by date, status, site
- [ ] Export functionality (CSV)
- [ ] Search within submissions

## Dashboard Metrics
- [ ] Key metrics cards (total submissions, success rate)
- [ ] Time-series charts for submission volume
- [ ] S3 destination status
- [ ] Error rate monitoring
- [ ] Cost tracking display

## Exit Criteria
- [ ] Admin can log in to dashboard
- [ ] Real-time submission monitoring working
- [ ] Site management functional
- [ ] S3 destination configuration working
- [ ] Responsive design on mobile/desktop
```

### Phase 7: End-to-End Integration & Launch
```markdown
## Full Integration Testing
- [ ] WordPress plugin → Webhook → EventBridge → S3 flow
- [ ] Dashboard displays real form submissions
- [ ] Admin user can manage sites and view metrics
- [ ] Error handling working across all components
- [ ] Performance testing under load

## Production Deployment
- [ ] Deploy all Lambda functions to AWS
- [ ] Configure production DynamoDB table
- [ ] Set up S3 bucket with proper permissions
- [ ] Deploy React dashboard (S3 + CloudFront)
- [ ] Configure domain and SSL certificates

## Monitoring & Alerting
- [ ] CloudWatch dashboards for all services
- [ ] Alerts for high error rates
- [ ] Cost monitoring and budget alerts
- [ ] Health check monitoring
- [ ] Performance threshold alerting

## Documentation & Guides
- [ ] WordPress plugin installation guide
- [ ] Dashboard user guide
- [ ] API documentation
- [ ] Troubleshooting guide
- [ ] Admin runbook

## Launch Validation
- [ ] Install WordPress plugin on test site
- [ ] Submit forms and verify S3 delivery
- [ ] Log in to dashboard and view submissions
- [ ] Verify all metrics and monitoring working
- [ ] Confirm costs under $5/month target

## Exit Criteria
- [ ] Complete form submission pipeline working
- [ ] Admin dashboard functional with real data
- [ ] WordPress plugin installable and working
- [ ] S3 destination receiving form data
- [ ] Production monitoring and alerting active
- [ ] MVP ready for beta user testing
```

---

## 🔧 Environment Setup Requirements

### AWS Configuration
```bash
# Required environment variables
AWS_REGION=us-east-1
AWS_PROFILE=formbridge-dev

# Admin user credentials (temporary MVP approach)
ADMIN_EMAIL=admin@yoursite.com
ADMIN_PASSWORD=secure-temp-password
JWT_SECRET=your-jwt-secret-256-bit

# Master encryption secret
MASTER_SECRET=your-master-encryption-secret

# S3 destination configuration
S3_BUCKET_NAME=formbridge-submissions-dev
S3_REGION=us-east-1
```

### Development Tools
```bash
# Install required tools
pip install boto3 pytest black safety
npm install -g @aws-amplify/cli
brew install awscli sam-cli  # or equivalent for your OS
```

### Local Testing
```bash
# Start DynamoDB Local
docker run -p 8000:8000 amazon/dynamodb-local

# WordPress local development
wp server --host=localhost --port=8080
```

---

## 📖 Key Configuration Files

### SAM Template Location
- `infrastructure/sam/template.yaml` - All AWS resources defined here

### Plugin Configuration
- `plugins/wordpress/formbridge.php` - Main plugin file
- `plugins/wordpress/admin/settings.php` - WordPress settings UI

### Dashboard Configuration  
- `dashboard/src/config/api.ts` - API endpoints and configuration
- `dashboard/src/contexts/AuthContext.tsx` - Authentication management

---

## 🎯 Success Validation Checklist

### WordPress Integration
- [ ] Plugin installs without errors
- [ ] Forms on WordPress site are captured
- [ ] HMAC signatures validate successfully
- [ ] Site registration appears in dashboard

### Backend Processing
- [ ] Webhooks received and validated
- [ ] Events published to EventBridge
- [ ] S3 files created for each submission
- [ ] DynamoDB stores submission metadata

### Dashboard Functionality
- [ ] Admin login works
- [ ] Real-time submission feed updates
- [ ] Metrics display correctly
- [ ] S3 destination shows as healthy

### Operational Requirements
- [ ] Monthly costs under $5
- [ ] Response times under 200ms p95
- [ ] Error rates under 1%
- [ ] Test form submission end-to-end works

---

## 🔄 Development Workflow with Claude Code

### Phase-Based Development
1. **Start each phase** by reviewing the specific phase documentation
2. **Follow TDD approach** - write tests first, then implement
3. **Complete exit criteria** before moving to next phase
4. **Document working state** for context handoff
5. **Clean up context** before starting next phase

### Claude Code Session Management
```markdown
Session Start Checklist:
- [ ] Review relevant phase documentation
- [ ] Check current TODO progress
- [ ] Set up testing environment
- [ ] Verify previous phase still working

Session End Checklist:
- [ ] Update TODO progress
- [ ] Commit working code
- [ ] Document any issues or learnings
- [ ] Prepare handoff notes for next session
```

---

## 🚨 Known Dependencies & Blockers

### AWS Account Requirements
- DynamoDB table creation permissions
- Lambda function deployment permissions  
- S3 bucket creation and access
- EventBridge rule creation
- API Gateway configuration

### Development Environment
- WordPress local development setup
- Node.js 18+ for React dashboard
- Python 3.9+ for Lambda functions
- AWS CLI configured with credentials

### External Integrations
- WordPress site with forms (Contact Form 7 or Gravity Forms)
- S3 bucket for destination storage
- Domain for dashboard deployment (optional for MVP)

---

This document provides everything needed to go from zero to a working MVP that accepts WordPress form submissions, processes them through EventBridge, stores them in S3, and provides a dashboard for monitoring - all while maintaining the $4.50/month cost target.
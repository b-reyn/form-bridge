# Form-Bridge Documentation Hub

*Last Updated: January 26, 2025*
*Status: REORGANIZED - New consolidated structure*

## Quick Navigation

### 📍 Essential Documents
- [**CLAUDE.md**](/CLAUDE.md) - Persistent AI assistant context
- [**Repository Strategy**](strategies/repo_strategy.md) - Directory structure & organization

## 📚 Documentation Structure

### 1. Security (`/docs/security/`) 🔐
**Critical security documentation requiring immediate attention**

- [**README**](security/README.md) - Security documentation index
- [**Critical Security Plan**](security/CRITICAL_SECURITY_IMPLEMENTATION_PLAN.md) - Priority fixes
- [**Comprehensive Audit**](security/comprehensive-security-audit-jan-2025.md) - Full security assessment
- [**Security Audit**](security/security-audit-jan-2025.md) - API key vulnerability analysis
- [**Monitoring Architecture**](security/security-monitoring-architecture.md) - Security monitoring
- [**Cognito JWT Plan**](security/cognito-jwt-integration-plan.md) - Authentication implementation

### 2. Frontend (`/docs/frontend/`) ⚛️
**React dashboard and UI documentation**

- [**README**](frontend/README.md) - Frontend documentation index
- [**Modern Architecture**](frontend/modern-react-dashboard-architecture.md) - React 18+ architecture
- [**MVP Specification**](frontend/mvp-v1-frontend-specification.md) - MVP requirements
- [**Analytics Dashboard**](frontend/dashboard-analytics-specification.md) - Analytics features
- [**Performance Plan**](frontend/frontend-performance-optimization-plan.md) - Optimization strategies
- [**User Stories**](frontend/form-bridge-user-stories.md) - Feature requirements

### 3. Integrations (`/docs/integrations/`) 🔌
**External service integrations and event routing**

- [**README**](integrations/README.md) - Integration documentation index
- [**EventBridge Plan**](integrations/eventbridge-implementation-plan-2025.md) - Core event bus
- [**Real-time Events**](integrations/eventbridge-realtime-integration-guide.md) - Real-time processing
- [**Analytics Guide**](integrations/analytics-implementation-guide.md) - Analytics pipeline
- [**Webhook Implementation**](integrations/hooks-implementation-guide.md) - Webhook delivery
- [**Hook Configuration**](integrations/hooks-configuration-recommendations.md) - Best practices

### 4. Testing (`/docs/testing/`) 🧪
**Testing strategies and quality assurance**

- [**README**](testing/README.md) - Testing documentation index
- [**TDD Plan**](testing/form-bridge-tdd-plan.md) - Test-driven development approach

### 5. Workflows (`/docs/workflows/`) 🔄
**Business processes and operational workflows**

- [**README**](workflows/README.md) - Workflow documentation index
- [**Onboarding V3**](workflows/form-bridge-onboarding-workflow-v3.md) - Current onboarding process

### 6. MVP Implementation (`/docs/mvp/`) 🚀
**Current MVP development and implementation status**

- [**README**](mvp/README.md) - MVP overview and navigation
- [**BUILD_DEPLOY_VALIDATE_PLAN**](mvp/BUILD_DEPLOY_VALIDATE_PLAN.md) - **🔥 Active implementation plan**
- [**Architecture**](mvp/architecture.md) - EventBridge-centric design
- [**Phases**](mvp/phases.md) - Implementation roadmap
- [**Improvements**](mvp/improvement-todo.md) - Prioritized task list
- [**Workflow Review**](mvp/workflow-review.md) - Process analysis

**Implementation Guides** (`/docs/mvp/implementation/`):
- Testing, monitoring, cost optimization, DynamoDB, and deployment guides

### 7. Agent Strategies (`/docs/strategies/`) 🤖
**Domain expertise maintained by specialist agents**

- [**Repository**](strategies/repo_strategy.md) - Directory organization
- [**Principal Engineer**](strategies/principal-engineer-strategy.md) - Technical leadership
- [**EventBridge**](strategies/eventbridge-architect-strategy.md) - Event patterns
- [**Lambda**](strategies/lambda-serverless-expert-strategy.md) - Serverless practices
- [**DynamoDB**](strategies/dynamodb-architect-strategy.md) - NoSQL modeling
- Plus 9 more specialist strategies...

### 8. Architecture (`/docs/architecture/`) 🏗️
**System design and architectural decisions**

- [**Migration Plan**](architecture/repository-migration-plan.md) - Repository restructuring

### 9. Research (`/docs/research/`) 🔬
**Technical investigations and proof-of-concepts**

- [**WordPress Auth**](research/wordpress-plugin-authentication-multisite-2025.md) - Multi-site authentication

### 10. Examples (`/docs/examples/`) 💡
**Reference implementations and proof-of-concept code**

- `/security/` - Security monitoring examples
- `/wordpress-auth/` - WordPress authentication patterns
- [README](examples/README.md) - Important usage notes

### 11. Archive (`/docs/archive/`) 📦
**Historical and deprecated documentation**

- `/v1/` - First iteration documents
- `/v2/` - Second iteration documents  
- `/legacy/` - Outdated references

## 🎯 Priority Documents (January 2025)

### Critical Security
1. [Security Audit - API Keys](security/security-audit-jan-2025.md) - **URGENT**
2. [Critical Security Plan](security/CRITICAL_SECURITY_IMPLEMENTATION_PLAN.md) - **HIGH**
3. [Cognito JWT Integration](security/cognito-jwt-integration-plan.md) - **HIGH**

### MVP Development
1. [Frontend Specification](frontend/mvp-v1-frontend-specification.md) - **ACTIVE**
2. [EventBridge Implementation](integrations/eventbridge-implementation-plan-2025.md) - **ACTIVE**
3. [Onboarding Workflow](workflows/form-bridge-onboarding-workflow-v3.md) - **ACTIVE**

## 📋 Documentation Standards

### File Naming Conventions
- **Guides**: `{topic}-guide.md`
- **Plans**: `{topic}-plan.md` or `{topic}-plan-{year}.md`
- **Specifications**: `{feature}-specification.md`
- **Audits**: `{type}-audit-{date}.md`
- **Strategies**: `{agent-name}-strategy.md`

### Document Headers
Every document must include:
```markdown
# Document Title

*Last Updated: YYYY-MM-DD*
*Status: ACTIVE/DRAFT/ARCHIVED*
*Owner: [Agent/Role Name]*
```

### Organization Rules
1. **No root-level docs** except README.md and essential files
2. **Categorize by function** not by date or version
3. **Archive outdated** documents with timestamps
4. **Consolidate duplicates** during quarterly reviews
5. **Update indexes** when structure changes

## 🔍 Finding Documentation

### By Topic
```bash
# Security documentation
ls docs/security/

# Frontend guides
ls docs/frontend/

# Integration specs
ls docs/integrations/
```

### By Keyword
```bash
# Search all documentation
grep -r "EventBridge" docs/

# Find recent updates
find docs -name "*.md" -mtime -7

# Locate strategies
find docs/strategies -name "*-strategy.md"
```

### By Status
- **Active**: Currently maintained and used
- **Planning**: Under development
- **Review**: Awaiting approval
- **Archived**: Historical reference only

## 🔄 Maintenance Schedule

### Weekly
- Review new documentation additions
- Update status fields
- Check for duplicates

### Monthly
- Archive completed initiatives
- Consolidate related documents
- Update navigation indexes

### Quarterly
- Major reorganization if needed
- Remove obsolete documentation
- Strategy document updates

## 📝 Contributing Guidelines

### Adding New Documentation
1. Choose appropriate category directory
2. Follow naming conventions
3. Include required headers
4. Update category README
5. Link from main index if priority

### Updating Existing Docs
1. Update "Last Updated" timestamp
2. Note significant changes
3. Archive if superseded
4. Update related indexes

### Archiving Documents
1. Move to `/docs/archive/`
2. Add archive date to filename
3. Update references
4. Note in category README

## Document Status Legend

- **Active** - Current and maintained
- **Draft** - Under development
- **Review** - Awaiting approval
- **Archived** - Historical reference only

## Contribution Guidelines

1. **New Documentation**: Place in appropriate category folder
2. **Updates**: Include "Last Updated" timestamp
3. **Archival**: Move to `/archive/` with date stamp when superseded
4. **Naming**: Follow conventions in `repo_strategy.md`

## Search Tips

```bash
# Find all strategy documents
find docs/strategies -name "*-strategy.md"

# Find implementation guides
find docs/mvp/implementation -name "*.md"

# Search for specific topics
grep -r "EventBridge" docs/

# List recent updates
find docs -name "*.md" -mtime -7
```

## Maintenance

This index is maintained by the Repository Strategy Owner and should be updated whenever documentation structure changes.
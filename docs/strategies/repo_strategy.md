# Repository Strategy Document

*Last Updated: January 26, 2025*
*Owner: Repository Strategy Agent*
*Purpose: Define and maintain optimal directory structure for Form-Bridge*

## Executive Summary

This document defines the canonical directory structure and organization patterns for Form-Bridge, optimized for both human developers and AI assistants. The structure follows EventBridge-centric architecture principles while maintaining clear separation of concerns.

## Core Principles

### 1. Single Source of Truth
- One obvious location for every file
- No duplication of functionality
- Clear ownership boundaries

### 2. Discoverability First
- Self-documenting names
- Logical grouping by function
- README files for context

### 3. Scalability by Design
- Flat when possible, nested when necessary
- Plugin-based extensibility
- Clear abstraction layers

### 4. AI-Optimized Patterns
- Consistent naming conventions
- Predictable file locations
- Rich context in directory structure

## Directory Structure

```
form-bridge/
│
├── .github/                        # GitHub-specific configuration
│   ├── workflows/                  # CI/CD pipelines
│   │   ├── test.yml               # Test automation
│   │   ├── deploy-dev.yml         # Development deployment
│   │   ├── deploy-prod.yml        # Production deployment
│   │   └── security-scan.yml      # Security scanning
│   └── CODEOWNERS                 # Code ownership mapping
│
├── infrastructure/                 # AWS Infrastructure as Code
│   ├── cdk/                       # CDK application (future)
│   │   └── README.md              # CDK patterns and usage
│   ├── sam/                       # SAM templates (current)
│   │   ├── template.yaml          # Main SAM template
│   │   ├── parameters/            # Environment parameters
│   │   │   ├── dev.json
│   │   │   └── prod.json
│   │   └── README.md              # Deployment instructions
│   ├── terraform/                 # Terraform modules (alternative)
│   └── scripts/                   # Infrastructure scripts
│       ├── deploy.sh
│       └── destroy.sh
│
├── services/                       # Core Lambda functions by domain
│   ├── ingestion/                 # Form submission ingestion
│   │   ├── api-handler/           # API Gateway handler
│   │   │   ├── index.py
│   │   │   ├── requirements.txt
│   │   │   └── tests/
│   │   ├── validator/             # Submission validation
│   │   │   ├── index.py
│   │   │   └── tests/
│   │   └── README.md
│   │
│   ├── processing/                # Event processing functions
│   │   ├── router/                # EventBridge router
│   │   ├── transformer/           # Data transformation
│   │   └── enricher/              # Data enrichment
│   │
│   ├── storage/                   # DynamoDB operations
│   │   ├── writer/                # Data persistence
│   │   ├── reader/                # Data retrieval
│   │   └── schemas/               # DynamoDB schemas
│   │       └── single-table.json
│   │
│   ├── delivery/                  # Outbound delivery
│   │   ├── webhook/               # Webhook delivery
│   │   ├── email/                 # Email notifications
│   │   └── orchestrator/          # Step Functions
│   │
│   └── admin/                     # Admin operations
│       ├── tenant-manager/        # Tenant CRUD
│       ├── metrics-aggregator/    # Analytics
│       └── audit-logger/          # Audit trails
│
├── plugins/                        # Platform-specific plugins
│   ├── wordpress/                  # WordPress plugin
│   │   ├── form-bridge/          # Plugin source
│   │   │   ├── form-bridge.php   # Main plugin file
│   │   │   ├── includes/         # PHP classes
│   │   │   ├── admin/            # Admin interface
│   │   │   └── assets/           # CSS/JS
│   │   ├── tests/                # PHPUnit tests
│   │   └── README.md              # Installation guide
│   │
│   ├── shopify/                   # Shopify app
│   │   ├── app/                  # App source
│   │   └── README.md
│   │
│   └── webhook-receiver/          # Generic webhook endpoint
│       └── README.md
│
├── dashboard/                      # React admin dashboard
│   ├── src/
│   │   ├── components/            # Reusable components
│   │   │   ├── common/           # Generic UI components
│   │   │   ├── forms/            # Form components
│   │   │   └── charts/           # Analytics visualizations
│   │   ├── pages/                # Route components
│   │   │   ├── Dashboard/
│   │   │   ├── Tenants/
│   │   │   ├── Submissions/
│   │   │   └── Settings/
│   │   ├── hooks/                # Custom React hooks
│   │   ├── services/             # API service layer
│   │   ├── store/                # State management
│   │   ├── utils/                # Utility functions
│   │   └── types/                # TypeScript definitions
│   ├── public/                    # Static assets
│   ├── tests/                     # Test files
│   └── package.json
│
├── shared/                         # Shared libraries
│   ├── python/                    # Python utilities
│   │   ├── auth/                  # Authentication helpers
│   │   │   ├── hmac.py
│   │   │   └── jwt.py
│   │   ├── dynamodb/              # DynamoDB utilities
│   │   │   ├── client.py
│   │   │   └── models.py
│   │   ├── eventbridge/           # EventBridge helpers
│   │   └── tests/
│   │
│   ├── typescript/                # TypeScript utilities
│   │   └── api-client/           # API client library
│   │
│   └── schemas/                   # Shared data schemas
│       ├── events/               # EventBridge event schemas
│       ├── api/                  # API request/response schemas
│       └── database/             # Database schemas
│
├── tests/                          # Integration & E2E tests
│   ├── integration/               # Cross-service tests
│   │   ├── workflows/            # Complete workflow tests
│   │   └── security/             # Security tests
│   ├── e2e/                      # End-to-end tests
│   │   └── scenarios/            # User scenarios
│   ├── load/                     # Performance tests
│   └── fixtures/                 # Test data
│
├── docs/                          # Documentation
│   ├── architecture/             # Architecture documentation
│   │   ├── decisions/           # ADRs
│   │   ├── diagrams/            # System diagrams
│   │   └── README.md            # Architecture overview
│   │
│   ├── api/                      # API documentation
│   │   ├── openapi.yaml         # OpenAPI specification
│   │   └── examples/            # Request/response examples
│   │
│   ├── strategies/               # Agent strategy documents
│   │   ├── repo_strategy.md     # This document
│   │   └── [agent-name]-strategy.md
│   │
│   ├── runbooks/                 # Operational runbooks
│   │   ├── deployment.md
│   │   ├── incident-response.md
│   │   └── rollback.md
│   │
│   └── guides/                   # User guides
│       ├── getting-started.md
│       ├── plugin-installation.md
│       └── api-integration.md
│
├── config/                        # Configuration files
│   ├── environments/             # Environment configs
│   │   ├── dev.env
│   │   ├── staging.env
│   │   └── prod.env
│   ├── security/                 # Security policies
│   │   ├── cors.json
│   │   └── csp.json
│   └── features/                 # Feature flags
│       └── flags.json
│
├── scripts/                       # Development scripts
│   ├── setup.sh                  # Initial setup
│   ├── test.sh                   # Run all tests
│   └── clean.sh                  # Cleanup
│
├── .vscode/                       # VS Code settings
│   ├── settings.json
│   ├── launch.json
│   └── extensions.json
│
├── CLAUDE.md                      # AI assistant context
├── README.md                      # Project overview
├── LICENSE                        # License file
└── .gitignore                    # Git ignore rules
```

## Naming Conventions

### Files

#### Python Files
- **Functions**: `snake_case.py` (e.g., `process_submission.py`)
- **Classes**: `snake_case.py` (e.g., `tenant_manager.py`)
- **Tests**: `test_[name].py` (e.g., `test_process_submission.py`)
- **Constants**: `constants.py`

#### JavaScript/TypeScript Files
- **React Components**: `PascalCase.tsx` (e.g., `SubmissionForm.tsx`)
- **Utilities**: `camelCase.ts` (e.g., `formatDate.ts`)
- **Hooks**: `use[Name].ts` (e.g., `useSubmissions.ts`)
- **Tests**: `[name].test.ts` or `[name].spec.ts`
- **Types**: `[name].types.ts`

#### Configuration Files
- **Environment**: `[environment].env` (e.g., `dev.env`)
- **Parameters**: `[environment].json` (e.g., `prod.json`)
- **YAML**: `kebab-case.yaml` (e.g., `template.yaml`)

### Directories

#### Service Directories
- **Purpose-based**: `ingestion/`, `processing/`, `storage/`
- **Function-specific**: `api-handler/`, `validator/`

#### Component Directories
- **Domain-based**: `forms/`, `charts/`, `auth/`
- **Feature-based**: `Dashboard/`, `Settings/`

## File Organization Patterns

### Lambda Functions
```
services/[domain]/[function]/
├── index.py                 # Main handler
├── requirements.txt         # Dependencies
├── config.py               # Configuration
├── tests/
│   ├── test_handler.py     # Unit tests
│   └── fixtures/           # Test data
└── README.md               # Function documentation
```

### React Components
```
dashboard/src/components/[category]/[Component]/
├── index.tsx               # Component export
├── [Component].tsx         # Component implementation
├── [Component].styles.ts   # Styled components/Tailwind
├── [Component].types.ts    # TypeScript types
├── [Component].test.tsx    # Component tests
└── README.md              # Component documentation
```

### Shared Libraries
```
shared/[language]/[library]/
├── __init__.py            # Package initialization
├── [module].py            # Core functionality
├── tests/
│   └── test_[module].py   # Unit tests
└── README.md              # Library documentation
```

## Documentation Standards

### README Files
Every major directory must have a README.md containing:
1. **Purpose**: What this directory contains
2. **Structure**: Subdirectory explanations
3. **Usage**: How to use/extend the code
4. **Dependencies**: Required packages/services
5. **Testing**: How to run tests

### Code Documentation
- **Python**: Docstrings for all public functions/classes
- **TypeScript**: JSDoc comments for public APIs
- **Infrastructure**: Inline comments for complex logic

### Architecture Decision Records (ADRs)
Location: `/docs/architecture/decisions/`
Format: `YYYY-MM-DD-[title].md`
Content:
- Status (proposed/accepted/deprecated)
- Context
- Decision
- Consequences

## Migration Guidelines

### From Current Structure to Target

#### Phase 1: Core Reorganization
1. Move `lambdas/` content to `services/`
2. Create proper domain separation
3. Establish shared libraries

#### Phase 2: Plugin Extraction
1. Move WordPress auth to `plugins/wordpress/`
2. Maintain backward compatibility
3. Update deployment scripts

#### Phase 3: Dashboard Integration
1. Create `dashboard/` structure
2. Migrate UI components
3. Establish API service layer

### Backward Compatibility
- Maintain symlinks during transition
- Update imports gradually
- Document breaking changes

## Quality Checks

### Directory Structure Validation
- [ ] No more than 4 levels deep (except node_modules)
- [ ] Each directory has clear purpose
- [ ] README files in all major directories
- [ ] Consistent naming patterns
- [ ] No duplicate functionality

### File Organization Audit
- [ ] Related files are co-located
- [ ] Test files mirror source structure
- [ ] Configuration centralized
- [ ] Documentation up-to-date
- [ ] No orphaned files

## Best Practices

### Do's
- ✅ Keep related code together
- ✅ Use clear, descriptive names
- ✅ Create README files proactively
- ✅ Follow established patterns
- ✅ Document deviations

### Don'ts
- ❌ Create deeply nested structures
- ❌ Mix languages in same directory
- ❌ Duplicate code across services
- ❌ Use ambiguous names
- ❌ Store secrets in code

## AI Assistant Optimization

### Context Preservation
- Directory names provide domain context
- README files explain purpose and patterns
- Consistent structure reduces ambiguity

### Discovery Patterns
- Predictable file locations
- Standard naming conventions
- Clear service boundaries

### Code Navigation
```bash
# Find all Lambda functions
ls -la services/*/

# Find all tests
find . -name "test_*.py" -o -name "*.test.ts"

# Find configuration
ls -la config/environments/
```

## Collaboration Guidelines

### For Product Owner
- Feature requests go in `/docs/guides/`
- User stories in `/docs/`
- Analytics requirements in `/docs/`

### For Principal Engineer
- Architecture decisions in `/docs/architecture/decisions/`
- Security policies in `/config/security/`
- Infrastructure code in `/infrastructure/`

### For Specialists
- Domain code in `/services/[domain]/`
- Shared utilities in `/shared/`
- Tests alongside implementation

## Future Considerations

### Microservices Migration
- Each service becomes separate repository
- Shared libraries become packages
- Maintain monorepo during transition

### Multi-Region Support
- Regional configuration in `/config/regions/`
- Region-specific deployments
- Centralized control plane

### Platform Expansion
- New plugins in `/plugins/[platform]/`
- Platform-specific documentation
- Shared plugin interfaces

## Maintenance Schedule

### Weekly
- Remove orphaned files
- Update README files
- Validate naming conventions

### Monthly
- Audit directory depth
- Review duplication
- Update this document

### Quarterly
- Major restructuring if needed
- Archive deprecated code
- Update migration plan

## Success Metrics

### Quantitative
- Average directory depth: < 4
- README coverage: > 90%
- Test coverage: > 80%
- Documentation freshness: < 30 days

### Qualitative
- Developer onboarding time
- AI assistant effectiveness
- Code discovery speed
- Maintenance burden

## Appendix

### Tool Configuration

#### VS Code Settings
```json
{
  "files.exclude": {
    "**/__pycache__": true,
    "**/node_modules": true,
    "**/.pytest_cache": true
  },
  "search.exclude": {
    "**/build": true,
    "**/dist": true
  }
}
```

#### Git Attributes
```
*.py linguist-language=Python
*.tsx linguist-language=TypeScript
/docs/** linguist-documentation
```

### Common Commands

```bash
# Create new Lambda function
mkdir -p services/[domain]/[function]/{tests,fixtures}

# Create new React component
mkdir -p dashboard/src/components/[category]/[Component]

# Find all strategy documents
find docs/strategies -name "*-strategy.md"

# Check directory depth
find . -type d | awk -F/ '{print NF-1}' | sort -n | tail -1
```

## Documentation Consolidation (Completed January 26, 2025)

### Reorganization Summary
Successfully consolidated 17 scattered documentation files from /docs root into 5 logical subdirectories, improving navigation and reducing clutter.

### Completed Structure

```
docs/
├── README.md                     # Documentation hub with clear navigation
│
├── security/                     # Security documentation (5 files)
│   ├── README.md                # Security index with priorities
│   ├── CRITICAL_SECURITY_IMPLEMENTATION_PLAN.md
│   ├── comprehensive-security-audit-jan-2025.md
│   ├── security-audit-jan-2025.md
│   ├── security-monitoring-architecture.md
│   └── cognito-jwt-integration-plan.md
│
├── frontend/                     # Frontend/React documentation (5 files)
│   ├── README.md                # Frontend index with stack info
│   ├── modern-react-dashboard-architecture.md
│   ├── mvp-v1-frontend-specification.md
│   ├── dashboard-analytics-specification.md
│   ├── frontend-performance-optimization-plan.md
│   └── form-bridge-user-stories.md
│
├── integrations/                 # Service integrations (5 files)
│   ├── README.md                # Integration index with patterns
│   ├── eventbridge-implementation-plan-2025.md
│   ├── eventbridge-realtime-integration-guide.md
│   ├── analytics-implementation-guide.md
│   ├── hooks-implementation-guide.md
│   └── hooks-configuration-recommendations.md
│
├── testing/                      # Testing documentation (1 file)
│   ├── README.md                # Testing index with strategies
│   └── form-bridge-tdd-plan.md
│
├── workflows/                    # Business workflows (1 file)
│   ├── README.md                # Workflow index with diagrams
│   └── form-bridge-onboarding-workflow-v3.md
│
├── mvp/                         # MVP implementation (existing)
├── strategies/                  # Agent strategies (existing)
├── architecture/                # Architecture docs (existing)
├── research/                    # Research docs (existing)
├── guides/                      # User guides (existing)
└── archive/                     # Historical docs (existing)
```

### Documentation Standards Enforced

#### Naming Conventions
- **Guides**: `{topic}-guide.md`
- **Plans**: `{topic}-plan.md` or `{topic}-plan-{year}.md`
- **Specifications**: `{feature}-specification.md`
- **Audits**: `{type}-audit-{date}.md`
- **Strategies**: `{agent-name}-strategy.md`

#### Each Subdirectory README Contains
1. **Purpose**: Clear explanation of category
2. **Document List**: All files with descriptions
3. **Status Indicators**: Active/Planning/Review/Archived
4. **Priority Levels**: Critical/High/Medium/Low
5. **Related Links**: Cross-references to other categories
6. **Quick Reference**: Common commands and usage

### Benefits Achieved

#### Improved Navigation
- Clear categorical organization
- Reduced cognitive load
- Faster document discovery
- Logical grouping by function

#### Better Maintenance
- No duplicate content found (all files unique)
- Clear ownership per category
- Easier to identify stale documents
- Simplified archival process

#### Enhanced Collaboration
- Agents know where to find/place documents
- Consistent structure across categories
- Self-documenting organization
- Clear contribution guidelines

### Ongoing Maintenance Rules

#### Documentation Placement
1. **Security Issues** → `/docs/security/`
2. **Frontend/UI** → `/docs/frontend/`
3. **External Services** → `/docs/integrations/`
4. **Testing/QA** → `/docs/testing/`
5. **Business Process** → `/docs/workflows/`
6. **Implementation** → `/docs/mvp/`
7. **Agent Knowledge** → `/docs/strategies/`
8. **System Design** → `/docs/architecture/`

#### Quarterly Reviews
- Check for documents to archive
- Consolidate related documents
- Update category READMEs
- Remove obsolete content

#### Anti-Patterns to Avoid
- ❌ Placing docs in /docs root
- ❌ Version numbers in filenames
- ❌ Duplicate content across files
- ❌ Missing "Last Updated" headers
- ❌ Unclear document ownership

---
*This document is the authoritative source for Form-Bridge repository organization. All structural changes must be reflected here.*
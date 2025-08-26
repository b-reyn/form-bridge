# Directory Structure Quick Reference

*For Developers and AI Assistants*

## Where Does It Go? Quick Decision Tree

### I'm writing a new Lambda function
```
services/
└── [domain]/           # Pick the right domain:
    ├── ingestion/      # API endpoints, form submission
    ├── processing/     # Event handling, transformation
    ├── storage/        # Database operations
    ├── delivery/       # Webhooks, notifications
    └── admin/          # Tenant management, metrics
        └── [function-name]/
            ├── index.py
            ├── requirements.txt
            └── tests/
```

### I'm adding a React component
```
dashboard/src/
├── components/         # Reusable components
│   ├── common/        # Buttons, inputs, modals
│   ├── forms/         # Form-specific components
│   └── charts/        # Data visualizations
└── pages/             # Route components
    └── [PageName]/    # Full page components
```

### I'm creating documentation
```
docs/
├── architecture/      # System design, ADRs
├── api/              # API specs, examples
├── guides/           # How-to guides
├── runbooks/         # Operational procedures
└── strategies/       # Agent knowledge bases
```

### I'm writing a test
```
# Unit tests: Same directory as code
services/ingestion/api-handler/tests/test_handler.py

# Integration tests: Cross-service tests
tests/integration/workflow_test.py

# E2E tests: User scenarios
tests/e2e/submit_form_test.py
```

### I'm adding configuration
```
config/
├── environments/     # Environment variables
│   └── dev.env
├── security/        # Security policies
│   └── cors.json
└── features/        # Feature flags
    └── flags.json
```

## File Naming Cheat Sheet

### Python
- Functions/Modules: `snake_case.py`
- Tests: `test_snake_case.py`
- Classes: Still use `snake_case.py`

### JavaScript/TypeScript
- Components: `PascalCase.tsx`
- Utilities: `camelCase.ts`
- Hooks: `useSomething.ts`
- Tests: `file.test.ts`

### Configuration
- Environment: `[env].env`
- YAML: `kebab-case.yaml`
- JSON: `camelCase.json`

## Common Locations

| What | Where | Example |
|------|-------|---------|
| Lambda handler | `services/[domain]/[function]/index.py` | `services/ingestion/api-handler/index.py` |
| React page | `dashboard/src/pages/[Page]/` | `dashboard/src/pages/Dashboard/` |
| Shared Python | `shared/python/[module]/` | `shared/python/auth/hmac.py` |
| API docs | `docs/api/` | `docs/api/openapi.yaml` |
| Unit tests | Next to source file | `index.py` → `tests/test_index.py` |
| Integration tests | `tests/integration/` | `tests/integration/form_submission.py` |
| WordPress plugin | `plugins/wordpress/` | `plugins/wordpress/form-bridge/` |
| SAM template | `infrastructure/sam/` | `infrastructure/sam/template.yaml` |
| Agent strategies | `docs/strategies/` | `docs/strategies/repo_strategy.md` |
| Feature flags | `config/features/` | `config/features/flags.json` |

## Service Domain Guide

### Ingestion Service
**Purpose**: Entry points for data
- API Gateway handlers
- Webhook receivers  
- Form validators
- Authentication

### Processing Service
**Purpose**: Transform and route data
- Event routers
- Data transformers
- Business logic
- Enrichment

### Storage Service
**Purpose**: Data persistence
- DynamoDB writers
- Query handlers
- Cache managers
- Backup operations

### Delivery Service  
**Purpose**: Send data to destinations
- Webhook delivery
- Email notifications
- API callbacks
- Step Functions

### Admin Service
**Purpose**: Management operations
- Tenant CRUD
- Metrics aggregation
- Audit logging
- Configuration

## Quick Commands

```bash
# Find where to put a Lambda function
ls -la services/

# Find all tests
find . -name "test_*.py" -o -name "*.test.ts"

# Find all README files
find . -name "README.md"

# Check directory depth
find . -type d | awk -F/ '{print NF-1}' | sort -n | tail -1

# Find strategy documents
ls -la docs/strategies/

# Find shared utilities
ls -la shared/python/
```

## AI Assistant Tips

### For Best Results
1. Check `/docs/strategies/repo_strategy.md` for detailed patterns
2. Look for README.md in target directory
3. Follow existing patterns in similar files
4. Use consistent naming with surrounding files
5. Keep related files together

### Common Patterns
```python
# Lambda function pattern
services/[domain]/[function]/
├── index.py           # Handler
├── config.py          # Configuration  
├── requirements.txt   # Dependencies
├── tests/            # Unit tests
└── README.md         # Documentation

# React component pattern
components/[Category]/[Component]/
├── index.tsx         # Public export
├── Component.tsx     # Implementation
├── Component.test.tsx # Tests
└── Component.types.ts # Types
```

## Do's and Don'ts

### DO ✅
- Put tests next to source code
- Create README for context
- Follow existing patterns
- Use clear, descriptive names
- Group related functionality

### DON'T ❌
- Create deep nesting (>4 levels)
- Mix languages in directories
- Duplicate code (use shared/)
- Use ambiguous names
- Store secrets in code

## Need Help?

1. Check `/docs/strategies/repo_strategy.md` for complete guide
2. Look at existing similar files for patterns
3. Review `/docs/architecture/` for design decisions
4. Check README.md in target directory

---
*Quick reference for Form-Bridge directory structure. Full documentation in `/docs/strategies/repo_strategy.md`*
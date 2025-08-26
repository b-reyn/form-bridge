# Repository Migration Plan

*Created: January 26, 2025*
*Purpose: Guide transition from current to optimal directory structure*

## Current State Analysis

### Existing Structure Issues
1. **Flat documentation structure** - All docs in single directory
2. **Lambda functions mixed** - WordPress auth mixed with general functions
3. **No clear service boundaries** - Functions not organized by domain
4. **Missing plugin structure** - WordPress code in lambdas directory
5. **No shared libraries** - Code duplication likely

### Assets to Preserve
- WordPress authentication implementation
- DynamoDB design documents
- Security audit findings
- Agent strategy documents
- EventBridge architecture

## Migration Phases

### Phase 0: Preparation (Week 1)
**Non-Breaking Setup**

1. Create new directory structure alongside existing:
```bash
mkdir -p services/{ingestion,processing,storage,delivery,admin}
mkdir -p plugins/wordpress/form-bridge
mkdir -p dashboard/src/{components,pages,hooks,services}
mkdir -p shared/{python,typescript,schemas}
mkdir -p tests/{integration,e2e,load}
mkdir -p infrastructure/{sam,scripts}
mkdir -p config/{environments,security,features}
mkdir -p docs/architecture/decisions
```

2. Add README templates to each directory
3. Update .gitignore for new structure
4. Create symlinks for backward compatibility

### Phase 1: Service Organization (Week 2)
**Reorganize Lambda Functions**

#### Current → Target Mapping
```
lambdas/wp-plugin-auth/ → services/admin/tenant-manager/
├── authentication.py → services/ingestion/api-handler/
├── initial_registration.py → services/admin/tenant-manager/
├── key_exchange.py → services/admin/tenant-manager/
├── site_validation.py → services/processing/validator/
├── update_check.py → plugins/wordpress/update-service/
├── shared_utils.py → shared/python/auth/
```

#### Migration Steps
1. Copy files to new locations (don't move yet)
2. Update import paths in copied files
3. Create integration tests
4. Update SAM templates to reference new paths
5. Deploy to dev environment
6. Validate functionality
7. Remove old files

### Phase 2: Plugin Extraction (Week 3)
**Create WordPress Plugin Structure**

1. Initialize WordPress plugin:
```bash
# Create plugin structure
mkdir -p plugins/wordpress/form-bridge/{includes,admin,assets}

# Move authentication logic
cp services/admin/tenant-manager/*.py plugins/wordpress/form-bridge/includes/

# Create plugin main file
touch plugins/wordpress/form-bridge/form-bridge.php
```

2. Create plugin distribution package
3. Set up plugin auto-update mechanism
4. Document installation process

### Phase 3: Shared Libraries (Week 4)
**Extract Common Code**

1. Identify duplicate code across services
2. Create shared modules:
```python
# shared/python/auth/hmac.py
class HMACValidator:
    """Shared HMAC validation logic"""
    
# shared/python/dynamodb/client.py  
class DynamoDBClient:
    """Shared DynamoDB operations"""
    
# shared/python/eventbridge/publisher.py
class EventPublisher:
    """Shared event publishing"""
```

3. Update services to use shared libraries
4. Create pip packages for Python shared libs
5. Create npm packages for TypeScript shared libs

### Phase 4: Dashboard Setup (Week 5)
**Initialize React Dashboard**

1. Create React application:
```bash
cd dashboard
npx create-react-app . --template typescript
npm install @aws-amplify/ui-react tailwindcss
```

2. Implement basic structure:
   - Authentication flow
   - Tenant list view
   - Submission history
   - Basic analytics

3. Connect to API endpoints
4. Deploy to S3/CloudFront

### Phase 5: Documentation Reorganization (Week 6)
**Restructure Documentation**

#### Current → Target
```
docs/*.md → docs/guides/
docs/research/ → docs/architecture/research/
docs/strategies/ → docs/strategies/ (keep as-is)
*.md (root) → docs/ or docs/guides/
```

1. Move documentation files
2. Update all internal links
3. Create comprehensive index
4. Add missing documentation

### Phase 6: Infrastructure Updates (Week 7)
**Modernize IaC**

1. Migrate SAM templates:
```yaml
# infrastructure/sam/template.yaml
Transform: AWS::Serverless-2016-10-31

Resources:
  # Organized by service domain
  IngestionService:
    Type: AWS::Serverless::Application
    Properties:
      Location: services/ingestion/template.yaml
      
  ProcessingService:
    Type: AWS::Serverless::Application
    Properties:
      Location: services/processing/template.yaml
```

2. Create deployment scripts
3. Set up CI/CD pipelines
4. Document deployment process

### Phase 7: Testing Infrastructure (Week 8)
**Establish Test Patterns**

1. Unit tests with source code
2. Integration tests in `/tests/integration/`
3. E2E tests in `/tests/e2e/`
4. Load tests in `/tests/load/`
5. Security tests in `/tests/security/`

### Phase 8: Cleanup (Week 9)
**Remove Legacy Structure**

1. Remove symlinks
2. Delete old directories
3. Archive deprecated code
4. Update all documentation
5. Final validation

## Rollback Plan

### Checkpoints
- After each phase, tag repository
- Maintain parallel deployments
- Keep old structure for 30 days

### Rollback Procedure
1. Revert SAM template changes
2. Restore symlinks
3. Redeploy from previous tag
4. Document issues encountered

## Success Criteria

### Phase Completion
- [ ] All tests passing
- [ ] No broken imports
- [ ] Documentation updated
- [ ] Deployments successful
- [ ] No service disruptions

### Final Validation
- [ ] Directory depth ≤ 4
- [ ] README in every directory
- [ ] No duplicate code
- [ ] All services isolated
- [ ] CI/CD fully functional

## Risk Mitigation

### Identified Risks
1. **Import path changes** → Use find/replace scripts
2. **Deployment failures** → Maintain blue/green deployments  
3. **Lost documentation** → Version control everything
4. **Team confusion** → Daily standup updates
5. **Integration breaks** → Comprehensive testing

### Mitigation Strategies
- Automated testing at each phase
- Gradual rollout with feature flags
- Detailed logging of all changes
- Team training sessions
- Rollback procedures tested

## Timeline

| Week | Phase | Description | Owner |
|------|-------|-------------|-------|
| 1 | Prep | Create structure | Repo Strategy |
| 2 | Phase 1 | Service organization | Principal Eng |
| 3 | Phase 2 | Plugin extraction | Principal Eng |
| 4 | Phase 3 | Shared libraries | Lambda Expert |
| 5 | Phase 4 | Dashboard setup | UI Designer |
| 6 | Phase 5 | Documentation | Repo Strategy |
| 7 | Phase 6 | Infrastructure | Principal Eng |
| 8 | Phase 7 | Testing | QA Lead |
| 9 | Phase 8 | Cleanup | Repo Strategy |

## Communication Plan

### Stakeholder Updates
- Weekly progress reports
- Blockers communicated immediately
- Success metrics dashboard
- Post-migration retrospective

### Team Notifications
- Daily standup updates
- Slack channel: #repo-migration
- Wiki documentation
- Training videos

## Post-Migration Tasks

1. Update onboarding documentation
2. Create architecture diagrams
3. Record training videos
4. Update CI/CD pipelines
5. Performance benchmarking
6. Security audit
7. Cost analysis

## Lessons Learned Log

*To be updated during migration*

- [ ] What worked well
- [ ] What was challenging  
- [ ] Time estimates accuracy
- [ ] Unexpected issues
- [ ] Process improvements

---
*This plan is a living document. Update throughout migration process.*
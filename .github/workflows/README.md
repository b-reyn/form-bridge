# GitHub Actions Workflows for Form-Bridge

## Active Workflows

### deploy-ultra-simple.yml
**Status:** ✅ ACTIVE  
**Purpose:** Deploy the ultra-simple Form Bridge architecture (Lambda + DynamoDB)  
**Cost:** $0/month (AWS Free Tier)

#### Triggers
- **Push to main/develop:** Automatically deploys when changes are made to `ultra-simple/` directory
- **Pull Request:** Validates changes without deploying
- **Manual Dispatch:** Deploy on-demand via GitHub Actions UI

#### Required Secrets
Configure these in your repository settings (Settings → Secrets and variables → Actions):
- `AWS_ACCESS_KEY_ID` - AWS IAM user access key
- `AWS_SECRET_ACCESS_KEY` - AWS IAM user secret key

#### Deployment Environments
- **test** - Default for development/testing
- **prod** - Production environment (main branch only)

#### Files Monitored
```
ultra-simple/
├── handler.py           # Lambda function code
├── template-minimal.yaml # SAM/CloudFormation template
├── requirements.txt     # Python dependencies
└── deploy.sh           # Local deployment script
```

#### Workflow Steps
1. **Validation (< 1 minute)**
   - Checks all required files exist
   - Validates Python syntax
   - Validates CloudFormation template structure

2. **Deployment (< 5 minutes)**
   - Builds SAM application
   - Deploys to AWS using CloudFormation
   - Creates Lambda Function URL
   - Creates DynamoDB table

3. **Testing**
   - Tests CORS preflight
   - Tests form submission with HMAC auth
   - Outputs WordPress plugin configuration

#### Manual Deployment
```bash
# Via GitHub UI
1. Go to Actions tab
2. Select "Deploy Ultra-Simple Form Bridge"
3. Click "Run workflow"
4. Select environment (test/prod)
5. Click "Run workflow"

# Via GitHub CLI
gh workflow run deploy-ultra-simple.yml -f environment=test
```

#### Monitoring Deployment
```bash
# View latest run
gh run list --workflow=deploy-ultra-simple.yml

# Watch deployment logs
gh run watch

# View specific run
gh run view <run-id>
```

## Disabled Workflows

### deploy-mvp.yml.disabled
**Status:** ❌ DISABLED  
**Reason:** MVP architecture files no longer present  
**Alternative:** Use `deploy-ultra-simple.yml`

## Local Testing

### Test Workflow Configuration
```bash
# Run validation script
./.github/workflows/test-workflow-validation.sh

# Expected output:
# ✅ All validation checks passed!
```

### Test Deployment Locally
```bash
# Use the ultra-simple deployment script
cd ultra-simple
./deploy.sh

# Or use SAM CLI directly
sam build --template-file template-minimal.yaml
sam deploy --guided
```

## Troubleshooting

### Common Issues

1. **"MVP template missing" error**
   - **Cause:** Using old workflow file
   - **Fix:** Ensure using `deploy-ultra-simple.yml` not `deploy-mvp.yml`

2. **AWS credentials error**
   - **Cause:** Missing or incorrect AWS secrets
   - **Fix:** Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to repository secrets

3. **SAM build fails**
   - **Cause:** Invalid template or missing dependencies
   - **Fix:** Test locally with `sam validate` and `sam build`

4. **Stack already exists**
   - **Cause:** Previous deployment with same name
   - **Fix:** Delete existing stack or use different environment name

### Debug Commands
```bash
# Check workflow syntax
cat .github/workflows/deploy-ultra-simple.yml | python -m yaml

# Test AWS credentials
aws sts get-caller-identity

# Check existing stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# Delete stack (if needed)
aws cloudformation delete-stack --stack-name form-bridge-ultra-test
```

## Cost Analysis

### Ultra-Simple Architecture
- **Lambda:** Free tier includes 1M requests/month
- **DynamoDB:** Free tier includes 25GB storage, 25 RCU, 25 WCU
- **Total:** $0.00/month for typical testing usage

### When to Upgrade
Consider upgrading to full architecture when:
- Processing > 10K forms/month
- Need admin UI for monitoring
- Require advanced routing/filtering
- Need multiple destination integrations

## Security Notes

### Development
- Uses hardcoded HMAC secret: `development-secret-change-in-production`
- Function URL with no AWS auth (handles auth in function)
- CORS allows all origins

### Production Recommendations
1. Use AWS Secrets Manager for HMAC secret
2. Restrict CORS origins to your domains
3. Enable CloudWatch detailed monitoring
4. Set up alarms for errors/throttling
5. Configure DynamoDB backups

## Contributing

### Adding New Features
1. Modify files in `ultra-simple/` directory
2. Push to feature branch
3. Create PR to main/develop
4. Workflow will validate changes
5. Merge to deploy automatically

### Workflow Modifications
1. Edit `.github/workflows/deploy-ultra-simple.yml`
2. Test with validation script
3. Create PR with changes
4. Test deployment in test environment first

## Support

### Resources
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Lambda Function URLs](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html)

### Getting Help
1. Check workflow logs in Actions tab
2. Review CloudFormation events in AWS Console
3. Check Lambda logs in CloudWatch
4. Open issue in repository with error details
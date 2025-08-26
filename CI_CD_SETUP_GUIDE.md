# Form-Bridge CI/CD Setup Guide

## Overview
This guide provides the complete setup for Form-Bridge CI/CD infrastructure using GitHub Actions and AWS CloudFormation. All infrastructure is defined as code with zero manual deployment steps after initial setup.

## Phase 0: CI/CD Pipeline Foundation

### Step 1: Create IAM User for GitHub Actions (Temporary)

**IMPORTANT**: This is a temporary step. We'll switch to OIDC authentication in Step 2 for better security.

Run these commands in your AWS CLI:

```bash
# Create IAM user for GitHub Actions
aws iam create-user --user-name formbridge-github-actions

# Create access keys (save these securely)
aws iam create-access-key --user-name formbridge-github-actions

# Attach PowerUser policy (temporary - will be restricted later)
aws iam attach-user-policy \
  --user-name formbridge-github-actions \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Add CloudFormation permissions
aws iam put-user-policy \
  --user-name formbridge-github-actions \
  --policy-name CloudFormationFullAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "cloudformation:*",
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:PassRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:CreateOIDCProvider",
          "iam:DeleteOIDCProvider",
          "iam:UpdateOIDCProvider"
        ],
        "Resource": "*"
      }
    ]
  }'
```

### Step 2: Configure GitHub Repository Secrets

Go to your GitHub repository: https://github.com/billybuilds/form-bridge

Navigate to: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:

| Secret Name | Value | Description |
|-------------|--------|-------------|
| `AWS_ACCESS_KEY_ID` | From Step 1 output | Temporary access key |
| `AWS_SECRET_ACCESS_KEY` | From Step 1 output | Temporary secret key |
| `AWS_ACCOUNT_ID` | Your AWS Account ID | Get with: `aws sts get-caller-identity --query Account --output text` |

### Step 3: Configure GitHub Repository Variables

Navigate to: **Settings → Secrets and variables → Actions → Variables tab → New repository variable**

Add these variables:

| Variable Name | Value | Description |
|---------------|--------|-------------|
| `AWS_DEFAULT_REGION` | `us-east-1` | Primary deployment region |

### Step 4: Deploy OIDC Provider (Secure Authentication)

Deploy the OIDC provider stack:

```bash
aws cloudformation create-stack \
  --stack-name formbridge-github-oidc \
  --template-body file://infrastructure/oidc-provider.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags Key=Application,Value=FormBridge Key=Environment,Value=infrastructure

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name formbridge-github-oidc

# Get the role ARN (you'll need this)
aws cloudformation describe-stacks \
  --stack-name formbridge-github-oidc \
  --query 'Stacks[0].Outputs[?OutputKey==`RoleArn`].OutputValue' \
  --output text
```

### Step 5: Deploy S3 Deployment Bucket

Deploy the S3 bucket for SAM artifacts:

```bash
aws cloudformation create-stack \
  --stack-name formbridge-deployment-bucket \
  --template-body file://infrastructure/deployment-bucket.yaml \
  --tags Key=Application,Value=FormBridge Key=Environment,Value=infrastructure

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name formbridge-deployment-bucket

# Verify bucket was created
aws s3 ls s3://formbridge-deployment-$(aws sts get-caller-identity --query Account --output text)/
```

### Step 6: Test GitHub Actions Deployment

Trigger the deployment workflow:

```bash
# Using GitHub CLI
gh workflow run deploy.yml --ref main -f environment=dev

# Or commit and push to main branch to trigger automatically
git add .
git commit -m "Add CI/CD infrastructure

- OIDC provider for secure GitHub Actions authentication
- S3 deployment bucket for SAM artifacts  
- Complete deployment workflow with validation
- Automated environment-based deployments

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
```

### Step 7: Remove Temporary IAM User (Security Cleanup)

After OIDC is working, remove the temporary IAM user:

```bash
# Detach policies
aws iam detach-user-policy \
  --user-name formbridge-github-actions \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

aws iam delete-user-policy \
  --user-name formbridge-github-actions \
  --policy-name CloudFormationFullAccess

# Delete access keys (list them first)
aws iam list-access-keys --user-name formbridge-github-actions

# Delete each key (replace with actual AccessKeyId)
aws iam delete-access-key \
  --user-name formbridge-github-actions \
  --access-key-id AKIA...

# Delete user
aws iam delete-user --user-name formbridge-github-actions

# Remove secrets from GitHub (go to repository settings)
# Delete: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

## Deployment Commands

### Manual Deployment Commands

For local testing or emergency deployments:

```bash
# Deploy infrastructure prerequisites
aws cloudformation create-stack \
  --stack-name formbridge-github-oidc \
  --template-body file://infrastructure/oidc-provider.yaml \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation create-stack \
  --stack-name formbridge-deployment-bucket \
  --template-body file://infrastructure/deployment-bucket.yaml

# Deploy main application (requires SAM CLI)
sam build --template template-arm64-optimized.yaml
sam deploy \
  --stack-name formbridge-dev \
  --s3-bucket formbridge-deployment-$(aws sts get-caller-identity --query Account --output text) \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides Environment=dev
```

### Validation Commands

Verify deployments are working:

```bash
# Check OIDC stack
aws cloudformation describe-stacks --stack-name formbridge-github-oidc

# Check deployment bucket
aws s3 ls s3://formbridge-deployment-$(aws sts get-caller-identity --query Account --output text)/

# Check main application stack
aws cloudformation describe-stacks --stack-name formbridge-dev

# Get API endpoint
aws cloudformation describe-stacks \
  --stack-name formbridge-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayEndpoint`].OutputValue' \
  --output text
```

## Troubleshooting

### Common Issues

1. **OIDC Authentication Failed**
   - Verify GitHub repository name in trust policy: `billybuilds/form-bridge`
   - Check that AWS_ACCOUNT_ID secret is correct
   - Ensure OIDC provider stack deployed successfully

2. **S3 Bucket Already Exists**
   - Bucket names are globally unique
   - The template uses your account ID as suffix to avoid conflicts
   - Check if bucket exists in different region

3. **CloudFormation Stack Creation Failed**
   - Check CloudFormation events in AWS Console
   - Verify IAM permissions
   - Look for resource naming conflicts

4. **SAM Deploy Failed**
   - Ensure S3 bucket exists and is accessible
   - Check that all dependencies are in requirements.txt
   - Verify SAM CLI is latest version

### Rollback Procedures

If deployment fails:

```bash
# Delete failed stacks (in reverse order)
aws cloudformation delete-stack --stack-name formbridge-dev
aws cloudformation delete-stack --stack-name formbridge-deployment-bucket
aws cloudformation delete-stack --stack-name formbridge-github-oidc

# Wait for deletions to complete
aws cloudformation wait stack-delete-complete --stack-name formbridge-dev
```

## Security Notes

1. **OIDC vs IAM User**: OIDC is more secure as it uses temporary credentials and doesn't require long-lived access keys
2. **Least Privilege**: The GitHub Actions role uses PowerUserAccess initially but should be restricted after testing
3. **Secret Management**: Never commit AWS credentials to Git. Use GitHub Secrets only
4. **Bucket Security**: S3 deployment bucket has public access blocked and requires SSL

## Environment Management

The workflow supports three environments:

- **dev**: Deployed on push to develop branch or manual trigger
- **staging**: Deployed on push to main branch (you can modify this)
- **prod**: Manual deployment only via workflow_dispatch

Stack naming convention: `formbridge-{environment}`

## Cost Optimization

Expected costs for CI/CD infrastructure:

- CloudFormation: Free (pay for underlying resources only)
- S3 Deployment Bucket: ~$1-2/month
- GitHub Actions: Free for public repos, $0.008/minute for private
- OIDC Provider: Free

Total estimated cost: < $5/month

## Next Steps

After CI/CD is working:

1. **Phase 1**: Deploy foundational AWS resources (DynamoDB, EventBridge, etc.)
2. **Phase 2**: Deploy Lambda functions
3. **Phase 3**: Configure API Gateway
4. **Phase 4**: Set up monitoring and logging
5. **Phase 5**: Deploy frontend dashboard

Each phase will be automated through the same CI/CD pipeline.
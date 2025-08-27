# GitHub Actions Deployment Setup

This guide explains how to set up GitHub Actions for automated deployment of the Form-Bridge Ultra-Simple architecture.

## Architecture Overview

The ultra-simple architecture includes:
- **Single Lambda Function** (128MB, Python 3.12, x86_64)
- **DynamoDB Table** (pay-per-request, TTL enabled)
- **Function URL** (direct HTTPS endpoint, no API Gateway)
- **CloudWatch Logging** (7-day retention)

**Estimated Cost:** $0.00 - $0.50/month for testing workloads

## Required GitHub Secrets

Add these secrets in your GitHub repository settings (`Settings > Secrets and variables > Actions`):

### AWS Credentials
- **`AWS_ACCESS_KEY_ID`** - AWS Access Key ID for deployment user
- **`AWS_SECRET_ACCESS_KEY`** - AWS Secret Access Key for deployment user

### Optional Notifications
- **`SLACK_WEBHOOK_URL`** (optional) - Slack webhook for cost alerts

## AWS IAM Setup

Create a dedicated IAM user for GitHub Actions with these permissions:

### IAM Policy: `GitHubActions-FormBridge-Deploy`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:ValidateTemplate"
      ],
      "Resource": [
        "arn:aws:cloudformation:us-east-1:*:stack/form-bridge-ultra-simple-*",
        "arn:aws:cloudformation:us-east-1:*:stack/aws-sam-cli-managed-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:ListTags",
        "lambda:TagResource",
        "lambda:UntagResource",
        "lambda:CreateFunctionUrlConfig",
        "lambda:UpdateFunctionUrlConfig",
        "lambda:DeleteFunctionUrlConfig",
        "lambda:GetFunctionUrlConfig",
        "lambda:AddPermission",
        "lambda:RemovePermission"
      ],
      "Resource": "arn:aws:lambda:us-east-1:*:function:form-bridge-ultra-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:UpdateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:TagResource",
        "dynamodb:UntagResource",
        "dynamodb:ListTagsOfResource",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/form-bridge-ultra-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy"
      ],
      "Resource": "arn:aws:iam::*:role/form-bridge-ultra-simple-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy",
        "logs:DeleteLogGroup"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/aws/lambda/form-bridge-ultra-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::aws-sam-cli-managed-*",
        "arn:aws:s3:::aws-sam-cli-managed-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

### Create IAM User

```bash
# Create user
aws iam create-user --user-name github-actions-form-bridge

# Attach policy (after creating the policy above)
aws iam attach-user-policy \
  --user-name github-actions-form-bridge \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/GitHubActions-FormBridge-Deploy

# Create access keys
aws iam create-access-key --user-name github-actions-form-bridge
```

## GitHub Environments Setup

Configure these environments in your repository (`Settings > Environments`):

### Test Environment
- **Name:** `test`
- **Protection Rules:** None (automatic deployment)
- **Environment Secrets:** None needed (uses repository secrets)

### Production Environment  
- **Name:** `production`
- **Protection Rules:** 
  - ✅ Required reviewers (at least 1)
  - ✅ Wait timer (optional, e.g., 5 minutes)
- **Environment Secrets:** None needed (uses repository secrets)

## Workflow Triggers

### Automatic Deployment (Test)
- **Push to `main`** with changes in `ultra-simple/` directory
- Automatically deploys to test environment
- Runs validation and smoke tests

### Manual Deployment (Production)
- **Workflow Dispatch** (manual trigger)
- Select environment: `test` or `prod`
- Production requires manual approval

### Cost Monitoring
- **Daily at 9 AM UTC** (automatic)
- **Manual trigger** available
- Alerts if costs exceed $5/month

## Deployment Workflow Steps

### 1. Validation
- CloudFormation template linting
- Python code compilation
- Unit tests (if available)

### 2. Build & Deploy
- SAM build (cached for speed)
- CloudFormation deployment
- Stack outputs capture

### 3. Smoke Tests
- CORS preflight test
- Valid form submission test
- Invalid HMAC rejection test
- DynamoDB data verification

### 4. Cost Monitoring
- Current month cost analysis
- Resource usage metrics
- Threshold alerts ($5/month)

## Expected Deployment Time

- **Total Time:** 3-5 minutes
- Build: ~1 minute
- Deploy: ~2-3 minutes  
- Tests: ~30 seconds

## Output URLs

After successful deployment, the workflow provides:

### Test Environment
- **Function URL:** `https://xyz.lambda-url.us-east-1.on.aws/`
- **Stack Name:** `form-bridge-ultra-simple-test`
- **Table Name:** `form-bridge-ultra-test`

### Production Environment
- **Function URL:** `https://abc.lambda-url.us-east-1.on.aws/`
- **Stack Name:** `form-bridge-ultra-simple-prod`  
- **Table Name:** `form-bridge-ultra-prod`

## WordPress Plugin Configuration

Use the Function URL in your WordPress plugin:

```php
// wp-config.php or plugin configuration
define('FORM_BRIDGE_ENDPOINT', 'https://xyz.lambda-url.us-east-1.on.aws/');
define('FORM_BRIDGE_SECRET', 'development-secret-change-in-production');
```

## Monitoring & Debugging

### View Deployment Logs
- GitHub Actions tab > Select workflow run
- Check each job for detailed logs

### Monitor AWS Resources
```bash
# Function logs
aws logs tail /aws/lambda/form-bridge-ultra-test --follow

# DynamoDB data
aws dynamodb query \
  --table-name form-bridge-ultra-test \
  --key-condition-expression 'PK = :pk' \
  --expression-attribute-values '":pk":{"S":"SUBMISSION"}' \
  --limit 5

# Stack status
aws cloudformation describe-stacks \
  --stack-name form-bridge-ultra-simple-test
```

### Cost Analysis
```bash
# Current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter '{"Tags":{"Key":"Project","Values":["FormBridge-Ultra"]}}'
```

## Troubleshooting

### Common Issues

1. **IAM Permission Errors**
   - Verify IAM policy includes all required actions
   - Check resource ARN patterns match your account/region

2. **Stack Already Exists**
   - Delete existing stack: `aws cloudformation delete-stack --stack-name STACK_NAME`
   - Or update workflow to use different stack name

3. **Lambda Timeout**
   - Ultra-simple architecture uses minimal resources
   - Should complete in <15 seconds typically

4. **DynamoDB Access Denied**
   - Verify DynamoDB permissions in IAM policy
   - Check table name matches template output

### Getting Help

1. **Check GitHub Actions Logs** - Most detailed error information
2. **Check CloudFormation Events** - AWS Console > CloudFormation
3. **Check Lambda Logs** - CloudWatch Logs
4. **Cost Analysis** - AWS Cost Explorer

## Security Best Practices

1. **Rotate Access Keys** - Every 90 days
2. **Use Least Privilege** - Only grant necessary permissions
3. **Monitor Costs** - Set up billing alerts
4. **Review Logs** - Check for unusual activity
5. **Update HMAC Secret** - Change from default in production

## Next Steps

After successful deployment:

1. **Test WordPress Integration** - Submit test forms
2. **Monitor Costs** - Check daily cost monitoring workflow
3. **Set Up Alerts** - AWS billing alerts as backup
4. **Plan Scaling** - Consider full architecture when you reach 10K+ requests/month

---

**Estimated Setup Time:** 15-30 minutes  
**First Deployment:** 5 minutes  
**Subsequent Deployments:** 3 minutes
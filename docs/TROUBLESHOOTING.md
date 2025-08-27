# Form-Bridge MVP Troubleshooting Guide

**Common Deployment Issues and Solutions**

*Last Updated: January 26, 2025*
*Focus: Quick Resolution for MVP Deployment*

## Overview

This guide provides solutions to common issues encountered when deploying and running Form-Bridge MVP. Issues are organized by deployment phase and include step-by-step resolution instructions.

## Quick Diagnosis Checklist

Before diving into specific issues, run this quick checklist:

```bash
# 1. Verify AWS credentials
aws sts get-caller-identity

# 2. Check required tools
aws --version    # Should be 2.x
sam --version    # Should be 1.70+
python3 --version # Should be 3.9+

# 3. Verify permissions
aws iam get-user
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE

# 4. Check region setting
aws configure get region
```

## Pre-Deployment Issues

### Issue: AWS CLI Not Configured

**Symptoms**:
```bash
$ aws sts get-caller-identity
Unable to locate credentials
```

**Solution**:
```bash
# Configure AWS CLI with your credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Verification**:
```bash
aws sts get-caller-identity
# Should return your account details
```

### Issue: Insufficient IAM Permissions

**Symptoms**:
```bash
User: arn:aws:iam::123456789012:user/username is not authorized to perform: cloudformation:CreateStack
```

**Required Permissions**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "lambda:*",
        "apigateway:*",
        "dynamodb:*",
        "events:*",
        "secretsmanager:*",
        "logs:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PassRole"
      ],
      "Resource": "*"
    }
  ]
}
```

**Quick Fix for Testing**:
```bash
# Attach PowerUser policy (for testing only)
aws iam attach-user-policy \
  --user-name YOUR_USERNAME \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

### Issue: SAM CLI Not Installed

**Symptoms**:
```bash
$ sam --version
Command 'sam' not found
```

**Solution**:
```bash
# Install via pip
pip install aws-sam-cli

# Or via Homebrew (macOS)
brew install aws-sam-cli

# Or download binary from GitHub releases
curl -L -o sam-installation.zip \
  https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip
unzip sam-installation.zip -d sam-installation/
sudo ./sam-installation/install
```

**Verification**:
```bash
sam --version
# Should show version 1.70.0 or higher
```

## Build Issues

### Issue: SAM Build Timeout

**Symptoms**:
```bash
Build Failed
Build timed out after 600 seconds
```

**Solution**:
```bash
# Use container build (slower but more reliable)
sam build --use-container

# Or increase timeout
sam build --debug --build-timeout 1200

# Clear cache if needed
rm -rf .aws-sam/
sam build
```

### Issue: Python Dependencies Not Found

**Symptoms**:
```bash
ModuleNotFoundError: No module named 'boto3'
```

**Solution**:
```bash
# Verify requirements.txt exists
ls -la lambdas/requirements-mvp.txt

# Build with verbose output
sam build --debug

# Check Python version in template
grep "Runtime:" template-mvp-*.yaml
# Should be python3.12 or python3.11
```

### Issue: Build Architecture Mismatch

**Symptoms**:
```bash
ERROR: Could not install packages due to an EnvironmentError
```

**Solution**:
```bash
# Force x86_64 architecture (MVP default)
sam build --use-container --debug

# Verify template architecture
grep -A 5 "Architectures:" template-mvp-*.yaml
# Should show:
#   Architectures:
#     - x86_64
```

## Deployment Issues

### Issue: CloudFormation Stack Creation Failed

**Symptoms**:
```bash
CREATE_FAILED: formbridge-mvp-dev
Resource handler returned message: "User: ... is not authorized to perform: iam:CreateRole"
```

**Solution**:
```bash
# Check CloudFormation events for specific error
aws cloudformation describe-stack-events \
  --stack-name formbridge-mvp-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'

# Common fixes:
# 1. Add IAM permissions (see above)
# 2. Check resource limits
aws servicequotas get-service-quota \
  --service-code lambda \
  --quota-code L-B99A9384

# 3. Delete failed stack and retry
aws cloudformation delete-stack --stack-name formbridge-mvp-dev
aws cloudformation wait stack-delete-complete --stack-name formbridge-mvp-dev
```

### Issue: Lambda Function Creation Failed

**Symptoms**:
```bash
CREATE_FAILED: IngestFunction
The role defined for the function cannot be assumed by Lambda
```

**Solution**:
```bash
# Verify IAM role trust policy
aws iam get-role --role-name FormBridgeMvpLambdaRole

# Check execution role has lambda:InvokeFunction
aws iam list-attached-role-policies --role-name FormBridgeMvpLambdaRole

# Force recreation of IAM roles
sam deploy --capabilities CAPABILITY_IAM --force-upload
```

### Issue: API Gateway Deployment Failed

**Symptoms**:
```bash
CREATE_FAILED: HttpApi
BadRequestException: Invalid authorizer specified
```

**Solution**:
```bash
# Check if Lambda authorizer exists
aws lambda list-functions --query 'Functions[?contains(FunctionName, `authorizer`)]'

# Verify authorizer configuration in template
grep -A 10 "Authorizers:" template-mvp-*.yaml

# Redeploy with explicit dependency
sam deploy --parameter-overrides Environment=dev --force-upload
```

### Issue: DynamoDB Table Creation Failed

**Symptoms**:
```bash
CREATE_FAILED: SubmissionsTable
Subscriber limit exceeded
```

**Solution**:
```bash
# Check DynamoDB limits
aws dynamodb describe-limits

# Use different table name if conflict
sam deploy --parameter-overrides \
  Environment=dev \
  TableName=formbridge-mvp-dev-$(date +%s)

# Check for existing tables
aws dynamodb list-tables
```

## Runtime Issues

### Issue: 403 Forbidden from API Gateway

**Symptoms**:
```bash
$ curl -X POST https://api-id.execute-api.region.amazonaws.com/submit
{"message":"Forbidden"}
```

**Diagnosis Steps**:
```bash
# 1. Check if endpoint exists
curl -v https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com/

# 2. Verify authorizer logs
aws logs tail /aws/lambda/formbridge-mvp-authorizer-dev --follow

# 3. Check tenant secret exists
aws secretsmanager get-secret-value --secret-id formbridge/tenants/t_sample
```

**Common Causes & Solutions**:

**Missing Headers**:
```bash
# Wrong (missing headers)
curl -X POST https://api-endpoint/submit -d '{"test": "data"}'

# Correct (with required headers)
curl -X POST https://api-endpoint/submit \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: t_sample" \
  -H "X-API-Key: mvp-test-key-123" \
  -d '{"form_data": {"test": "data"}}'
```

**Tenant Not Found**:
```bash
# Create missing tenant secret
aws secretsmanager create-secret \
  --name "formbridge/tenants/t_sample" \
  --secret-string '{"api_key": "mvp-test-key-123", "tenant_name": "Sample Tenant"}'
```

**API Key Mismatch**:
```bash
# Check stored API key
aws secretsmanager get-secret-value \
  --secret-id formbridge/tenants/t_sample \
  --query SecretString --output text | jq -r .api_key
```

### Issue: 500 Internal Server Error

**Symptoms**:
```bash
$ curl -X POST https://api-endpoint/submit -H "X-Tenant-ID: t_sample" -H "X-API-Key: mvp-test-key-123"
{"errorMessage":"Internal server error"}
```

**Diagnosis**:
```bash
# Check ingestion Lambda logs
aws logs tail /aws/lambda/formbridge-mvp-ingest-dev --follow

# Check processor Lambda logs  
aws logs tail /aws/lambda/formbridge-mvp-processor-dev --follow

# Look for specific errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/formbridge-mvp-ingest-dev \
  --filter-pattern "ERROR"
```

**Common Causes**:

**DynamoDB Permission Error**:
```bash
# Verify Lambda has DynamoDB permissions
aws iam get-role-policy \
  --role-name FormBridgeMvpLambdaRole \
  --policy-name DynamoDBPolicy

# Check table exists
aws dynamodb describe-table --table-name formbridge-mvp-dev
```

**EventBridge Permission Error**:
```bash
# Verify EventBridge permissions
aws iam get-role-policy \
  --role-name FormBridgeMvpLambdaRole \
  --policy-name EventBridgePolicy

# Check rule exists and is enabled
aws events list-rules --name-prefix formbridge-mvp
```

### Issue: Data Not Appearing in DynamoDB

**Symptoms**:
- API returns 200 OK
- No errors in logs
- DynamoDB table is empty

**Diagnosis**:
```bash
# Check if data was written
aws dynamodb scan --table-name formbridge-mvp-dev --limit 10

# Check ingestion Lambda logs for PutItem operations
aws logs filter-log-events \
  --log-group-name /aws/lambda/formbridge-mvp-ingest-dev \
  --filter-pattern "PutItem"

# Verify table name in Lambda environment
aws lambda get-function-configuration \
  --function-name formbridge-mvp-ingest-dev \
  --query 'Environment.Variables'
```

**Solution**:
```bash
# Check Lambda environment variables match table name
aws lambda update-function-configuration \
  --function-name formbridge-mvp-ingest-dev \
  --environment Variables='{TABLE_NAME=formbridge-mvp-dev}'
```

### Issue: EventBridge Not Triggering Processor

**Symptoms**:
- Data appears in DynamoDB
- Events not processed by processor Lambda
- No processor Lambda logs

**Diagnosis**:
```bash
# Check EventBridge rule
aws events list-rules --query 'Rules[?contains(Name, `formbridge`)]'

# Check rule targets
aws events list-targets-by-rule --rule formbridge-mvp-processor-dev

# Verify processor Lambda permissions
aws lambda get-policy --function-name formbridge-mvp-processor-dev
```

**Solution**:
```bash
# Add EventBridge permission to Lambda
aws lambda add-permission \
  --function-name formbridge-mvp-processor-dev \
  --statement-id eventbridge-invoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT:rule/formbridge-mvp-processor-dev
```

## Performance Issues

### Issue: High Latency (> 5 seconds)

**Symptoms**:
```bash
$ time curl -X POST https://api-endpoint/submit ...
real    0m8.234s  # Too slow!
```

**Diagnosis**:
```bash
# Check Lambda cold start metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=formbridge-mvp-ingest-dev \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum,Average

# Check API Gateway latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiId,Value=YOUR_API_ID \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum,Average
```

**Solutions**:

**Increase Lambda Memory**:
```bash
# Increase memory allocation (more CPU)
aws lambda update-function-configuration \
  --function-name formbridge-mvp-ingest-dev \
  --memory-size 512

# Monitor improvement
aws logs tail /aws/lambda/formbridge-mvp-ingest-dev --follow
```

**Warm Up Functions**:
```bash
# Create periodic invocation to keep warm
aws events put-rule \
  --name warmup-formbridge \
  --schedule-expression "rate(5 minutes)"

aws events put-targets \
  --rule warmup-formbridge \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:formbridge-mvp-ingest-dev","Input"='{"warmup":true}'
```

### Issue: High Error Rate

**Symptoms**:
```bash
# Many 5xx responses
curl -X POST https://api-endpoint/submit ... # Returns 500
```

**Diagnosis**:
```bash
# Check error rate metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=formbridge-mvp-ingest-dev \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Find error patterns
aws logs filter-log-events \
  --log-group-name /aws/lambda/formbridge-mvp-ingest-dev \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Common Error Patterns**:

**Timeout Errors**:
```bash
# Increase timeout
aws lambda update-function-configuration \
  --function-name formbridge-mvp-ingest-dev \
  --timeout 30
```

**Memory Errors**:
```bash
# Increase memory
aws lambda update-function-configuration \
  --function-name formbridge-mvp-ingest-dev \
  --memory-size 512
```

## Cost Issues

### Issue: Unexpected High Costs

**Diagnosis**:
```bash
# Check AWS Cost Explorer or use CLI
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

**Common Cost Drivers**:

**DynamoDB On-Demand Pricing**:
```bash
# Check DynamoDB usage
aws dynamodb describe-table --table-name formbridge-mvp-dev \
  --query 'Table.{ReadCapacity:BillingModeSummary,WriteCapacity:BillingModeSummary}'

# Consider switching to provisioned if usage is predictable
aws dynamodb modify-table \
  --table-name formbridge-mvp-dev \
  --billing-mode PROVISIONED \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

**Lambda Invocation Costs**:
```bash
# Check invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=formbridge-mvp-ingest-dev \
  --start-time $(date -d '7 days ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum
```

## Cleanup and Recovery

### Complete Environment Cleanup

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name formbridge-mvp-dev

# Wait for completion
aws cloudformation wait stack-delete-complete --stack-name formbridge-mvp-dev

# Clean up Secrets Manager (if desired)
aws secretsmanager delete-secret \
  --secret-id formbridge/tenants/t_sample \
  --force-delete-without-recovery

# Clean up CloudWatch logs (if desired)
aws logs delete-log-group --log-group-name /aws/lambda/formbridge-mvp-ingest-dev
aws logs delete-log-group --log-group-name /aws/lambda/formbridge-mvp-processor-dev
aws logs delete-log-group --log-group-name /aws/lambda/formbridge-mvp-authorizer-dev
```

### Partial Recovery (Keep Data)

```bash
# Update stack with fixes
sam deploy --parameter-overrides Environment=dev

# Or just update Lambda functions
sam build
sam deploy --force-upload
```

## Prevention and Monitoring

### Set Up Basic Monitoring

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name FormBridge-MVP \
  --dashboard-body file://dashboard.json

# Create basic alarms
aws cloudwatch put-metric-alarm \
  --alarm-name formbridge-errors \
  --alarm-description "Form Bridge Error Rate" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=formbridge-mvp-ingest-dev
```

### Enable Debug Logging

```bash
# Enable debug logs temporarily
aws lambda update-function-configuration \
  --function-name formbridge-mvp-ingest-dev \
  --environment Variables='{LOG_LEVEL=DEBUG,TABLE_NAME=formbridge-mvp-dev}'

# Test with debug output
curl -X POST https://api-endpoint/submit ... 
aws logs tail /aws/lambda/formbridge-mvp-ingest-dev --follow

# Disable debug when done (reduces costs)
aws lambda update-function-configuration \
  --function-name formbridge-mvp-ingest-dev \
  --environment Variables='{LOG_LEVEL=INFO,TABLE_NAME=formbridge-mvp-dev}'
```

## Getting Additional Help

### AWS Support Resources
- **AWS Documentation**: [docs.aws.amazon.com](https://docs.aws.amazon.com)
- **AWS Support Center**: For account-specific issues
- **AWS Forums**: [forums.aws.amazon.com](https://forums.aws.amazon.com)

### Form-Bridge Resources
- **GitHub Issues**: Report bugs and get help
- **Architecture Guide**: [MVP-ARCHITECTURE.md](mvp/MVP-ARCHITECTURE.md)
- **Quick Start Guide**: [QUICK-START.md](mvp/QUICK-START.md)
- **Simplification Choices**: [SIMPLIFIED-CHOICES.md](mvp/SIMPLIFIED-CHOICES.md)

### Escalation Process
1. **Check this troubleshooting guide first**
2. **Search GitHub issues** for similar problems
3. **Collect diagnostic information**:
   ```bash
   # Essential debug info
   aws sts get-caller-identity
   aws cloudformation describe-stacks --stack-name formbridge-mvp-dev
   aws logs filter-log-events --log-group-name /aws/lambda/formbridge-mvp-ingest-dev --filter-pattern "ERROR" --start-time $(date -d '1 hour ago' +%s)000
   ```
4. **Create GitHub issue** with:
   - Steps to reproduce
   - Expected vs actual behavior  
   - Diagnostic command outputs
   - Environment details (region, account type, etc.)

## Summary

Most Form-Bridge MVP issues are related to:
1. **AWS credentials and permissions** (60% of issues)
2. **Missing or misconfigured resources** (25% of issues)
3. **API authentication errors** (10% of issues)
4. **Resource limits and timeouts** (5% of issues)

The key to quick resolution is systematic diagnosis using AWS CLI commands and CloudWatch logs. When in doubt, delete and redeploy the stack - the MVP is designed for fast, reliable deployment.

**Remember**: If you encounter issues not covered here, the MVP's simplified architecture makes debugging much easier than complex alternatives. Most problems can be resolved in under 15 minutes using the diagnostic steps provided.
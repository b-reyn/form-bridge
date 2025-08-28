# MVP Build-Deploy-Validate Implementation Plan

## Executive Summary
This document provides a **comprehensive, step-by-step implementation plan** for deploying the Form-Bridge MVP from zero infrastructure to a fully operational multi-tenant form processing system. Every component follows a strict **Build-Deploy-Validate** pattern with zero manual intervention after initial setup.

**Current Status**: All code written, nothing deployed
**Target Architecture**: EventBridge-centric serverless (Option A)
**Deployment Method**: GitHub Actions + SAM/CloudFormation
**URLs**:
- UI: formbridge.billybuilds.ai  
- API: api.formbridge.billybuilds.ai

---

## Phase 0: CI/CD Pipeline Foundation (CRITICAL - DO THIS FIRST)

### 0.1 GitHub Secrets Configuration
**Description**: Set up AWS credentials and environment variables for automated deployment
**Documentation**: AWS IAM Best Practices, GitHub Actions Secrets
**Agent**: cicd-cloudformation-engineer
**Dependencies**: GitHub repository access, AWS account

#### Build:
- [ ] Create IAM user for GitHub Actions with programmatic access
- [ ] Generate access keys (temporary - will switch to OIDC in 0.2)
- [ ] Document all required secrets

#### Deploy:
```bash
# Add these secrets to GitHub repository settings:
# Settings → Secrets and variables → Actions → New repository secret

AWS_ACCESS_KEY_ID         # From IAM user
AWS_SECRET_ACCESS_KEY      # From IAM user  
AWS_DEFAULT_REGION         # us-east-1
AWS_ACCOUNT_ID            # Your AWS account number
ENVIRONMENT               # dev (initially)
```

#### Validate:
```bash
# Test secret access via workflow dispatch
gh workflow run test-suite.yml --ref main
gh run watch
```

---

### 0.2 OIDC Authentication Setup
**Description**: Replace IAM keys with secure OIDC provider for GitHub Actions
**Documentation**: /docs/security/README.md, AWS OIDC documentation
**Agent**: cicd-cloudformation-engineer
**Dependencies**: 0.1 completed

#### Build:
- [ ] Create CloudFormation template for OIDC provider: `infrastructure/oidc-provider.yaml`
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: GitHub Actions OIDC Provider for Form-Bridge

Resources:
  GitHubOIDCProvider:
    Type: AWS::IAM::OIDCProvider
    Properties:
      Url: https://token.actions.githubusercontent.com
      ClientIdList:
        - sts.amazonaws.com
      ThumbprintList:
        - 6938fd4d98bab03faadb97b34396831e3780aea1
        
  GitHubActionsRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: GitHubActionsDeploymentRole
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Federated: !Ref GitHubOIDCProvider
            Action: sts:AssumeRoleWithWebIdentity
            Condition:
              StringLike:
                token.actions.githubusercontent.com:sub: repo:YOUR_ORG/form-bridge:*
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/PowerUserAccess  # Refine later
      
Outputs:
  RoleArn:
    Value: !GetAtt GitHubActionsRole.Arn
    Description: ARN for GitHub Actions to assume
```

#### Deploy:
```bash
aws cloudformation create-stack \
  --stack-name formbridge-github-oidc \
  --template-body file://infrastructure/oidc-provider.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Validate:
```bash
aws cloudformation describe-stacks \
  --stack-name formbridge-github-oidc \
  --query 'Stacks[0].Outputs'
```

---

### 0.3 GitHub Actions Deployment Workflow
**Description**: Create main deployment workflow using SAM and CloudFormation
**Documentation**: .github/workflows/test-suite.yml (existing), SAM CLI documentation
**Agent**: cicd-cloudformation-engineer  
**Dependencies**: 0.2 completed

#### Build:
- [ ] Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy Form-Bridge Infrastructure

on:
  push:
    branches: [main, develop]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        default: 'dev'
        type: choice
        options: ['dev', 'staging', 'prod']

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'dev' }}
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/GitHubActionsDeploymentRole
          aws-region: ${{ vars.AWS_DEFAULT_REGION }}
          
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
          
      - name: Setup SAM CLI
        uses: aws-actions/setup-sam@v2
        
      - name: Validate SAM template
        run: sam validate --template template-arm64-optimized.yaml
        
      - name: Build SAM application
        run: sam build --template template-arm64-optimized.yaml
        
      - name: Deploy SAM application
        run: |
          sam deploy \
            --stack-name formbridge-${{ github.event.inputs.environment || 'dev' }} \
            --s3-bucket formbridge-deployment-${{ secrets.AWS_ACCOUNT_ID }} \
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
            --parameter-overrides \
              Environment=${{ github.event.inputs.environment || 'dev' }} \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset
```

#### Deploy:
```bash
git add .github/workflows/deploy.yml
git commit -m "Add deployment workflow"
git push origin main
```

#### Validate:
```bash
# Trigger deployment
gh workflow run deploy.yml --ref main -f environment=dev

# Watch deployment
gh run watch

# Verify stack creation
aws cloudformation describe-stacks --stack-name formbridge-dev
```

---

## Phase 1: Foundational AWS Resources

### 1.1 S3 Deployment Bucket
**Description**: S3 bucket for SAM deployment artifacts
**Documentation**: SAM deployment guide
**Agent**: aws-infrastructure-engineer
**Dependencies**: Phase 0 completed

#### Build:
- [ ] Create `infrastructure/deployment-bucket.yaml`:
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Deployment bucket for SAM artifacts

Parameters:
  BucketName:
    Type: String
    Default: formbridge-deployment

Resources:
  DeploymentBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${BucketName}-${AWS::AccountId}'
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      VersioningConfiguration:
        Status: Enabled
        
Outputs:
  BucketName:
    Value: !Ref DeploymentBucket
    Export:
      Name: formbridge-deployment-bucket
```

#### Deploy:
```bash
aws cloudformation create-stack \
  --stack-name formbridge-deployment-bucket \
  --template-body file://infrastructure/deployment-bucket.yaml
```

#### Validate:
```bash
aws s3 ls s3://formbridge-deployment-$(aws sts get-caller-identity --query Account --output text)/
```

---

### 1.2 DynamoDB Tables
**Description**: Multi-tenant single-table design for submissions, destinations, and delivery attempts
**Documentation**: /docs/mvp/implementation/dynamodb-guide.md, /docs/mvp/architecture.md
**Agent**: dynamodb-architect
**Dependencies**: 1.1 completed

#### Build:
- [ ] Review existing template section in `/template-arm64-optimized.yaml` (lines 324-368)
- [ ] Verify indexes and attributes match architecture requirements

#### Deploy:
```bash
# Deploy via SAM (includes DynamoDB table)
sam deploy \
  --template-file template-arm64-optimized.yaml \
  --stack-name formbridge-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides Environment=dev
```

#### Validate:
```bash
# Verify table creation
aws dynamodb describe-table --table-name form-bridge-data

# Check GSI
aws dynamodb describe-table \
  --table-name form-bridge-data \
  --query 'Table.GlobalSecondaryIndexes[0]'
  
# Test write
aws dynamodb put-item \
  --table-name form-bridge-data \
  --item '{"PK":{"S":"TENANT#test"},"SK":{"S":"CONFIG#test"},"test":{"S":"true"}}'
```

---

### 1.3 Secrets Manager Setup
**Description**: Store per-tenant HMAC secrets and destination credentials
**Documentation**: /docs/mvp/architecture.md (lines 84-85), AWS Secrets Manager best practices
**Agent**: aws-infrastructure-engineer
**Dependencies**: 1.2 completed

#### Build:
- [ ] Create initial tenant secret creation script `scripts/create-tenant-secret.py`:
```python
import boto3
import json
import secrets

def create_tenant_secret(tenant_id):
    client = boto3.client('secretsmanager')
    secret_value = {
        'hmac_key': secrets.token_hex(32),
        'api_version': '1.0',
        'created': datetime.utcnow().isoformat()
    }
    
    response = client.create_secret(
        Name=f'formbridge/{tenant_id}',
        SecretString=json.dumps(secret_value),
        Tags=[
            {'Key': 'Application', 'Value': 'FormBridge'},
            {'Key': 'Tenant', 'Value': tenant_id}
        ]
    )
    return response['ARN']
```

#### Deploy:
```bash
# Create test tenant secret
python scripts/create-tenant-secret.py --tenant-id t_test001
```

#### Validate:
```bash
# Verify secret exists
aws secretsmanager describe-secret --secret-id formbridge/t_test001

# Test retrieval (DO NOT log in production)
aws secretsmanager get-secret-value \
  --secret-id formbridge/t_test001 \
  --query SecretString
```

---

### 1.4 EventBridge Custom Bus
**Description**: Central event bus for form submission routing
**Documentation**: /docs/mvp/architecture.md (lines 175-189)
**Agent**: eventbridge-architect
**Dependencies**: 1.3 completed

#### Build:
- [ ] Verify EventBridge configuration in template (lines 314-320)
- [ ] Prepare event rules configuration

#### Deploy:
```bash
# EventBridge bus is created as part of main SAM deployment
sam deploy \
  --template-file template-arm64-optimized.yaml \
  --stack-name formbridge-dev \
  --capabilities CAPABILITY_IAM
```

#### Validate:
```bash
# Verify bus exists
aws events describe-event-bus --name form-bridge-bus

# Test putting an event
aws events put-events \
  --entries '[{
    "Source": "test",
    "DetailType": "test",
    "Detail": "{\"test\": true}",
    "EventBusName": "form-bridge-bus"
  }]'
```

---

## Phase 2: Lambda Functions Deployment

### 2.1 Lambda Layers
**Description**: Shared dependencies and multi-tenant security utilities
**Documentation**: /template-arm64-optimized.yaml (lines 53-67)
**Agent**: lambda-serverless-expert
**Dependencies**: Phase 1 completed

#### Build:
- [ ] Create layer structure at `lambdas/layers/mt-security-layer/python/`:
```python
# lambdas/layers/mt-security-layer/python/mt_security.py
import hmac
import hashlib
import json
from datetime import datetime, timezone

class MultiTenantValidator:
    @staticmethod
    def validate_hmac(secret, timestamp, body, signature):
        message = f"{timestamp}\n{body}"
        expected = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
```

#### Deploy:
```bash
# Build and package layer
cd lambdas/layers/mt-security-layer
pip install -r requirements.txt -t python/
zip -r mt-security-layer.zip python/

# Deploy via SAM (includes layers)
sam build && sam deploy
```

#### Validate:
```bash
# List layers
aws lambda list-layers --query 'Layers[?contains(LayerName, `formbridge`)]'

# Get layer details
aws lambda get-layer-version \
  --layer-name formbridge-mt-security-dev \
  --version-number 1
```

---

### 2.2 HMAC Authorizer Function
**Description**: Lambda authorizer for API Gateway HMAC validation
**Documentation**: /lambdas/optimized-hmac-authorizer.py, /docs/mvp/architecture.md (lines 131-174)
**Agent**: lambda-serverless-expert
**Dependencies**: 2.1 completed

#### Build:
- [ ] Review existing code at `/lambdas/optimized-hmac-authorizer.py`
- [ ] Ensure proper error handling and logging

#### Deploy:
```bash
# Deploy via SAM (includes authorizer)
sam deploy \
  --stack-name formbridge-dev \
  --capabilities CAPABILITY_IAM
```

#### Validate:
```bash
# Get function details
aws lambda get-function --function-name formbridge-hmac-authorizer-dev

# Test invoke with sample event
aws lambda invoke \
  --function-name formbridge-hmac-authorizer-dev \
  --payload '{"headers":{"x-tenant-id":"t_test001","x-timestamp":"2025-01-26T12:00:00Z","x-signature":"test"},"body":"test"}' \
  response.json
  
cat response.json
```

---

### 2.3 Ingestion Lambda Function
**Description**: Main form submission ingestion endpoint
**Documentation**: /lambdas/eventbridge-optimized-publisher.py, /docs/mvp/architecture.md
**Agent**: lambda-serverless-expert
**Dependencies**: 2.2 completed

#### Build:
- [ ] Review `/lambdas/eventbridge-optimized-publisher.py`
- [ ] Verify EventBridge integration

#### Deploy:
```bash
# Included in main SAM deployment
sam deploy --stack-name formbridge-dev
```

#### Validate:
```bash
# Test function directly
aws lambda invoke \
  --function-name formbridge-ingest-dev \
  --payload '{"body":"{\"test\":true}","requestContext":{"authorizer":{"lambda":{"tenant_id":"t_test001"}}}}' \
  response.json

# Check EventBridge for published events
aws events list-rules --event-bus-name form-bridge-bus
```

---

### 2.4 Event Processor Function
**Description**: Processes events from EventBridge, persists to DynamoDB
**Documentation**: /lambdas/arm64-event-processor.py
**Agent**: lambda-serverless-expert
**Dependencies**: 2.3 completed

#### Build:
- [ ] Review `/lambdas/arm64-event-processor.py`
- [ ] Ensure DynamoDB integration works

#### Deploy:
```bash
sam deploy --stack-name formbridge-dev
```

#### Validate:
```bash
# Check EventBridge rule
aws events list-targets-by-rule \
  --rule PersistRule \
  --event-bus-name form-bridge-bus

# Verify function logs
aws logs tail /aws/lambda/formbridge-event-processor-dev --follow
```

---

### 2.5 Smart Connector Function
**Description**: Handles delivery to external destinations
**Documentation**: /lambdas/arm64-smart-connector.py, /docs/mvp/architecture.md (lines 245-293)
**Agent**: lambda-serverless-expert
**Dependencies**: 2.4 completed

#### Build:
- [ ] Review `/lambdas/arm64-smart-connector.py`
- [ ] Verify external API call handling

#### Deploy:
```bash
sam deploy --stack-name formbridge-dev
```

#### Validate:
```bash
# Test with mock destination
aws lambda invoke \
  --function-name formbridge-smart-connector-dev \
  --payload '{"destination":{"type":"rest","config":{"endpoint":"https://httpbin.org/post","auth":{"mode":"none"}}}}' \
  response.json
```

---

## Phase 3: API Gateway Configuration

### 3.1 REST API with HMAC Authorization
**Description**: API Gateway with custom HMAC authorizer
**Documentation**: /template-arm64-optimized.yaml (lines 227-270)
**Agent**: api-gateway-specialist
**Dependencies**: Phase 2 completed

#### Build:
- [ ] Verify API Gateway configuration in SAM template
- [ ] Ensure CORS settings are correct

#### Deploy:
```bash
# API Gateway created as part of SAM deployment
sam deploy --stack-name formbridge-dev
```

#### Validate:
```bash
# Get API endpoint
aws cloudformation describe-stacks \
  --stack-name formbridge-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayEndpoint`].OutputValue' \
  --output text

# Test endpoint (will fail auth without proper HMAC)
curl -X POST https://[API_ID].execute-api.us-east-1.amazonaws.com/dev/submit \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: t_test001" \
  -H "X-Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -d '{"test": true}'
```

---

### 3.2 Custom Domain Setup
**Description**: Configure api.formbridge.billybuilds.ai domain
**Documentation**: AWS API Gateway custom domains
**Agent**: api-gateway-specialist
**Dependencies**: 3.1 completed, Route53 hosted zone exists

#### Build:
- [ ] Create `infrastructure/custom-domain.yaml`:
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Custom domain for Form-Bridge API

Parameters:
  DomainName:
    Type: String
    Default: api.formbridge.billybuilds.ai
  HostedZoneId:
    Type: String
    Description: Route53 Hosted Zone ID

Resources:
  Certificate:
    Type: AWS::CertificateManager::Certificate
    Properties:
      DomainName: !Ref DomainName
      DomainValidationOptions:
        - DomainName: !Ref DomainName
          HostedZoneId: !Ref HostedZoneId
      ValidationMethod: DNS
      
  ApiDomainName:
    Type: AWS::ApiGateway::DomainName
    Properties:
      DomainName: !Ref DomainName
      RegionalCertificateArn: !Ref Certificate
      EndpointConfiguration:
        Types: [REGIONAL]
        
  ApiMapping:
    Type: AWS::ApiGateway::BasePathMapping
    Properties:
      DomainName: !Ref ApiDomainName
      RestApiId: !ImportValue formbridge-dev-ApiId
      Stage: dev
      
  RecordSet:
    Type: AWS::Route53::RecordSet
    Properties:
      HostedZoneId: !Ref HostedZoneId
      Name: !Ref DomainName
      Type: A
      AliasTarget:
        DNSName: !GetAtt ApiDomainName.RegionalDomainName
        HostedZoneId: !GetAtt ApiDomainName.RegionalHostedZoneId
```

#### Deploy:
```bash
aws cloudformation create-stack \
  --stack-name formbridge-api-domain \
  --template-body file://infrastructure/custom-domain.yaml \
  --parameters ParameterKey=HostedZoneId,ParameterValue=YOUR_ZONE_ID
```

#### Validate:
```bash
# Test custom domain
curl https://api.formbridge.billybuilds.ai/health

# Verify DNS resolution
nslookup api.formbridge.billybuilds.ai
```

---

## Phase 4: Step Functions Orchestration

### 4.1 Delivery State Machine
**Description**: Orchestrates fan-out delivery to multiple destinations
**Documentation**: /docs/mvp/architecture.md (lines 191-239)
**Agent**: step-functions-orchestrator
**Dependencies**: Phase 3 completed

#### Build:
- [ ] Create `statemachines/delivery-workflow.asl.json`:
```json
{
  "Comment": "Delivery orchestration for form submissions",
  "StartAt": "LoadDestinations",
  "States": {
    "LoadDestinations": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:getItem",
      "Parameters": {
        "TableName": "form-bridge-data",
        "Key": {
          "PK": {"S.$": "$.tenant_id"},
          "SK": {"S": "DESTINATIONS"}
        }
      },
      "ResultPath": "$.destinations",
      "Next": "MapDestinations"
    },
    "MapDestinations": {
      "Type": "Map",
      "ItemsPath": "$.destinations.Items",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "InvokeConnector",
        "States": {
          "InvokeConnector": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
              "FunctionName": "${SmartConnectorFunctionArn}",
              "Payload.$": "$"
            },
            "Retry": [
              {
                "ErrorEquals": ["States.ALL"],
                "IntervalSeconds": 2,
                "MaxAttempts": 3,
                "BackoffRate": 2.0
              }
            ],
            "End": true
          }
        }
      },
      "End": true
    }
  }
}
```

#### Deploy:
```bash
# State machine deployed via SAM
sam deploy --stack-name formbridge-dev
```

#### Validate:
```bash
# Get state machine ARN
aws stepfunctions list-state-machines \
  --query "stateMachines[?contains(name, 'formbridge-delivery')]"

# Start test execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:XXX:stateMachine:formbridge-delivery-dev \
  --input '{"tenant_id":"TENANT#t_test001","submission_id":"test123"}'
```

---

## Phase 5: Monitoring & Observability

### 5.1 CloudWatch Dashboards
**Description**: Operational dashboard for monitoring system health
**Documentation**: /docs/mvp/implementation/monitoring-plan.md
**Agent**: monitoring-observability-expert
**Dependencies**: Phase 4 completed

#### Build:
- [ ] Create `infrastructure/monitoring-dashboard.yaml`:
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: CloudWatch Dashboard for Form-Bridge

Resources:
  Dashboard:
    Type: AWS::CloudWatch::Dashboard
    Properties:
      DashboardName: FormBridge-Overview
      DashboardBody: !Sub |
        {
          "widgets": [
            {
              "type": "metric",
              "properties": {
                "metrics": [
                  ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
                  [".", "Errors", {"stat": "Sum"}],
                  [".", "Duration", {"stat": "Average"}]
                ],
                "period": 300,
                "stat": "Average",
                "region": "${AWS::Region}",
                "title": "Lambda Performance"
              }
            }
          ]
        }
```

#### Deploy:
```bash
aws cloudformation create-stack \
  --stack-name formbridge-monitoring \
  --template-body file://infrastructure/monitoring-dashboard.yaml
```

#### Validate:
```bash
# Open dashboard in console
aws cloudwatch get-dashboard --dashboard-name FormBridge-Overview
```

---

### 5.2 CloudWatch Alarms
**Description**: Alerts for critical metrics
**Documentation**: CloudWatch Alarms best practices
**Agent**: monitoring-observability-expert  
**Dependencies**: 5.1 completed

#### Build:
- [ ] Add alarms to monitoring stack for:
  - Lambda errors > 1% 
  - API Gateway 5xx errors
  - DLQ messages > 0
  - DynamoDB throttles

#### Deploy:
```bash
aws cloudformation update-stack \
  --stack-name formbridge-monitoring \
  --template-body file://infrastructure/monitoring-dashboard.yaml
```

#### Validate:
```bash
# List alarms
aws cloudwatch describe-alarms --alarm-name-prefix FormBridge
```

---

### 5.3 X-Ray Tracing
**Description**: Distributed tracing for request flow
**Documentation**: AWS X-Ray developer guide
**Agent**: monitoring-observability-expert
**Dependencies**: 5.2 completed

#### Build:
- [ ] Verify X-Ray is enabled in SAM template (already configured)

#### Deploy:
```bash
# X-Ray enabled via SAM template
sam deploy --stack-name formbridge-dev
```

#### Validate:
```bash
# Generate test traffic and view traces
aws xray get-trace-summaries \
  --time-range-type LastHour \
  --query 'TraceSummaries[0]'
```

---

## Phase 6: Frontend Dashboard

### 6.1 React Dashboard Setup
**Description**: Admin UI for monitoring submissions
**Documentation**: /docs/frontend/mvp-v1-frontend-specification.md
**Agent**: frontend-react-expert
**Dependencies**: Phase 5 completed

#### Build:
- [ ] Create React app structure:
```bash
npx create-react-app formbridge-dashboard --template typescript
cd formbridge-dashboard
npm install @aws-amplify/ui-react aws-amplify axios recharts
```

#### Deploy:
```bash
# Build and upload to S3
npm run build
aws s3 sync build/ s3://formbridge-ui-dev/ --delete
```

#### Validate:
```bash
# Test local development
npm start

# Verify S3 upload
aws s3 ls s3://formbridge-ui-dev/
```

---

### 6.2 CloudFront Distribution
**Description**: CDN for React dashboard
**Documentation**: CloudFront for SPAs
**Agent**: frontend-react-expert
**Dependencies**: 6.1 completed

#### Build:
- [ ] Create `infrastructure/frontend-cdn.yaml` with CloudFront distribution

#### Deploy:
```bash
aws cloudformation create-stack \
  --stack-name formbridge-frontend \
  --template-body file://infrastructure/frontend-cdn.yaml
```

#### Validate:
```bash
# Get CloudFront URL
aws cloudformation describe-stacks \
  --stack-name formbridge-frontend \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionUrl`].OutputValue'
```

---

### 6.3 Custom Domain for UI
**Description**: Configure formbridge.billybuilds.ai
**Documentation**: CloudFront custom domains
**Agent**: frontend-react-expert
**Dependencies**: 6.2 completed

#### Build:
- [ ] Add Route53 record for formbridge.billybuilds.ai → CloudFront

#### Deploy:
```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id YOUR_ZONE_ID \
  --change-batch file://route53-change.json
```

#### Validate:
```bash
# Test custom domain
curl https://formbridge.billybuilds.ai

# Verify SSL certificate
openssl s_client -connect formbridge.billybuilds.ai:443 -servername formbridge.billybuilds.ai
```

---

## Phase 7: Authentication & Authorization

### 7.1 Cognito User Pool
**Description**: Authentication for admin dashboard
**Documentation**: /docs/security/cognito-jwt-integration-plan.md
**Agent**: cognito-auth-expert
**Dependencies**: Phase 6 completed

#### Build:
- [ ] Create Cognito User Pool configuration in SAM template

#### Deploy:
```bash
sam deploy --stack-name formbridge-auth-dev
```

#### Validate:
```bash
# Create test user
aws cognito-idp admin-create-user \
  --user-pool-id YOUR_POOL_ID \
  --username admin@example.com \
  --temporary-password TempPass123!
```

---

## Phase 8: Integration Testing

### 8.1 End-to-End Test Suite
**Description**: Validate complete flow from submission to delivery
**Documentation**: /docs/testing/form-bridge-tdd-plan.md
**Agent**: test-qa-engineer
**Dependencies**: All phases completed

#### Build:
- [ ] Create E2E test script `tests/e2e/full-flow-test.py`

#### Deploy:
```bash
python tests/e2e/full-flow-test.py --environment dev
```

#### Validate:
```bash
# Check test results
cat test-results/e2e-report.json

# Verify data in DynamoDB
aws dynamodb query \
  --table-name form-bridge-data \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"TENANT#t_test001"}}'
```

---

### 8.2 Load Testing
**Description**: Verify system can handle expected load
**Documentation**: /tests/load/form-submission-load-test.js
**Agent**: test-qa-engineer
**Dependencies**: 8.1 completed

#### Build:
- [ ] Configure k6 load test parameters

#### Deploy:
```bash
k6 run tests/load/form-submission-load-test.js \
  --vus 10 --duration 30s
```

#### Validate:
```bash
# Check CloudWatch metrics during load
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=formbridge-ingest-dev \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average
```

---

## Phase 9: Production Readiness

### 9.1 Security Audit
**Description**: Final security validation
**Documentation**: /docs/security/comprehensive-security-audit-jan-2025.md
**Agent**: security-engineer
**Dependencies**: Phase 8 completed

#### Build:
- [ ] Run security scanning tools
- [ ] Review IAM policies
- [ ] Validate encryption settings

#### Deploy:
```bash
# Run security audit script
python scripts/security-audit.py --full
```

#### Validate:
```bash
# Check security hub findings
aws securityhub get-findings \
  --filters '{"ResourceTags": [{"Key": "Application", "Value": "FormBridge"}]}'
```

---

### 9.2 Cost Monitoring
**Description**: Set up cost tracking and alerts
**Documentation**: /docs/mvp/implementation/cost-optimization-analysis.md
**Agent**: aws-infrastructure-engineer
**Dependencies**: 9.1 completed

#### Build:
- [ ] Create cost allocation tags
- [ ] Set up billing alarms

#### Deploy:
```bash
aws ce create-cost-category-definition \
  --name FormBridge \
  --rules file://cost-category.json
```

#### Validate:
```bash
# Get current costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://cost-filter.json
```

---

### 9.3 Documentation Update
**Description**: Ensure all documentation is current
**Documentation**: /docs/README.md
**Agent**: principal-engineer
**Dependencies**: 9.2 completed

#### Build:
- [ ] Update API documentation
- [ ] Create runbooks
- [ ] Document deployment process

#### Deploy:
```bash
# Generate API documentation
sam local generate-event apigateway aws-proxy > docs/api/sample-event.json
```

#### Validate:
```bash
# Verify documentation completeness
ls -la docs/*/
```

---

## Phase 10: Go Live

### 10.1 Production Deployment
**Description**: Deploy to production environment
**Documentation**: GitHub Actions deployment workflow
**Agent**: cicd-cloudformation-engineer
**Dependencies**: All phases completed

#### Build:
- [ ] Tag release version
- [ ] Create production parameters

#### Deploy:
```bash
# Create production release
git tag -a v1.0.0 -m "Initial production release"
git push origin v1.0.0

# Trigger production deployment
gh workflow run deploy.yml --ref v1.0.0 -f environment=prod
```

#### Validate:
```bash
# Smoke test production
curl https://api.formbridge.billybuilds.ai/health

# Verify production metrics
aws cloudwatch get-metric-statistics \
  --namespace FormBridge \
  --metric-name SuccessfulSubmissions \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

---

## Rollback Procedures

If any deployment fails:

1. **Automatic Rollback** (CloudFormation):
```bash
# CloudFormation automatically rolls back on failure
# Monitor rollback
aws cloudformation describe-stack-events \
  --stack-name formbridge-dev \
  --query 'StackEvents[?ResourceStatus==`ROLLBACK_IN_PROGRESS`]'
```

2. **Manual Rollback**:
```bash
# Delete failed stack
aws cloudformation delete-stack --stack-name formbridge-dev

# Redeploy previous version
git checkout <previous-tag>
sam deploy --stack-name formbridge-dev
```

3. **Data Recovery**:
```bash
# DynamoDB point-in-time recovery
aws dynamodb restore-table-to-point-in-time \
  --source-table-name form-bridge-data \
  --target-table-name form-bridge-data-restored \
  --restore-date-time $(date -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)
```

---

## Success Criteria

Each phase is considered complete when:

1. **Build**: All code/configuration files created and reviewed
2. **Deploy**: Resources successfully created in AWS
3. **Validate**: All validation commands return expected results
4. **No Manual Steps**: Everything automated via GitHub Actions
5. **Documentation**: README updated with any changes

---

## Cost Monitoring Checkpoints

Monitor costs after each phase:

- Phase 1-2: Should be < $1/day (Lambda, DynamoDB on-demand)
- Phase 3-4: Should be < $2/day (+ API Gateway)
- Phase 5-6: Should be < $3/day (+ CloudFront)
- Phase 7-8: Should be < $5/day (+ Cognito)
- Production: Target < $100/month for 1M submissions

---

## Next Steps After MVP

1. **Multi-region deployment** for high availability
2. **OAuth2 connectors** for CRM integrations  
3. **Advanced analytics** with QuickSight
4. **Webhook management UI** for self-service
5. **Rate limiting** per tenant
6. **Data retention policies** with lifecycle rules

---

*This plan provides a complete path from zero infrastructure to a fully operational Form-Bridge system. Each step has been designed to be executable by specialized agents with clear success criteria.*
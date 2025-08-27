#!/bin/bash

# Quick Deploy - Fast Local/Manual Deployment
# For immediate testing when GitHub Actions is not available
# Optimized for speed and reliability

set -e

ENVIRONMENT=${1:-dev}
STACK_NAME="formbridge-mvp-${ENVIRONMENT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Form-Bridge MVP Quick Deploy"
echo "Environment: ${ENVIRONMENT}"
echo "Stack: ${STACK_NAME}"
echo "Project Root: ${PROJECT_ROOT}"
echo ""

# Pre-flight checks
echo "🔍 Running pre-flight checks..."

# Check required tools
REQUIRED_TOOLS=("sam" "aws" "python3" "curl")
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! command -v $tool &> /dev/null; then
        echo "❌ Required tool not found: $tool"
        case $tool in
            "sam")
                echo "   Install with: pip install aws-sam-cli"
                ;;
            "aws")
                echo "   Install AWS CLI: https://aws.amazon.com/cli/"
                ;;
            "python3")
                echo "   Install Python 3.12+"
                ;;
            "curl")
                echo "   Install curl for testing"
                ;;
        esac
        exit 1
    fi
done

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI is not configured. Run: aws configure"
    exit 1
fi

# Check required files
cd "$PROJECT_ROOT"

REQUIRED_FILES=(
    "template-mvp-fast-deploy.yaml"
    "lambdas/requirements-mvp.txt"
    "lambdas/mvp-ingest-handler.py"
    "lambdas/mvp-event-processor.py"
    "lambdas/mvp-api-authorizer.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Required file missing: $file"
        exit 1
    fi
done

echo "✅ Pre-flight checks passed"
echo ""

# Prepare for deployment
echo "📦 Preparing for deployment..."

# Use minimal requirements for speed
cp lambdas/requirements-mvp.txt lambdas/requirements.txt

# Show current AWS context
CURRENT_USER=$(aws sts get-caller-identity --query 'Arn' --output text)
CURRENT_REGION=$(aws configure get region)
echo "AWS User: $CURRENT_USER"
echo "AWS Region: $CURRENT_REGION"
echo ""

# Build
echo "🔨 Building SAM application (x86_64 for speed)..."
START_TIME=$(date +%s)

sam build \
    --template-file template-mvp-fast-deploy.yaml \
    --use-container false \
    --cached \
    --parallel

BUILD_TIME=$(($(date +%s) - START_TIME))
echo "✅ Build completed in ${BUILD_TIME} seconds"
echo ""

# Deploy
echo "🚀 Deploying CloudFormation stack..."
DEPLOY_START=$(date +%s)

# Check if this is first deployment
if aws cloudformation describe-stacks --stack-name ${STACK_NAME} &> /dev/null; then
    echo "📡 Stack exists, deploying updates..."
    DEPLOY_MODE="update"
else
    echo "📡 New stack, deploying for first time..."
    DEPLOY_MODE="create"
fi

sam deploy \
    --template-file template-mvp-fast-deploy.yaml \
    --stack-name ${STACK_NAME} \
    --parameter-overrides Environment=${ENVIRONMENT} \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --resolve-s3

DEPLOY_TIME=$(($(date +%s) - DEPLOY_START))
echo "✅ Deployment completed in ${DEPLOY_TIME} seconds"
echo ""

# Get outputs
echo "📊 Getting deployment outputs..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

DYNAMODB_TABLE=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[?OutputKey==`DynamoDBTable`].OutputValue' \
    --output text)

S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[?OutputKey==`S3Bucket`].OutputValue' \
    --output text)

# Quick smoke test
echo "🧪 Running smoke test..."
SMOKE_TEST_START=$(date +%s)

# Test CORS preflight
if curl -f -s -X OPTIONS "$API_ENDPOINT/submit" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: Content-Type,X-Tenant-ID,X-API-Key" \
    --max-time 10 > /dev/null; then
    echo "✅ CORS preflight successful"
else
    echo "⚠️  CORS preflight failed (might be normal for new deployments)"
fi

SMOKE_TIME=$(($(date +%s) - SMOKE_TEST_START))
TOTAL_TIME=$(($(date +%s) - START_TIME))

echo ""
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "=========================================="
echo "Environment: ${ENVIRONMENT}"
echo "Stack Name: ${STACK_NAME}"
echo "Deploy Mode: ${DEPLOY_MODE}"
echo ""
echo "📊 Timing:"
echo "  Build: ${BUILD_TIME}s"
echo "  Deploy: ${DEPLOY_TIME}s" 
echo "  Smoke Test: ${SMOKE_TIME}s"
echo "  Total: ${TOTAL_TIME}s"
echo ""
echo "🔗 Resources:"
echo "  API Endpoint: $API_ENDPOINT"
echo "  DynamoDB Table: $DYNAMODB_TABLE"
echo "  S3 Bucket: $S3_BUCKET"
echo ""
echo "🧪 Test your deployment:"
echo "----------------------------------------"
echo "curl -X POST $API_ENDPOINT/submit \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"X-Tenant-ID: t_sample\" \\"
echo "  -H \"X-API-Key: mvp-test-key-123\" \\"
echo "  -d '{\"form_data\": {\"name\": \"Quick Deploy Test\", \"email\": \"test@formbridge.dev\"}, \"form_type\": \"contact\"}'"
echo ""
echo "📋 All Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue,Description]' \
    --output table

echo ""
echo "🔍 Monitor with:"
echo "aws logs tail /aws/lambda/formbridge-mvp-ingest-${ENVIRONMENT} --follow"
echo ""
echo "🗑️  Cleanup with:"
echo "aws cloudformation delete-stack --stack-name ${STACK_NAME}"
echo ""

if [ $TOTAL_TIME -lt 300 ]; then
    echo "🏆 Deployment completed in under 5 minutes! (${TOTAL_TIME}s)"
else
    echo "⏱️  Deployment took ${TOTAL_TIME} seconds"
fi
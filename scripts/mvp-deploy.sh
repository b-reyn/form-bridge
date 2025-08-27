#!/bin/bash

# MVP Fast Deployment Script
# Deploys simplified Form-Bridge for quick testing

set -e

ENVIRONMENT=${1:-dev}
STACK_NAME="formbridge-mvp-${ENVIRONMENT}"

echo "🚀 Starting MVP deployment for environment: ${ENVIRONMENT}"

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI is not installed. Please install it first:"
    echo "   pip install aws-sam-cli"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI is not configured. Please run 'aws configure' first."
    exit 1
fi

# Copy minimal requirements
echo "📦 Using minimal requirements for fast build..."
cp lambdas/requirements-mvp.txt lambdas/requirements.txt

# Build with SAM (x86_64 for speed)
echo "🔨 Building SAM application (x86_64 for speed)..."
sam build \
    --template-file template-mvp-fast-deploy.yaml \
    --use-container false \
    --cached \
    --parallel

# Deploy with guided setup on first run
if aws cloudformation describe-stacks --stack-name ${STACK_NAME} &> /dev/null; then
    echo "📡 Stack exists, deploying updates..."
    sam deploy \
        --template-file template-mvp-fast-deploy.yaml \
        --stack-name ${STACK_NAME} \
        --parameter-overrides Environment=${ENVIRONMENT} \
        --capabilities CAPABILITY_IAM \
        --no-confirm-changeset
else
    echo "📡 New stack, starting guided deployment..."
    sam deploy \
        --template-file template-mvp-fast-deploy.yaml \
        --stack-name ${STACK_NAME} \
        --parameter-overrides Environment=${ENVIRONMENT} \
        --capabilities CAPABILITY_IAM \
        --guided
fi

# Get outputs
echo "📊 Deployment complete! Getting stack outputs..."
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)
DYNAMODB_TABLE=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query 'Stacks[0].Outputs[?OutputKey==`DynamoDBTable`].OutputValue' --output text)

echo ""
echo "✅ MVP Deployment Successful!"
echo "🌐 API Endpoint: ${API_ENDPOINT}"
echo "💾 DynamoDB Table: ${DYNAMODB_TABLE}"
echo ""
echo "🧪 Test your deployment:"
echo "curl -X POST ${API_ENDPOINT}/submit \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"X-Tenant-ID: t_sample\" \\"
echo "  -H \"X-API-Key: mvp-test-key-123\" \\"
echo "  -d '{\"form_data\": {\"name\": \"Test User\", \"email\": \"test@example.com\"}, \"form_type\": \"contact\"}'"
echo ""
echo "🔍 Monitor with:"
echo "aws logs tail /aws/lambda/formbridge-mvp-ingest-${ENVIRONMENT} --follow"
echo ""
echo "🗑️ Cleanup with:"
echo "aws cloudformation delete-stack --stack-name ${STACK_NAME}"
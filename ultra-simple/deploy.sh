#!/bin/bash

# Form-Bridge Ultra-Simple Deployment Script
# Deploys the minimal-cost architecture: Lambda + DynamoDB only

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-test}
REGION=${AWS_REGION:-us-east-1}
STACK_NAME="form-bridge-ultra-simple-${ENVIRONMENT}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Form-Bridge Ultra-Simple Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Environment:${NC} ${ENVIRONMENT}"
echo -e "${YELLOW}Region:${NC} ${REGION}"
echo -e "${YELLOW}Stack:${NC} ${STACK_NAME}"
echo ""

# Check AWS CLI is configured
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${RED}Error: AWS CLI not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

# Check SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo -e "${RED}Error: SAM CLI not installed${NC}"
    echo "Install: pip install aws-sam-cli"
    exit 1
fi

# Choose template based on requirements
TEMPLATE_FILE="template-minimal.yaml"
echo -e "${YELLOW}Using minimal template (Lambda + DynamoDB only)${NC}"

# Build the application
echo -e "${YELLOW}Building application...${NC}"
sam build \
    --template-file ${TEMPLATE_FILE} \
    --cached

# Deploy the application
echo -e "${YELLOW}Deploying to AWS...${NC}"
sam deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        Environment=${ENVIRONMENT} \
    --no-fail-on-empty-changeset \
    --no-confirm-changeset

# Get outputs
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get the Lambda Function URL
FUNCTION_URL=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionUrl'].OutputValue" \
    --output text)

# Get DynamoDB Table
TABLE_NAME=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query "Stacks[0].Outputs[?OutputKey=='DynamoDBTable'].OutputValue" \
    --output text)

echo -e "${GREEN}WordPress Plugin Endpoint:${NC}"
echo "  ${FUNCTION_URL}"
echo ""
echo -e "${GREEN}DynamoDB Table:${NC}"
echo "  ${TABLE_NAME}"
echo ""

# Test the endpoint (using development secret)
echo -e "${YELLOW}Testing the endpoint...${NC}"

# Use development secret (change in production)
SECRET="development-secret-change-in-production"

# Generate test signature
TIMESTAMP=$(date +%s)
TEST_DATA='{"form_data":{"name":"Test User","email":"test@example.com","message":"Ultra-simple test"},"metadata":{"source":"deploy-script","form_id":"test-form"}}'
MESSAGE="${TIMESTAMP}:${TEST_DATA}"
SIGNATURE=$(echo -n "${MESSAGE}" | openssl dgst -sha256 -hmac "${SECRET}" | cut -d' ' -f2)

# Make test request
echo -e "${YELLOW}Sending test submission...${NC}"
RESPONSE=$(curl -s -w "\nHTTP Status: %{http_code}" -X POST "${FUNCTION_URL}" \
    -H "Content-Type: application/json" \
    -H "X-Signature: ${SIGNATURE}" \
    -H "X-Timestamp: ${TIMESTAMP}" \
    -d "${TEST_DATA}")

echo "Response: ${RESPONSE}"
echo ""

# Cost estimate
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Ultra-Simple Cost Estimate${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Testing (0-1K requests):      $0.00 (Free Tier)"
echo "Light Usage (1K-10K):         $0.00 - $0.50"
echo "Growing Usage (10K-100K):     $1.00 - $5.00"
echo ""
echo -e "${YELLOW}AWS Free Tier (12 months):${NC}"
echo "• Lambda: 1M requests + 400K GB-seconds/month"
echo "• DynamoDB: 25GB storage + 25 WCU + 25 RCU"
echo "• CloudWatch: 10 metrics + 5GB logs"
echo ""
echo -e "${YELLOW}This deployment includes:${NC}"
echo "• Single Lambda function (128MB, ultra-optimized)"
echo "• DynamoDB table with TTL auto-cleanup"
echo "• CloudWatch logging (7-day retention)"
echo "• No API Gateway, S3, or CloudFront costs"
echo ""

# Next steps
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}WordPress Plugin Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "1. Update your WordPress plugin config:"
echo ""
echo "define('FORM_BRIDGE_ENDPOINT', '${FUNCTION_URL}');"
echo "define('FORM_BRIDGE_SECRET', 'development-secret-change-in-production');"
echo ""
echo "2. Test from WordPress:"
echo "   - Submit a form"
echo "   - Check logs: aws logs tail /aws/lambda/form-bridge-ultra-${ENVIRONMENT} --follow"
echo "   - View data: aws dynamodb scan --table-name ${TABLE_NAME} --limit 5"
echo ""
echo "3. For production:"
echo "   - Change HMAC secret in template-minimal.yaml"
echo "   - Enable Secrets Manager (uncomment in template)"
echo "   - Set up monitoring alerts"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Monitoring Commands${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Real-time logs:"
echo "  aws logs tail /aws/lambda/form-bridge-ultra-${ENVIRONMENT} --follow"
echo ""
echo "Recent submissions:"
echo "  aws dynamodb query \\"
echo "    --table-name ${TABLE_NAME} \\"
echo "    --key-condition-expression 'PK = :pk' \\"
echo "    --expression-attribute-values '{\":pk\":{\"S\":\"SUBMISSION\"}}' \\"
echo "    --scan-index-forward false --limit 5"
echo ""
echo "Delete stack:"
echo "  aws cloudformation delete-stack --stack-name ${STACK_NAME}"
echo ""

echo -e "${GREEN}Ultra-simple deployment complete! 🚀${NC}"
#!/bin/bash
set -e

# Form-Bridge WordPress Plugin Authentication Deployment Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-east-1}
STACK_NAME="form-bridge-plugin-auth-${ENVIRONMENT}"

echo "🚀 Deploying Form-Bridge Plugin Authentication System"
echo "   Environment: $ENVIRONMENT"
echo "   Region: $AWS_REGION"
echo "   Stack: $STACK_NAME"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
print_status "Checking prerequisites..."

# Check if AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    print_error "SAM CLI is not installed. Please install it first."
    echo "  Install with: pip install aws-sam-cli"
    exit 1
fi

# Check if Python 3.12 is available
if ! command -v python3.12 &> /dev/null; then
    print_warning "Python 3.12 not found. Using default python3."
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python3.12"
fi

# Verify AWS credentials
print_status "Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

print_success "Prerequisites verified"

# Build Lambda layer
print_status "Building Lambda dependencies layer..."
rm -rf layers/dependencies/python
mkdir -p layers/dependencies/python

# Install dependencies in the layer directory
pip install -r requirements.txt -t layers/dependencies/python/ --no-deps --platform manylinux2014_aarch64 --only-binary=:all:

# Copy shared utilities to each function directory (SAM expects it)
cp shared_utils.py layers/dependencies/python/

print_success "Dependencies layer built"

# Validate SAM template
print_status "Validating SAM template..."
sam validate --template-file template.yaml

if [ $? -ne 0 ]; then
    print_error "SAM template validation failed"
    exit 1
fi

print_success "Template validation passed"

# Build the application
print_status "Building SAM application..."
sam build --use-container --container-image amazon/aws-sam-cli-emulation-image-python3.12

if [ $? -ne 0 ]; then
    print_error "SAM build failed"
    exit 1
fi

print_success "Build completed"

# Deploy the application
print_status "Deploying to AWS..."

# Determine if this is first deployment
STACK_EXISTS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" 2>/dev/null || echo "false")

if [[ $STACK_EXISTS == "false" ]]; then
    print_status "First deployment - running guided deployment"
    sam deploy \
        --guided \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --parameter-overrides Environment="$ENVIRONMENT" \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
        --tags Environment="$ENVIRONMENT" Project=form-bridge Component=plugin-auth
else
    print_status "Updating existing stack"
    sam deploy \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --parameter-overrides Environment="$ENVIRONMENT" \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
        --tags Environment="$ENVIRONMENT" Project=form-bridge Component=plugin-auth \
        --no-confirm-changeset
fi

if [ $? -ne 0 ]; then
    print_error "Deployment failed"
    exit 1
fi

print_success "Deployment completed"

# Get outputs
print_status "Retrieving deployment outputs..."
API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
    --output text)

TABLE_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`TableName`].OutputValue' \
    --output text)

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`PluginBucketName`].OutputValue' \
    --output text)

# Display deployment information
echo ""
print_success "🎉 Deployment Summary"
echo "========================"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "Stack Name: $STACK_NAME"
echo ""
echo "📡 API Gateway URL: $API_URL"
echo "🗄️  DynamoDB Table: $TABLE_NAME"
echo "🪣 S3 Bucket: $BUCKET_NAME"
echo ""

# Test basic connectivity
print_status "Testing API connectivity..."
HEALTH_CHECK_URL="${API_URL}/health"

# Simple health check (this endpoint would need to be added to template)
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/register" -X OPTIONS || echo "000")

if [[ $HTTP_STATUS == "200" ]]; then
    print_success "API is responding correctly"
else
    print_warning "API health check returned status: $HTTP_STATUS"
    print_warning "This might be expected if CORS preflight is not configured"
fi

# Create configuration file for easy access
CONFIG_FILE=".env.${ENVIRONMENT}"
cat > "$CONFIG_FILE" << EOF
# Form-Bridge Plugin Authentication Configuration
# Environment: $ENVIRONMENT
# Generated: $(date)

ENVIRONMENT=$ENVIRONMENT
AWS_REGION=$AWS_REGION
API_URL=$API_URL
TABLE_NAME=$TABLE_NAME
BUCKET_NAME=$BUCKET_NAME
STACK_NAME=$STACK_NAME

# API Endpoints
REGISTER_ENDPOINT=${API_URL}/register
EXCHANGE_ENDPOINT=${API_URL}/exchange
VALIDATE_ENDPOINT=${API_URL}/validate
UPDATE_CHECK_ENDPOINT=${API_URL}/updates/check
EOF

print_success "Configuration saved to $CONFIG_FILE"

# Deployment tips
echo ""
print_status "📝 Next Steps:"
echo "1. Test the API endpoints using the URLs above"
echo "2. Upload plugin release files to S3 bucket: $BUCKET_NAME"
echo "3. Configure DNS/custom domain for API Gateway (if needed)"
echo "4. Set up CloudWatch alarms and monitoring"
echo "5. Test WordPress plugin integration"
echo ""
print_status "💡 Useful Commands:"
echo "  - View logs: sam logs --stack-name $STACK_NAME --tail"
echo "  - Local testing: sam local start-api"
echo "  - Delete stack: aws cloudformation delete-stack --stack-name $STACK_NAME"
echo ""

print_success "🚀 Deployment completed successfully!"
#!/bin/bash

# Deployment Validation Script
# Validates that the MVP deployment is working correctly
# Usage: ./validate-deployment.sh [environment]

set -e

ENVIRONMENT=${1:-dev}
STACK_NAME="formbridge-mvp-${ENVIRONMENT}"

echo "🧪 Form-Bridge MVP Deployment Validation"
echo "Environment: ${ENVIRONMENT}"
echo "Stack: ${STACK_NAME}"
echo ""

# Check if stack exists
if ! aws cloudformation describe-stacks --stack-name ${STACK_NAME} &> /dev/null; then
    echo "❌ Stack ${STACK_NAME} does not exist"
    echo "Deploy first with: ./quick-deploy.sh ${ENVIRONMENT}"
    exit 1
fi

echo "✅ Stack ${STACK_NAME} exists"

# Get stack outputs
echo "📊 Getting stack information..."
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

echo "API Endpoint: $API_ENDPOINT"
echo "DynamoDB Table: $DYNAMODB_TABLE"
echo "S3 Bucket: $S3_BUCKET"
echo ""

# Validation tests
PASSED=0
FAILED=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "🧪 $test_name... "
    
    if eval "$test_command" &> /dev/null; then
        echo "✅ PASS"
        ((PASSED++))
    else
        echo "❌ FAIL"
        ((FAILED++))
    fi
}

echo "🔍 Running validation tests..."
echo ""

# Test 1: DynamoDB Table exists and is accessible
run_test "DynamoDB table accessibility" \
    "aws dynamodb describe-table --table-name $DYNAMODB_TABLE"

# Test 2: S3 Bucket exists and is accessible  
run_test "S3 bucket accessibility" \
    "aws s3api head-bucket --bucket $S3_BUCKET"

# Test 3: Lambda functions exist and are active
LAMBDA_FUNCTIONS=(
    "formbridge-mvp-ingest-${ENVIRONMENT}"
    "formbridge-mvp-processor-${ENVIRONMENT}"
    "formbridge-mvp-authorizer-${ENVIRONMENT}"
)

for func in "${LAMBDA_FUNCTIONS[@]}"; do
    run_test "Lambda function: $func" \
        "aws lambda get-function --function-name $func"
done

# Test 4: API Gateway is responding
run_test "API Gateway CORS preflight" \
    "curl -f -s -X OPTIONS '$API_ENDPOINT/submit' \
     -H 'Access-Control-Request-Method: POST' \
     -H 'Access-Control-Request-Headers: Content-Type,X-Tenant-ID,X-API-Key' \
     --max-time 10"

# Test 5: Sample tenant secret exists
run_test "Sample tenant secret exists" \
    "aws secretsmanager get-secret-value --secret-id 'formbridge/tenants/t_sample'"

# Test 6: Full API test with sample data
echo -n "🧪 End-to-end API test... "

API_RESPONSE=$(curl -s -X POST "$API_ENDPOINT/submit" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: t_sample" \
    -H "X-API-Key: mvp-test-key-123" \
    -d '{"form_data": {"name": "Validation Test", "email": "test@formbridge.dev"}, "form_type": "contact"}' \
    --max-time 15 \
    --write-out "%{http_code}")

HTTP_CODE="${API_RESPONSE: -3}"
RESPONSE_BODY="${API_RESPONSE%???}"

if [ "$HTTP_CODE" == "200" ] || [ "$HTTP_CODE" == "201" ]; then
    echo "✅ PASS (HTTP $HTTP_CODE)"
    ((PASSED++))
    echo "    Response: $RESPONSE_BODY"
else
    echo "❌ FAIL (HTTP $HTTP_CODE)"
    ((FAILED++))
    echo "    Response: $RESPONSE_BODY"
fi

echo ""
echo "📋 Validation Results"
echo "===================="
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo "Total: $((PASSED + FAILED))"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo "🎉 ALL TESTS PASSED!"
    echo "Your deployment is working correctly."
    echo ""
    echo "🚀 Ready for production use:"
    echo "curl -X POST $API_ENDPOINT/submit \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -H \"X-Tenant-ID: t_sample\" \\"
    echo "  -H \"X-API-Key: mvp-test-key-123\" \\"
    echo "  -d '{\"form_data\": {\"name\": \"Your Name\", \"email\": \"you@example.com\"}, \"form_type\": \"contact\"}'"
    echo ""
    echo "📊 Monitor with:"
    echo "aws logs tail /aws/lambda/formbridge-mvp-ingest-${ENVIRONMENT} --follow"
    
    exit 0
else
    echo ""
    echo "⚠️  SOME TESTS FAILED"
    echo "Please check the failed tests and redeploy if necessary."
    echo ""
    echo "🔧 Troubleshooting:"
    echo "1. Check CloudWatch logs for Lambda errors"
    echo "2. Verify AWS credentials and permissions"
    echo "3. Ensure all resources are in the same region"
    echo "4. Try redeploying with: ./quick-deploy.sh ${ENVIRONMENT}"
    
    exit 1
fi
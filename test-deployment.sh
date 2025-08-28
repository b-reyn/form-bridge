#!/bin/bash

# Test the deployed Form-Bridge ultra-simple architecture

FUNCTION_URL="https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/"
SECRET="development-secret-change-in-production"
TIMESTAMP=$(date +%s)
PAYLOAD='{"form_data":{"test":"deployment-validation","pm":"success","timestamp":"'$TIMESTAMP'"}}'

# Generate HMAC signature
SIGNATURE=$(echo -n "${TIMESTAMP}:${PAYLOAD}" | openssl dgst -sha256 -hmac "${SECRET}" | cut -d' ' -f2)

echo "🧪 Testing Form-Bridge Deployment"
echo "=================================="
echo "Function URL: $FUNCTION_URL"
echo "Timestamp: $TIMESTAMP"
echo "Payload: $PAYLOAD"
echo "Signature: $SIGNATURE"
echo ""

echo "🔄 Sending test request..."
RESPONSE=$(curl -s -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -H "X-Timestamp: $TIMESTAMP" \
  -d "$PAYLOAD" \
  -w "\nHTTP_STATUS:%{http_code}\nTIME_TOTAL:%{time_total}")

echo "📋 Response:"
echo "$RESPONSE"
echo ""

# Check if successful
if echo "$RESPONSE" | grep -q '"success":true'; then
    echo "✅ Test PASSED - Form submission successful!"
    echo "🎉 Ultra-Simple Form-Bridge is working correctly!"
else
    echo "⚠️  Test result unclear - check response above"
fi
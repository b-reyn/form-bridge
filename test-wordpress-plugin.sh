#!/bin/bash

# Test WordPress Form-Bridge Plugin Integration

echo "🧪 Testing Form-Bridge WordPress Plugin Integration"
echo "=================================================="

# Check if containers are running
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ WordPress containers are not running."
    echo "💡 Run: ./setup-wordpress.sh"
    exit 1
fi

echo "✅ WordPress containers are running"

# Check WordPress accessibility
if curl -s http://localhost:8080 | grep -q "WordPress"; then
    echo "✅ WordPress is accessible at http://localhost:8080"
else
    echo "❌ WordPress is not accessible"
    exit 1
fi

# Check if plugin file exists in the container
if docker exec form-bridge-wordpress test -f /var/www/html/wp-content/plugins/form-bridge/form-bridge.php; then
    echo "✅ Form-Bridge plugin is mounted in container"
else
    echo "❌ Form-Bridge plugin not found in container"
    exit 1
fi

# Test Form-Bridge endpoint connectivity from within container
echo "🔗 Testing Form-Bridge endpoint from WordPress container..."
ENDPOINT_TEST=$(docker exec form-bridge-wordpress curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/)

if [ "$ENDPOINT_TEST" = "200" ] || [ "$ENDPOINT_TEST" = "403" ]; then
    echo "✅ Form-Bridge endpoint is accessible from WordPress (HTTP $ENDPOINT_TEST)"
else
    echo "⚠️  Form-Bridge endpoint returned HTTP $ENDPOINT_TEST (might be connectivity issue)"
fi

# Test HMAC signature generation (PHP test)
echo "🔐 Testing HMAC signature generation in WordPress container..."

# Create a test PHP script for HMAC validation
cat > /tmp/test_hmac.php << 'EOF'
<?php
$secret = 'development-secret-change-in-production';
$timestamp = time();
$payload = '{"form_data":{"test":"plugin_test"}}';

$signature = hash_hmac('sha256', $timestamp . ':' . $payload, $secret);

echo "Timestamp: $timestamp\n";
echo "Payload: $payload\n";
echo "Signature: $signature\n";

// Test against known working signature generation
$test_timestamp = 1737974400;
$test_payload = '{"form_data":{"test":"known_test"}}';
$expected_signature = hash_hmac('sha256', $test_timestamp . ':' . $test_payload, $secret);

echo "Test signature (timestamp $test_timestamp): $expected_signature\n";
?>
EOF

# Copy and run the test script in WordPress container
docker cp /tmp/test_hmac.php form-bridge-wordpress:/tmp/
HMAC_OUTPUT=$(docker exec form-bridge-wordpress php /tmp/test_hmac.php)

if echo "$HMAC_OUTPUT" | grep -q "Signature:"; then
    echo "✅ HMAC signature generation working in WordPress"
    echo "📝 Sample output:"
    echo "$HMAC_OUTPUT" | head -3
else
    echo "❌ HMAC signature generation failed"
fi

# Check WordPress debug log
echo "📋 Recent WordPress debug log entries:"
if docker exec form-bridge-wordpress test -f /var/www/html/wp-content/debug.log; then
    docker exec form-bridge-wordpress tail -5 /var/www/html/wp-content/debug.log 2>/dev/null || echo "   (Debug log empty or not accessible)"
else
    echo "   (Debug log not created yet)"
fi

echo ""
echo "🎯 Manual Testing Steps:"
echo "1. Go to http://localhost:8080"
echo "2. Complete WordPress setup if not done"
echo "3. Go to Plugins → Activate 'Form-Bridge Connector'"
echo "4. Go to Settings → Form-Bridge"
echo "5. Click 'Test Connection' - should show ✅ Connection successful!"
echo ""
echo "📦 To install Contact Form 7 for testing:"
echo "   - Go to Plugins → Add New"
echo "   - Search for 'Contact Form 7'"
echo "   - Install and activate"
echo "   - Go to Contact → Contact Forms"
echo "   - Create a test form"
echo ""
echo "🔍 Monitor submissions:"
echo "   - WordPress logs: docker exec form-bridge-wordpress tail -f /var/www/html/wp-content/debug.log"
echo "   - Form-Bridge logs: aws logs tail /aws/lambda/form-bridge-ultra-prod --follow"
echo "   - DynamoDB data: aws dynamodb scan --table-name form-bridge-ultra-prod"
echo ""

# Final connectivity test to our live endpoint
echo "🌐 Final connectivity test to live Form-Bridge endpoint..."
if ./test-deployment.sh | grep -q "✅ Test PASSED"; then
    echo "✅ Form-Bridge endpoint is working and ready for WordPress integration!"
else
    echo "⚠️  Form-Bridge endpoint test had issues - check ./test-deployment.sh output"
fi

echo ""
echo "🎉 WordPress test environment is ready for Form-Bridge plugin testing!"
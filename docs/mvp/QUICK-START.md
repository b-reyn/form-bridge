# Form-Bridge Ultra-Simple Quick Start

**The System is Already Deployed - Just Start Using It!**

*Last Updated: January 27, 2025*
*Status: ✅ LIVE and Ready*

## It's Already Working!

**Good news**: Form-Bridge is already deployed and working. No setup required!

- **Live Endpoint**: https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/
- **Cost**: $0.00/month (AWS Free Tier)
- **Ready For**: WordPress integration

## Quick Test (30 seconds)

### Verify It's Working
```bash
# Run the test script from the repo root
./test-deployment.sh

# Expected output:
# ✅ Test PASSED - Form submission successful!
# 🎉 Ultra-Simple Form-Bridge is working correctly!
```

### Manual Test with curl
```bash
# Test manually with curl
FUNCTION_URL="https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/"
SECRET="development-secret-change-in-production"
TIMESTAMP=$(date +%s)
PAYLOAD='{"form_data":{"email":"test@example.com","name":"John Doe"}}'

# Generate HMAC signature
SIGNATURE=$(echo -n "${TIMESTAMP}:${PAYLOAD}" | openssl dgst -sha256 -hmac "${SECRET}" | cut -d' ' -f2)

# Send request
curl -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -H "X-Timestamp: $TIMESTAMP" \
  -d "$PAYLOAD"

# Expected response:
# {"success": true, "submission_id": "sub_1737974400_abc123", "message": "Form submitted successfully"}
```

## WordPress Integration (5 minutes)

### Step 1: Add to your WordPress site
Add this to your theme's `functions.php` or create a custom plugin:

```php
<?php
function submit_to_form_bridge($form_data) {
    $endpoint = 'https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/';
    $secret = 'development-secret-change-in-production';
    
    $timestamp = time();
    $payload = json_encode(['form_data' => $form_data]);
    $signature = hash_hmac('sha256', $timestamp . ':' . $payload, $secret);
    
    $response = wp_remote_post($endpoint, [
        'headers' => [
            'Content-Type' => 'application/json',
            'X-Timestamp' => $timestamp,
            'X-Signature' => $signature
        ],
        'body' => $payload,
        'timeout' => 10
    ]);
    
    if (is_wp_error($response)) {
        return ['success' => false, 'error' => $response->get_error_message()];
    }
    
    return json_decode(wp_remote_retrieve_body($response), true);
}

// Example: Hook into Contact Form 7 submissions
add_action('wpcf7_mail_sent', function($contact_form) {
    $submission = WPCF7_Submission::get_instance();
    if ($submission) {
        $form_data = $submission->get_posted_data();
        $result = submit_to_form_bridge($form_data);
        
        // Log the result
        error_log('Form-Bridge submission: ' . json_encode($result));
    }
});

// Example: Hook into WPForms submissions
add_action('wpforms_process_complete', function($fields, $entry, $form_data) {
    $form_submission = [];
    foreach ($fields as $field) {
        $form_submission[$field['name']] = $field['value'];
    }
    
    $result = submit_to_form_bridge($form_submission);
    error_log('Form-Bridge submission: ' . json_encode($result));
}, 10, 3);
?>
```

### Step 2: Test your WordPress form
1. Fill out any form on your WordPress site
2. Check your WordPress error logs: `tail -f /path/to/wordpress/wp-content/debug.log`
3. Look for: `Form-Bridge submission: {"success":true,"submission_id":"sub_..."}`

## View Your Data (2 minutes)

### See all form submissions
```bash
# View all stored submissions
aws dynamodb scan --table-name form-bridge-ultra-prod --region us-east-1

# Query by tenant (when you add multi-tenancy later)
aws dynamodb query \
  --table-name form-bridge-ultra-prod \
  --key-condition-expression "tenant_id = :tid" \
  --expression-attribute-values '{":tid":{"S":"wordpress_site_123"}}' \
  --region us-east-1
```

### Monitor in real-time
```bash
# Watch Lambda logs
aws logs tail /aws/lambda/form-bridge-ultra-prod --follow --region us-east-1

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/form-bridge-ultra-prod \
  --filter-pattern "ERROR" \
  --region us-east-1
```

## What You Get

### Current Features ✅
- **Form Ingestion**: WordPress forms submit successfully
- **HMAC Security**: Prevents request tampering
- **Data Storage**: 30-day automatic cleanup via TTL
- **Auto-scaling**: Handles 1000 concurrent requests
- **Zero Cost**: AWS Free Tier coverage
- **CloudWatch Logs**: Basic debugging and monitoring

### What's NOT Included (Can Add Later)
- ❌ Multi-tenant isolation (single tenant only)
- ❌ Rate limiting (Function URL defaults only)  
- ❌ Advanced monitoring (basic CloudWatch only)
- ❌ Webhook delivery (just storage for now)
- ❌ Admin dashboard (use AWS Console)

## Troubleshooting

### Common Issues

**403 Forbidden - Invalid Signature**
```bash
# Check your timestamp (must be within 5 minutes)
date +%s

# Verify signature generation - test with curl example above
# Make sure your secret matches: 'development-secret-change-in-production'
```

**No response / timeout**
```bash
# Check if Function URL is accessible
curl -I https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/

# Should return: HTTP/2 200 or HTTP/2 403 (not timeout)
```

**WordPress not sending data**
```bash
# Add debugging to your WordPress function
error_log('Form data being sent: ' . json_encode($form_data));
error_log('Form-Bridge response: ' . json_encode($result));

# Check your WordPress error logs
```

### Getting Help

1. **Check the logs**: `aws logs tail /aws/lambda/form-bridge-ultra-prod --follow`
2. **Run the test script**: `./test-deployment.sh` should always pass
3. **Verify AWS permissions**: Make sure you can access DynamoDB and Lambda

## Next Steps

### For Production Use
1. **Change the secret**: Replace `development-secret-change-in-production`
2. **Add monitoring**: Set up basic CloudWatch alarms
3. **Multi-tenancy**: Add per-client isolation when needed
4. **Backup**: Consider DynamoDB backups for critical data

### For Development
1. **Deploy your own**: Use the `ultra-simple/` directory to deploy your own instance
2. **Customize**: Modify the Lambda function for your specific needs
3. **Enhance**: Add features incrementally based on real requirements

## Architecture Summary

What's actually deployed:
```
WordPress Form → Function URL → Lambda → DynamoDB
```

- **Function URL**: Direct HTTPS endpoint (no API Gateway)
- **Lambda**: Single function handles everything (auth + storage)
- **DynamoDB**: Simple table with 30-day TTL
- **Cost**: $0.00/month (Free Tier)

## Success!

If you got a successful response from the test script, **you're done!** The system is working and ready to handle your WordPress forms.

**Next**: Try the WordPress integration code above and watch your form data flow into DynamoDB.

---

*This system is deliberately simple - working is better than perfect.*
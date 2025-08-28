# Form-Bridge WordPress Plugin

**Connects WordPress forms to Form-Bridge serverless backend**

## Plugin Versions

### Standard Version (form-bridge.php)
- Version: 1.1.0  
- Features: Core functionality, 7 form integrations
- Best for: Most WordPress sites

### Enhanced Version (form-bridge-enhanced.php) 
- Version: 1.2.0
- Features: Advanced dashboard, retry queue, 9+ integrations, WooCommerce support
- Best for: Production sites requiring advanced features

Compatible with: WordPress 5.0+  
Tested up to: WordPress 6.4  
License: MIT  

## Overview

The Form-Bridge WordPress plugin automatically sends form submissions from popular WordPress form plugins to your Form-Bridge serverless backend. It supports HMAC authentication and provides a comprehensive admin interface for configuration and testing.

## Features

✅ **Universal Form Support**: Works with 6+ popular form plugins  
✅ **HMAC Authentication**: Secure request signing  
✅ **Admin Interface**: Easy configuration and testing  
✅ **Connection Testing**: Built-in endpoint validation  
✅ **Detailed Logging**: Debug form submissions  
✅ **Multi-site Compatible**: Works with WordPress Multisite  
✅ **Zero Dependencies**: Uses WordPress built-in functions only  

## Supported Form Plugins

### Standard Version
- **Contact Form 7** - Most popular contact form plugin
- **WPForms** - Drag & drop form builder  
- **Gravity Forms** - Advanced form solution
- **Ninja Forms** - User-friendly form builder
- **Formidable Forms** - Advanced form builder
- **WordPress Comments** - Built-in comment system

### Enhanced Version (Additional)
- **Elementor Forms** - Page builder forms
- **Fluent Forms** - Advanced form builder
- **WooCommerce Orders** - E-commerce integration
- **User Registration** - WordPress user events

## Installation

### Method 1: Upload Plugin Files
1. Download `form-bridge.php`
2. Upload to `/wp-content/plugins/form-bridge/`
3. Activate in WordPress admin → Plugins

### Method 2: Copy and Paste
1. Go to WordPress admin → Plugins → Add New → Upload Plugin
2. Upload the `form-bridge.php` file
3. Activate the plugin

## Configuration

### Step 1: Basic Settings
1. Go to **Settings → Form-Bridge** in WordPress admin
2. Configure these settings:

```
Enable Form-Bridge: ✅ Checked
Form-Bridge Endpoint: https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/
HMAC Secret: development-secret-change-in-production
Tenant ID: your-site-name_1
Request Timeout: 10 seconds
Log Submissions: ✅ Checked (for debugging)
```

### Step 2: Test Connection
1. Click "Test Connection" on the settings page
2. You should see: **✅ Connection successful!**
3. Check the submission ID matches your DynamoDB records

### Step 3: Verify Form Integration
1. Submit a test form on your website
2. Check WordPress error logs: `wp-content/debug.log`
3. Look for: `Form-Bridge [SUCCESS] contact_form_7: Sent successfully`

## Usage Examples

### Contact Form 7 Integration
The plugin automatically hooks into Contact Form 7:

```php
// Automatic - no code needed!
// When a CF7 form is submitted, it's automatically sent to Form-Bridge
```

### Custom Form Integration
For custom forms, use the plugin's core function:

```php
// Manual integration for custom forms
if (class_exists('FormBridgeConnector')) {
    $connector = new FormBridgeConnector();
    
    $form_data = array(
        'name' => $_POST['name'],
        'email' => $_POST['email'],
        'message' => $_POST['message']
    );
    
    $result = $connector->submit_to_form_bridge($form_data, 'custom_form');
    
    if ($result['success']) {
        echo 'Form sent successfully! ID: ' . $result['submission_id'];
    } else {
        echo 'Error: ' . $result['error'];
    }
}
```

### Programmatic Submission
```php
// Send data programmatically
$form_data = array(
    'user_id' => get_current_user_id(),
    'action' => 'user_login',
    'timestamp' => current_time('mysql')
);

// This will appear in DynamoDB as form_type: 'user_activity'
do_action('form_bridge_submit', $form_data, 'user_activity');
```

## Data Structure

### What Gets Sent to Form-Bridge
```json
{
    "form_data": {
        "name": "John Doe",
        "email": "john@example.com",
        "message": "Hello world"
    },
    "form_type": "contact_form_7_contact_us",
    "tenant_id": "my-site_1",
    "site_info": {
        "site_url": "https://my-website.com",
        "site_name": "My Website",
        "wp_version": "6.4",
        "plugin_version": "1.0.0"
    }
}
```

### What Gets Stored in DynamoDB
```json
{
    "tenant_id": "my-site_1",
    "submission_id": "sub_1737974400_abc123",
    "form_data": {
        "name": "John Doe",
        "email": "john@example.com", 
        "message": "Hello world"
    },
    "timestamp": 1737974400,
    "expires_at": 1740566400
}
```

## Security Features

### HMAC Authentication
- All requests are signed with HMAC-SHA256
- Timestamp validation prevents replay attacks
- Configurable timeout window (5 minutes default)

### Data Handling
- No sensitive data logged by default
- Secure transmission over HTTPS
- WordPress nonce verification for admin actions
- Input sanitization and validation

### Best Practices
```php
// 1. Change the default secret in production
update_option('form_bridge_secret', 'your-production-secret-here');

// 2. Use environment variables for secrets
define('FORM_BRIDGE_SECRET', $_ENV['FORM_BRIDGE_SECRET']);

// 3. Disable logging in production
update_option('form_bridge_log_submissions', 0);
```

## Troubleshooting

### Connection Issues

**❌ Connection failed: HTTP 403**
```bash
# Check your HMAC secret
# Verify timestamp is within 5 minutes
# Test with curl command from docs
```

**❌ Connection failed: HTTP 500**  
```bash
# Check Form-Bridge Lambda logs
aws logs tail /aws/lambda/form-bridge-ultra-prod --follow

# Look for DynamoDB permission errors
```

**❌ AJAX request failed**
```bash
# Check WordPress admin-ajax.php is accessible
# Verify nonce security tokens
# Check browser console for JavaScript errors
```

### Form Not Submitting

**Forms submit but no data in Form-Bridge**
1. Check plugin is enabled: Settings → Form-Bridge
2. Verify form plugin compatibility (see supported list)
3. Enable logging and check `wp-content/debug.log`
4. Test connection from plugin settings page

**Plugin not detecting form submissions**
```php
// Add manual debugging to your form
add_action('wp_footer', function() {
    if (is_admin()) return;
    ?>
    <script>
    jQuery(document).ready(function($) {
        $('form').submit(function() {
            console.log('Form submitted:', this);
        });
    });
    </script>
    <?php
});
```

### Debug Mode
Enable WordPress debug logging:

```php
// In wp-config.php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
define('WP_DEBUG_DISPLAY', false);
```

Then check: `wp-content/debug.log` for Form-Bridge entries.

## Performance

### Optimizations
- **Async Processing**: Forms don't wait for Form-Bridge response
- **Timeout Handling**: Configurable request timeouts (5-30 seconds)
- **Error Resilience**: Failed submissions don't break form functionality
- **Lightweight**: Single file plugin, no external dependencies

### Resource Usage
- **Memory**: < 1MB additional usage
- **Database**: No custom tables, uses WordPress options
- **Network**: Only outbound HTTPS requests to Form-Bridge

## Multisite Support

The plugin works with WordPress Multisite:

```php
// Each site gets unique tenant ID automatically
// Site 1: "network-name_1" 
// Site 2: "network-name_2"

// Override tenant ID per site:
update_option('form_bridge_tenant_id', 'custom-site-identifier');
```

## API Reference

### Hooks and Filters

**Actions:**
```php
// Manually submit data to Form-Bridge
do_action('form_bridge_submit', $form_data, $form_type);

// Hook into successful submissions
add_action('form_bridge_success', function($result, $form_data) {
    // Handle successful submission
}, 10, 2);

// Hook into failed submissions  
add_action('form_bridge_failed', function($error, $form_data) {
    // Handle failed submission
}, 10, 2);
```

**Filters:**
```php
// Modify form data before sending
add_filter('form_bridge_form_data', function($form_data, $form_type) {
    // Add custom fields or modify data
    $form_data['custom_field'] = 'custom_value';
    return $form_data;
}, 10, 2);

// Modify request arguments
add_filter('form_bridge_request_args', function($args) {
    // Modify timeout, headers, etc.
    $args['timeout'] = 15;
    return $args;
});
```

## FAQ

**Q: Will this slow down my forms?**  
A: No. Form-Bridge submissions happen after the form is processed, so users don't wait.

**Q: What happens if Form-Bridge is down?**  
A: Forms continue working normally. Failed submissions are logged for retry.

**Q: Can I use this with custom forms?**  
A: Yes! Use the `do_action('form_bridge_submit', $data, $type)` method.

**Q: Does this work with WooCommerce?**  
A: Not automatically, but you can hook into WooCommerce actions manually.

**Q: Can I see the data that was sent?**  
A: Yes, enable "Log Submissions" and check `wp-content/debug.log`.

## Changelog

### 1.0.0
- Initial release
- Support for 6 major form plugins
- HMAC authentication
- Admin interface with testing
- Comprehensive error handling
- WordPress Multisite compatibility

## Support

- **Documentation**: [Form-Bridge Docs](../../docs/mvp/)
- **Issues**: Check WordPress debug logs first
- **Testing**: Use built-in connection test feature

## License

MIT License - feel free to modify and distribute.

---

**Ready to use!** Install the plugin, configure your settings, and start sending WordPress form data to Form-Bridge automatically.
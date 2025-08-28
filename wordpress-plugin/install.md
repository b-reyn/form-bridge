# Form-Bridge WordPress Plugin Installation Guide

## Quick Start (2 Minutes)

1. **Download**: Choose your version
   - `form-bridge.php` - Standard version (recommended for most sites)
   - `form-bridge-enhanced.php` - Enhanced version with advanced features

2. **Upload**: 
   ```bash
   # Via WordPress Admin
   Plugins → Add New → Upload Plugin → Choose File → Activate
   
   # Via FTP
   Upload to: /wp-content/plugins/form-bridge/
   ```

3. **Configure**:
   - Go to: **Settings → Form-Bridge**
   - Endpoint: `https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/`
   - Secret: `development-secret-change-in-production`
   - Click **Test Connection** - should show ✅

4. **Done!** Your forms are now connected to Form-Bridge.

---

## Detailed Installation Options

### Option 1: WordPress Admin Upload (Recommended)

```bash
1. Login to WordPress admin
2. Go to Plugins → Add New
3. Click "Upload Plugin"
4. Choose form-bridge.php (or enhanced version)
5. Click "Install Now"
6. Click "Activate Plugin"
7. Go to Settings → Form-Bridge to configure
```

### Option 2: FTP Upload

```bash
1. Create directory: /wp-content/plugins/form-bridge/
2. Upload form-bridge.php to this directory
3. Login to WordPress admin
4. Go to Plugins → Installed Plugins
5. Find "Form-Bridge Connector" and click "Activate"
6. Go to Settings → Form-Bridge to configure
```

### Option 3: WP-CLI Installation

```bash
# Copy plugin file to plugins directory
wp plugin install /path/to/form-bridge.php --activate

# Or download and activate if hosted online
wp plugin install https://your-domain.com/form-bridge.php --activate

# Configure via WP-CLI
wp option update form_bridge_endpoint "https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/"
wp option update form_bridge_secret "your-production-secret"
wp option update form_bridge_tenant_id "your-site-name"
```

---

## Configuration Guide

### Basic Settings (Required)

1. **Go to Settings → Form-Bridge**

2. **Configure these settings**:

   | Setting | Value | Notes |
   |---------|-------|-------|
   | **Enable Form-Bridge** | ✅ Checked | Must be enabled |
   | **Endpoint** | `https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/` | Your Form-Bridge URL |
   | **HMAC Secret** | `development-secret-change-in-production` | ⚠️ Change for production |
   | **Tenant ID** | `your-site-name_1` | Auto-generated, customize as needed |
   | **Timeout** | `10` seconds | 5-30 seconds recommended |

3. **Test Connection**
   - Click "Test Connection" button
   - Should show: ✅ Connection successful!
   - Note the Submission ID for verification

### Advanced Settings (Enhanced Version)

| Setting | Default | Description |
|---------|---------|-------------|
| **Log Submissions** | ✅ Enabled | Debug logging (disable in production) |
| **Retry Failed** | ✅ Enabled | Auto-retry failed submissions |
| **User Registration** | ❌ Disabled | Send user signups to Form-Bridge |
| **WooCommerce Orders** | ❌ Disabled | Send order data to Form-Bridge |

---

## Version Comparison

### Standard Version (form-bridge.php)
```php
✅ 7 Form Plugin Integrations
✅ HMAC Authentication  
✅ Admin Interface
✅ Connection Testing
✅ Basic Logging
✅ WordPress Multisite
✅ Manual Submissions (hooks)
```

### Enhanced Version (form-bridge-enhanced.php)
```php
✅ Everything in Standard +
✅ 9+ Form Plugin Integrations
✅ Advanced Dashboard with Statistics
✅ Automatic Retry Queue
✅ WooCommerce Integration
✅ User Registration Events
✅ Enhanced Error Handling
✅ Activity Log Viewer
✅ System Requirements Check
✅ Developer Hooks & Filters
```

**Recommendation**: 
- Use **Standard** for simple sites
- Use **Enhanced** for production/e-commerce sites

---

## Post-Installation Checklist

### 1. Verify Form Integration

Test each form plugin you have installed:

```bash
# Contact Form 7
✅ Submit a CF7 form → Check WordPress logs for "Form-Bridge [SUCCESS]"

# WPForms  
✅ Submit a WPForms form → Check activity log in admin

# Gravity Forms
✅ Submit a Gravity form → Verify submission ID appears

# Other plugins
✅ Test each form type you use
```

### 2. Check Logs

Enable WordPress debug logging:
```php
// Add to wp-config.php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
define('WP_DEBUG_DISPLAY', false);
```

Check logs at: `wp-content/debug.log`
Look for: `Form-Bridge [SUCCESS]` or `Form-Bridge [FAILED]`

### 3. Production Setup

```php
// Change default secret (CRITICAL!)
update_option('form_bridge_secret', 'your-secure-production-secret');

// Disable logging (performance)
update_option('form_bridge_log_submissions', 0);

// Set appropriate timeout
update_option('form_bridge_timeout', 15);

// Configure tenant ID
update_option('form_bridge_tenant_id', 'your-company-site1');
```

### 4. Security Hardening

```php
// 1. Change default secret immediately
// 2. Use environment variables for secrets
define('FORM_BRIDGE_SECRET', $_ENV['FORM_BRIDGE_SECRET']);

// 3. Restrict file permissions
chmod 644 form-bridge.php

// 4. Hide from directory listings
// Add to .htaccess in plugins directory:
Options -Indexes
```

---

## Troubleshooting

### Connection Issues

**❌ Connection failed: HTTP 403**
```bash
Problem: HMAC authentication failed
Solution: 
- Verify secret matches Form-Bridge deployment
- Check timestamp synchronization
- Test with curl command from docs
```

**❌ Connection failed: HTTP 500**
```bash
Problem: Form-Bridge server error
Solution:
- Check AWS Lambda logs
- Verify DynamoDB permissions
- Test Form-Bridge deployment
```

**❌ Plugin not working**
```bash
Problem: Forms submitting but no Form-Bridge activity
Solution:
1. Check plugin is enabled in Settings
2. Verify form plugin compatibility 
3. Enable logging and check debug.log
4. Test connection from admin page
```

### Form Detection Issues

**Forms not being detected:**
```php
// Add debugging to see form submissions
add_action('wp_footer', function() {
    if (is_admin()) return;
    ?>
    <script>
    jQuery(document).ready(function($) {
        $('form').submit(function() {
            console.log('Form submitted:', this.action, this.method);
        });
    });
    </script>
    <?php
});
```

**Manual integration for custom forms:**
```php
// In your custom form handler
if (function_exists('form_bridge_submit')) {
    form_bridge_submit(array(
        'name' => $_POST['name'],
        'email' => $_POST['email'],
        'message' => $_POST['message']
    ), 'custom_contact_form');
}
```

### Performance Issues

**Slow form submissions:**
```php
// Reduce timeout
update_option('form_bridge_timeout', 5);

// Disable logging
update_option('form_bridge_log_submissions', 0);

// Use async processing (if available)
add_filter('form_bridge_request_args', function($args) {
    $args['blocking'] = false; // Fire and forget
    return $args;
});
```

---

## Multisite Installation

### Network Activation
```php
1. Upload plugin to /wp-content/plugins/
2. Go to Network Admin → Plugins
3. Click "Network Activate" 
4. Configure per-site settings
```

### Per-Site Configuration
```php
// Each site gets unique tenant ID automatically
// Site 1: "network-name_1"
// Site 2: "network-name_2" 

// Override per site if needed
update_option('form_bridge_tenant_id', 'custom-site-id');
```

---

## Developer Integration

### Custom Form Integration
```php
// Method 1: Use action hook
do_action('form_bridge_submit', $form_data, 'my_custom_form');

// Method 2: Use convenience function
form_bridge_submit($form_data, 'my_custom_form');

// Method 3: Direct class method (if instantiated)
if (class_exists('FormBridgeConnector')) {
    $connector = new FormBridgeConnector();
    $result = $connector->submit_to_form_bridge($data, 'custom');
}
```

### Hook into Events
```php
// Successful submissions
add_action('form_bridge_success', function($result, $form_data) {
    // Handle successful submission
    error_log('Form sent successfully: ' . $result['submission_id']);
}, 10, 2);

// Failed submissions
add_action('form_bridge_failed', function($error, $form_data) {
    // Handle failed submission
    error_log('Form failed: ' . $error);
}, 10, 2);
```

### Filter Form Data
```php
// Modify data before sending
add_filter('form_bridge_form_data', function($form_data, $form_type) {
    // Add custom fields
    $form_data['site_id'] = get_current_blog_id();
    $form_data['user_ip'] = $_SERVER['REMOTE_ADDR'];
    
    // Remove sensitive data
    unset($form_data['password']);
    
    return $form_data;
}, 10, 2);
```

---

## Support & Maintenance

### Regular Maintenance
```bash
1. Monitor wp-content/debug.log for errors
2. Check Form-Bridge admin dashboard monthly  
3. Test connection after WordPress/plugin updates
4. Review failed submissions in retry queue
5. Update HMAC secret periodically
```

### Performance Monitoring
```php
// Monitor submission success rate
$stats = get_option('form_bridge_stats', array());

// Check retry queue size (Enhanced version)
$queue = get_option('form_bridge_retry_queue', array());
if (count($queue) > 50) {
    // Alert admin of high failure rate
}
```

### Backup Configuration
```php
// Export current settings
$config = array(
    'endpoint' => get_option('form_bridge_endpoint'),
    'tenant_id' => get_option('form_bridge_tenant_id'),
    'enabled' => get_option('form_bridge_enabled'),
    'timeout' => get_option('form_bridge_timeout')
    // Note: Don't backup the secret!
);

// Save to file or database
update_option('form_bridge_backup_config', $config);
```

---

## Need Help?

1. **Check Connection**: Use built-in test feature
2. **Review Logs**: Check wp-content/debug.log  
3. **Verify Settings**: Ensure endpoint and secret are correct
4. **Test Manually**: Use developer hooks to test
5. **Documentation**: Refer to Form-Bridge docs for backend issues

**Ready to go!** Your WordPress forms are now connected to Form-Bridge with enterprise-grade reliability and security.
<?php
/**
 * Plugin Name: Form-Bridge Connector Enhanced
 * Plugin URI: https://github.com/your-repo/form-bridge
 * Description: Enhanced WordPress plugin that sends form submissions to Form-Bridge serverless backend with HMAC authentication. Supports 8+ form plugins including Contact Form 7, WPForms, Gravity Forms, Ninja Forms, Formidable Forms, Elementor Forms, Fluent Forms, WooCommerce, and WordPress comments.
 * Version: 1.2.0
 * Author: Form-Bridge Team
 * Requires at least: 5.0
 * Tested up to: 6.4
 * Requires PHP: 7.4
 * License: MIT
 * License URI: https://opensource.org/licenses/MIT
 * Text Domain: form-bridge
 * Domain Path: /languages
 * Network: true
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Enhanced Form-Bridge Plugin Class
 */
class FormBridgeConnectorEnhanced {
    
    /**
     * Plugin version
     */
    const VERSION = '1.2.0';
    
    /**
     * Minimum WordPress version
     */
    const MIN_WP_VERSION = '5.0';
    
    /**
     * Minimum PHP version
     */
    const MIN_PHP_VERSION = '7.4';
    
    /**
     * Default endpoint URL
     */
    const DEFAULT_ENDPOINT = 'https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/';
    
    /**
     * Default secret for development
     */
    const DEFAULT_SECRET = 'development-secret-change-in-production';
    
    /**
     * Retry queue option name
     */
    const RETRY_QUEUE_OPTION = 'form_bridge_retry_queue';
    
    /**
     * Initialize the plugin
     */
    public function __construct() {
        // Check system requirements
        if (!$this->check_requirements()) {
            return;
        }
        
        add_action('init', array($this, 'init'));
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('admin_init', array($this, 'init_settings'));
        add_action('admin_enqueue_scripts', array($this, 'enqueue_admin_scripts'));
        
        // Hook into popular form plugins
        $this->init_form_hooks();
        
        // Add AJAX endpoints for testing
        add_action('wp_ajax_test_form_bridge', array($this, 'test_connection'));
        add_action('wp_ajax_get_form_bridge_log', array($this, 'get_activity_log'));
        add_action('wp_ajax_retry_failed_submissions', array($this, 'retry_failed_submissions'));
        
        // Add custom action for manual submissions
        add_action('form_bridge_submit', array($this, 'handle_manual_submission'), 10, 2);
        
        // Admin notices for configuration
        add_action('admin_notices', array($this, 'admin_notices'));
        
        // Retry failed submissions via cron
        add_action('form_bridge_retry_failed', array($this, 'process_retry_queue'));
        if (!wp_next_scheduled('form_bridge_retry_failed')) {
            wp_schedule_event(time(), 'hourly', 'form_bridge_retry_failed');
        }
    }
    
    /**
     * Check system requirements
     */
    private function check_requirements() {
        global $wp_version;
        
        // Check WordPress version
        if (version_compare($wp_version, self::MIN_WP_VERSION, '<')) {
            add_action('admin_notices', function() {
                echo '<div class="notice notice-error"><p>';
                printf(
                    __('Form-Bridge requires WordPress %s or higher. You are running %s.', 'form-bridge'),
                    self::MIN_WP_VERSION,
                    $GLOBALS['wp_version']
                );
                echo '</p></div>';
            });
            return false;
        }
        
        // Check PHP version
        if (version_compare(PHP_VERSION, self::MIN_PHP_VERSION, '<')) {
            add_action('admin_notices', function() {
                echo '<div class="notice notice-error"><p>';
                printf(
                    __('Form-Bridge requires PHP %s or higher. You are running %s.', 'form-bridge'),
                    self::MIN_PHP_VERSION,
                    PHP_VERSION
                );
                echo '</p></div>';
            });
            return false;
        }
        
        return true;
    }
    
    /**
     * Plugin initialization
     */
    public function init() {
        load_plugin_textdomain('form-bridge', false, dirname(plugin_basename(__FILE__)) . '/languages');
    }
    
    /**
     * Enqueue admin scripts and styles
     */
    public function enqueue_admin_scripts($hook) {
        // Only load on our settings page
        if ($hook !== 'settings_page_form-bridge') {
            return;
        }
        
        wp_enqueue_script('jquery');
        wp_enqueue_style('form-bridge-admin', false, array(), self::VERSION);
        wp_add_inline_style('form-bridge-admin', '
            .form-bridge-status { font-weight: bold; }
            .form-bridge-success { color: #00a32a; }
            .form-bridge-error { color: #d63638; }
            .form-bridge-testing { color: #0073aa; }
            .form-bridge-warning { color: #dba617; }
            .form-bridge-log { background: #f0f0f1; padding: 15px; margin: 15px 0; border-left: 4px solid #0073aa; max-height: 300px; overflow-y: auto; }
            .form-bridge-log pre { margin: 0; overflow-x: auto; font-family: Consolas, Monaco, monospace; font-size: 12px; }
            .form-bridge-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .form-bridge-card { background: #fff; border: 1px solid #c3c4c7; border-radius: 4px; padding: 15px; }
            .form-bridge-metric { text-align: center; margin: 10px 0; }
            .form-bridge-metric .number { font-size: 24px; font-weight: bold; display: block; }
            .form-bridge-metric .label { font-size: 14px; color: #646970; }
            @media (max-width: 768px) {
                .form-bridge-grid { grid-template-columns: 1fr; }
            }
        ');
    }
    
    /**
     * Admin notices for important configuration
     */
    public function admin_notices() {
        $screen = get_current_screen();
        
        // Only show on relevant pages
        if (!in_array($screen->id, array('dashboard', 'plugins', 'settings_page_form-bridge'))) {
            return;
        }
        
        // Check if using default secret in production
        if (get_option('form_bridge_secret') === self::DEFAULT_SECRET && !defined('WP_DEBUG')) {
            echo '<div class="notice notice-warning is-dismissible">';
            echo '<p><strong>' . __('Form-Bridge Security Warning:', 'form-bridge') . '</strong> ';
            echo __('You are using the default HMAC secret. Please change this in production!', 'form-bridge');
            echo ' <a href="' . admin_url('options-general.php?page=form-bridge') . '">' . __('Configure Now', 'form-bridge') . '</a></p>';
            echo '</div>';
        }
        
        // Check if plugin is disabled
        if (!get_option('form_bridge_enabled', 1)) {
            echo '<div class="notice notice-info is-dismissible">';
            echo '<p><strong>' . __('Form-Bridge Notice:', 'form-bridge') . '</strong> ';
            echo __('Form submissions are not being sent to Form-Bridge because the plugin is disabled.', 'form-bridge');
            echo ' <a href="' . admin_url('options-general.php?page=form-bridge') . '">' . __('Enable Now', 'form-bridge') . '</a></p>';
            echo '</div>';
        }
    }
    
    /**
     * Initialize form hooks for popular plugins
     */
    private function init_form_hooks() {
        // Contact Form 7
        if (class_exists('WPCF7_ContactForm')) {
            add_action('wpcf7_mail_sent', array($this, 'handle_cf7_submission'));
        }
        
        // WPForms
        if (class_exists('WPForms')) {
            add_action('wpforms_process_complete', array($this, 'handle_wpforms_submission'), 10, 4);
        }
        
        // Gravity Forms
        if (class_exists('GFForms')) {
            add_action('gform_after_submission', array($this, 'handle_gravity_forms_submission'), 10, 2);
        }
        
        // Ninja Forms
        if (class_exists('Ninja_Forms')) {
            add_action('ninja_forms_after_submission', array($this, 'handle_ninja_forms_submission'));
        }
        
        // Formidable Forms
        if (class_exists('FrmHooksController')) {
            add_action('frm_after_create_entry', array($this, 'handle_formidable_submission'), 30, 2);
        }
        
        // Elementor Forms
        if (class_exists('\\ElementorPro\\Plugin')) {
            add_action('elementor_pro/forms/new_record', array($this, 'handle_elementor_submission'), 10, 2);
        }
        
        // Fluent Forms
        if (class_exists('FluentForm\\Framework\\Foundation\\Application')) {
            add_action('fluentform_submission_inserted', array($this, 'handle_fluent_forms_submission'), 10, 3);
        }
        
        // Generic WordPress comments
        add_action('comment_post', array($this, 'handle_comment_submission'), 10, 3);
        
        // WooCommerce events (optional)
        if (class_exists('WooCommerce')) {
            add_action('woocommerce_checkout_order_processed', array($this, 'handle_woocommerce_order'), 10, 3);
        }
        
        // User registration
        add_action('user_register', array($this, 'handle_user_registration'));
    }
    
    /**
     * Add admin menu page
     */
    public function add_admin_menu() {
        add_options_page(
            __('Form-Bridge Settings', 'form-bridge'),
            __('Form-Bridge', 'form-bridge'),
            'manage_options',
            'form-bridge',
            array($this, 'admin_page')
        );
    }
    
    /**
     * Initialize settings
     */
    public function init_settings() {
        register_setting('form_bridge_settings', 'form_bridge_endpoint');
        register_setting('form_bridge_settings', 'form_bridge_secret');
        register_setting('form_bridge_settings', 'form_bridge_tenant_id');
        register_setting('form_bridge_settings', 'form_bridge_enabled');
        register_setting('form_bridge_settings', 'form_bridge_log_submissions');
        register_setting('form_bridge_settings', 'form_bridge_timeout');
        register_setting('form_bridge_settings', 'form_bridge_wc_enabled');
        register_setting('form_bridge_settings', 'form_bridge_retry_failed');
        register_setting('form_bridge_settings', 'form_bridge_user_registration');
    }
    
    /**
     * Admin settings page
     */
    public function admin_page() {
        $stats = $this->get_submission_stats();
        ?>
        <div class="wrap">
            <h1><?php _e('Form-Bridge Settings', 'form-bridge'); ?></h1>
            
            <div class="notice notice-info">
                <p><strong><?php _e('Form-Bridge Status:', 'form-bridge'); ?></strong> 
                   <span id="fb-status"><?php _e('Testing connection...', 'form-bridge'); ?></span>
                </p>
            </div>
            
            <!-- Statistics Dashboard -->
            <div class="form-bridge-grid">
                <div class="form-bridge-card">
                    <h3><?php _e('Submission Statistics', 'form-bridge'); ?></h3>
                    <div class="form-bridge-grid">
                        <div class="form-bridge-metric">
                            <span class="number form-bridge-success"><?php echo esc_html($stats['successful']); ?></span>
                            <span class="label"><?php _e('Successful', 'form-bridge'); ?></span>
                        </div>
                        <div class="form-bridge-metric">
                            <span class="number form-bridge-error"><?php echo esc_html($stats['failed']); ?></span>
                            <span class="label"><?php _e('Failed', 'form-bridge'); ?></span>
                        </div>
                    </div>
                    <?php if ($stats['failed'] > 0): ?>
                        <p><button type="button" id="retry-failed" class="button button-secondary">
                            <?php _e('Retry Failed Submissions', 'form-bridge'); ?>
                        </button></p>
                    <?php endif; ?>
                </div>
                
                <div class="form-bridge-card">
                    <h3><?php _e('System Status', 'form-bridge'); ?></h3>
                    <ul>
                        <li><?php printf(__('Plugin Version: %s', 'form-bridge'), self::VERSION); ?></li>
                        <li><?php printf(__('WordPress: %s', 'form-bridge'), get_bloginfo('version')); ?></li>
                        <li><?php printf(__('PHP: %s', 'form-bridge'), PHP_VERSION); ?></li>
                        <li><?php printf(__('Multisite: %s', 'form-bridge'), is_multisite() ? __('Yes', 'form-bridge') : __('No', 'form-bridge')); ?></li>
                        <li><?php printf(__('Debug Mode: %s', 'form-bridge'), defined('WP_DEBUG') && WP_DEBUG ? __('Enabled', 'form-bridge') : __('Disabled', 'form-bridge')); ?></li>
                    </ul>
                </div>
            </div>
            
            <form method="post" action="options.php">
                <?php
                settings_fields('form_bridge_settings');
                do_settings_sections('form_bridge_settings');
                ?>
                
                <table class="form-table">
                    <tr>
                        <th scope="row"><?php _e('Enable Form-Bridge', 'form-bridge'); ?></th>
                        <td>
                            <label>
                                <input type="checkbox" name="form_bridge_enabled" value="1" 
                                       <?php checked(get_option('form_bridge_enabled', 1)); ?> />
                                <?php _e('Send form submissions to Form-Bridge', 'form-bridge'); ?>
                            </label>
                        </td>
                    </tr>
                    
                    <tr>
                        <th scope="row"><?php _e('Form-Bridge Endpoint', 'form-bridge'); ?></th>
                        <td>
                            <input type="url" name="form_bridge_endpoint" 
                                   value="<?php echo esc_attr(get_option('form_bridge_endpoint', self::DEFAULT_ENDPOINT)); ?>" 
                                   class="regular-text" required />
                            <p class="description">
                                <?php _e('The Lambda Function URL endpoint for your Form-Bridge deployment.', 'form-bridge'); ?>
                            </p>
                        </td>
                    </tr>
                    
                    <tr>
                        <th scope="row"><?php _e('HMAC Secret', 'form-bridge'); ?></th>
                        <td>
                            <input type="password" name="form_bridge_secret" 
                                   value="<?php echo esc_attr(get_option('form_bridge_secret', self::DEFAULT_SECRET)); ?>" 
                                   class="regular-text" required />
                            <?php if (get_option('form_bridge_secret') === self::DEFAULT_SECRET): ?>
                                <p class="description form-bridge-warning">
                                    <strong><?php _e('⚠️ Security Warning:', 'form-bridge'); ?></strong>
                                    <?php _e('Change this default secret for production use!', 'form-bridge'); ?>
                                </p>
                            <?php else: ?>
                                <p class="description">
                                    <?php _e('The HMAC secret key for request authentication.', 'form-bridge'); ?>
                                </p>
                            <?php endif; ?>
                        </td>
                    </tr>
                    
                    <tr>
                        <th scope="row"><?php _e('Tenant ID', 'form-bridge'); ?></th>
                        <td>
                            <input type="text" name="form_bridge_tenant_id" 
                                   value="<?php echo esc_attr(get_option('form_bridge_tenant_id', get_bloginfo('name') . '_' . get_current_blog_id())); ?>" 
                                   class="regular-text" />
                            <p class="description">
                                <?php _e('Unique identifier for this WordPress site. Used for data organization in multi-tenant environments.', 'form-bridge'); ?>
                            </p>
                        </td>
                    </tr>
                    
                    <tr>
                        <th scope="row"><?php _e('Request Timeout', 'form-bridge'); ?></th>
                        <td>
                            <input type="number" name="form_bridge_timeout" min="5" max="30"
                                   value="<?php echo esc_attr(get_option('form_bridge_timeout', 10)); ?>" />
                            <p class="description">
                                <?php _e('Timeout in seconds for Form-Bridge requests (5-30 seconds).', 'form-bridge'); ?>
                            </p>
                        </td>
                    </tr>
                    
                    <tr>
                        <th scope="row"><?php _e('Advanced Options', 'form-bridge'); ?></th>
                        <td>
                            <fieldset>
                                <label>
                                    <input type="checkbox" name="form_bridge_log_submissions" value="1" 
                                           <?php checked(get_option('form_bridge_log_submissions', 1)); ?> />
                                    <?php _e('Enable detailed logging for debugging', 'form-bridge'); ?>
                                </label><br>
                                
                                <label>
                                    <input type="checkbox" name="form_bridge_retry_failed" value="1" 
                                           <?php checked(get_option('form_bridge_retry_failed', 1)); ?> />
                                    <?php _e('Automatically retry failed submissions', 'form-bridge'); ?>
                                </label><br>
                                
                                <label>
                                    <input type="checkbox" name="form_bridge_user_registration" value="1" 
                                           <?php checked(get_option('form_bridge_user_registration', 0)); ?> />
                                    <?php _e('Send user registrations to Form-Bridge', 'form-bridge'); ?>
                                </label><br>
                                
                                <?php if (class_exists('WooCommerce')): ?>
                                <label>
                                    <input type="checkbox" name="form_bridge_wc_enabled" value="1" 
                                           <?php checked(get_option('form_bridge_wc_enabled', 0)); ?> />
                                    <?php _e('Send WooCommerce orders to Form-Bridge', 'form-bridge'); ?>
                                </label><br>
                                <?php endif; ?>
                            </fieldset>
                            <p class="description">
                                <?php _e('Additional integration options and features.', 'form-bridge'); ?>
                            </p>
                        </td>
                    </tr>
                </table>
                
                <?php submit_button(); ?>
            </form>
            
            <hr>
            
            <h2><?php _e('Test Connection', 'form-bridge'); ?></h2>
            <p><?php _e('Test your Form-Bridge connection with a sample submission:', 'form-bridge'); ?></p>
            
            <button type="button" id="test-connection" class="button button-secondary">
                <?php _e('Test Connection', 'form-bridge'); ?>
            </button>
            
            <div id="test-results" style="margin-top: 20px;"></div>
            
            <hr>
            
            <h2><?php _e('Supported Integrations', 'form-bridge'); ?></h2>
            <div class="form-bridge-grid">
                <div>
                    <h3><?php _e('Form Builders', 'form-bridge'); ?></h3>
                    <ul>
                        <li><?php echo class_exists('WPCF7_ContactForm') ? '✅' : '❌'; ?> Contact Form 7</li>
                        <li><?php echo class_exists('WPForms') ? '✅' : '❌'; ?> WPForms</li>
                        <li><?php echo class_exists('GFForms') ? '✅' : '❌'; ?> Gravity Forms</li>
                        <li><?php echo class_exists('Ninja_Forms') ? '✅' : '❌'; ?> Ninja Forms</li>
                        <li><?php echo class_exists('FrmHooksController') ? '✅' : '❌'; ?> Formidable Forms</li>
                        <li><?php echo class_exists('\\ElementorPro\\Plugin') ? '✅' : '❌'; ?> Elementor Forms</li>
                        <li><?php echo class_exists('FluentForm\\Framework\\Foundation\\Application') ? '✅' : '❌'; ?> Fluent Forms</li>
                    </ul>
                </div>
                <div>
                    <h3><?php _e('Other Integrations', 'form-bridge'); ?></h3>
                    <ul>
                        <li>✅ WordPress Comments</li>
                        <li><?php echo get_option('form_bridge_user_registration', 0) ? '✅' : '❌'; ?> User Registration</li>
                        <li><?php echo class_exists('WooCommerce') && get_option('form_bridge_wc_enabled', 0) ? '✅' : '❌'; ?> WooCommerce Orders</li>
                        <li>✅ Custom Forms (via hooks)</li>
                    </ul>
                </div>
            </div>
            
            <hr>
            
            <div class="form-bridge-log">
                <h3><?php _e('Recent Activity Log', 'form-bridge'); ?></h3>
                <div id="activity-log">
                    <p><?php _e('Loading recent submissions...', 'form-bridge'); ?></p>
                </div>
            </div>
        </div>
        
        <script type="text/javascript">
        jQuery(document).ready(function($) {
            // Test connection on page load
            testConnection();
            
            $('#test-connection').click(function() {
                testConnection();
            });
            
            $('#retry-failed').click(function() {
                retryFailedSubmissions();
            });
            
            function testConnection() {
                $('#test-results').html('<div class="notice notice-info"><p><?php _e("Testing connection...", "form-bridge"); ?></p></div>');
                $('#fb-status').html('<span class="form-bridge-status form-bridge-testing">🔄 <?php _e("Testing...", "form-bridge"); ?></span>');
                $('#test-connection').prop('disabled', true).text('<?php _e("Testing...", "form-bridge"); ?>');
                
                $.ajax({
                    url: ajaxurl,
                    type: 'POST',
                    data: {
                        action: 'test_form_bridge',
                        nonce: '<?php echo wp_create_nonce("test_form_bridge"); ?>'
                    },
                    success: function(response) {
                        if (response.success) {
                            $('#test-results').html('<div class="notice notice-success"><p><strong><?php _e("✅ Connection successful!", "form-bridge"); ?></strong><br>' +
                                'Submission ID: <code>' + response.data.submission_id + '</code><br>' +
                                'Response Time: ' + (response.data.response_time || 'N/A') + 'ms<br>' +
                                'Timestamp: ' + new Date().toLocaleString() + '</p></div>');
                            $('#fb-status').html('<span class="form-bridge-status form-bridge-success">✅ <?php _e("Connected", "form-bridge"); ?></span>');
                        } else {
                            $('#test-results').html('<div class="notice notice-error"><p><strong><?php _e("❌ Connection failed:", "form-bridge"); ?></strong><br>' + 
                                '<code>' + response.data + '</code></p></div>');
                            $('#fb-status').html('<span class="form-bridge-status form-bridge-error">❌ <?php _e("Connection failed", "form-bridge"); ?></span>');
                        }
                    },
                    error: function(xhr, status, error) {
                        $('#test-results').html('<div class="notice notice-error"><p><strong><?php _e("❌ AJAX request failed", "form-bridge"); ?></strong><br>' +
                            'Status: ' + status + '<br>Error: ' + error + '</p></div>');
                        $('#fb-status').html('<span class="form-bridge-status form-bridge-error">❌ <?php _e("AJAX failed", "form-bridge"); ?></span>');
                    },
                    complete: function() {
                        $('#test-connection').prop('disabled', false).text('<?php _e("Test Connection", "form-bridge"); ?>');
                    }
                });
            }
            
            function retryFailedSubmissions() {
                $('#retry-failed').prop('disabled', true).text('<?php _e("Retrying...", "form-bridge"); ?>');
                
                $.ajax({
                    url: ajaxurl,
                    type: 'POST',
                    data: {
                        action: 'retry_failed_submissions',
                        nonce: '<?php echo wp_create_nonce("retry_failed_submissions"); ?>'
                    },
                    success: function(response) {
                        if (response.success) {
                            alert('<?php _e("Retry completed successfully!", "form-bridge"); ?>');
                            location.reload();
                        } else {
                            alert('<?php _e("Retry failed:", "form-bridge"); ?> ' + response.data);
                        }
                    },
                    complete: function() {
                        $('#retry-failed').prop('disabled', false).text('<?php _e("Retry Failed Submissions", "form-bridge"); ?>');
                    }
                });
            }
            
            // Load activity log
            function loadActivityLog() {
                $.ajax({
                    url: ajaxurl,
                    type: 'POST',
                    data: {
                        action: 'get_form_bridge_log',
                        nonce: '<?php echo wp_create_nonce("get_form_bridge_log"); ?>'
                    },
                    success: function(response) {
                        if (response.success) {
                            $('#activity-log').html(response.data);
                        } else {
                            $('#activity-log').html('<p><?php _e("No recent activity or logging disabled.", "form-bridge"); ?></p>');
                        }
                    }
                });
            }
            
            // Load activity log on page load and refresh periodically
            loadActivityLog();
            setInterval(loadActivityLog, 30000); // Refresh every 30 seconds
        });
        </script>
        <?php
    }
    
    /**
     * Get submission statistics from logs
     */
    private function get_submission_stats() {
        $stats = array('successful' => 0, 'failed' => 0);
        
        if (!get_option('form_bridge_log_submissions', 1)) {
            return $stats;
        }
        
        $log_file = WP_CONTENT_DIR . '/debug.log';
        if (!file_exists($log_file)) {
            return $stats;
        }
        
        $log_content = file_get_contents($log_file);
        $lines = explode("\n", $log_content);
        
        foreach ($lines as $line) {
            if (strpos($line, 'Form-Bridge') !== false) {
                if (strpos($line, '[SUCCESS]') !== false) {
                    $stats['successful']++;
                } elseif (strpos($line, '[FAILED]') !== false) {
                    $stats['failed']++;
                }
            }
        }
        
        return $stats;
    }
    
    /**
     * Test Form-Bridge connection via AJAX
     */
    public function test_connection() {
        if (!wp_verify_nonce($_POST['nonce'], 'test_form_bridge')) {
            wp_die(__('Security check failed', 'form-bridge'));
        }
        
        $start_time = microtime(true);
        
        $test_data = array(
            'test' => true,
            'plugin_version' => self::VERSION,
            'wordpress_version' => get_bloginfo('version'),
            'php_version' => PHP_VERSION,
            'site_url' => get_site_url(),
            'site_name' => get_bloginfo('name'),
            'multisite' => is_multisite(),
            'timestamp' => current_time('mysql'),
            'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'Unknown',
            'admin_email' => get_option('admin_email'),
            'timezone' => wp_timezone_string()
        );
        
        $result = $this->submit_to_form_bridge($test_data, 'plugin_connection_test');
        
        if ($result['success']) {
            $result['response_time'] = round((microtime(true) - $start_time) * 1000, 2);
            wp_send_json_success($result);
        } else {
            wp_send_json_error($result['error']);
        }
    }
    
    /**
     * Get activity log via AJAX
     */
    public function get_activity_log() {
        if (!wp_verify_nonce($_POST['nonce'], 'get_form_bridge_log')) {
            wp_die(__('Security check failed', 'form-bridge'));
        }
        
        if (!get_option('form_bridge_log_submissions', 1)) {
            wp_send_json_error(__('Logging is disabled', 'form-bridge'));
        }
        
        $log_file = WP_CONTENT_DIR . '/debug.log';
        if (!file_exists($log_file)) {
            wp_send_json_success('<p>' . __('No log file found. Enable WordPress debug logging in wp-config.php.', 'form-bridge') . '</p>');
        }
        
        $log_content = file_get_contents($log_file);
        $lines = explode("\n", $log_content);
        $form_bridge_lines = array();
        
        // Filter for Form-Bridge entries (last 20 entries)
        foreach (array_reverse($lines) as $line) {
            if (strpos($line, 'Form-Bridge') !== false && count($form_bridge_lines) < 20) {
                $form_bridge_lines[] = esc_html($line);
            }
        }
        
        if (empty($form_bridge_lines)) {
            wp_send_json_success('<p>' . __('No recent Form-Bridge activity found.', 'form-bridge') . '</p>');
        }
        
        $output = '<pre>' . implode("\n", $form_bridge_lines) . '</pre>';
        wp_send_json_success($output);
    }
    
    /**
     * Retry failed submissions via AJAX
     */
    public function retry_failed_submissions() {
        if (!wp_verify_nonce($_POST['nonce'], 'retry_failed_submissions')) {
            wp_die(__('Security check failed', 'form-bridge'));
        }
        
        $result = $this->process_retry_queue();
        wp_send_json_success($result);
    }
    
    /**
     * Handle manual form submissions via action hook
     */
    public function handle_manual_submission($form_data, $form_type = 'manual') {
        $this->submit_to_form_bridge($form_data, $form_type);
    }
    
    /**
     * Core function to submit data to Form-Bridge
     */
    private function submit_to_form_bridge($form_data, $form_type = 'unknown') {
        // Check if plugin is enabled
        if (!get_option('form_bridge_enabled', 1)) {
            return array('success' => false, 'error' => 'Form-Bridge plugin is disabled');
        }
        
        $endpoint = get_option('form_bridge_endpoint', self::DEFAULT_ENDPOINT);
        $secret = get_option('form_bridge_secret', self::DEFAULT_SECRET);
        $tenant_id = get_option('form_bridge_tenant_id', get_bloginfo('name') . '_' . get_current_blog_id());
        $timeout = get_option('form_bridge_timeout', 10);
        
        // Apply filter to allow modification of form data
        $form_data = apply_filters('form_bridge_form_data', $form_data, $form_type);
        
        // Prepare payload
        $payload_data = array(
            'form_data' => $form_data,
            'form_type' => $form_type,
            'tenant_id' => $tenant_id,
            'submission_time' => current_time('c'),
            'site_info' => array(
                'site_url' => get_site_url(),
                'site_name' => get_bloginfo('name'),
                'wp_version' => get_bloginfo('version'),
                'php_version' => PHP_VERSION,
                'plugin_version' => self::VERSION,
                'multisite' => is_multisite(),
                'blog_id' => get_current_blog_id(),
                'user_ip' => $this->get_client_ip(),
                'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'Unknown',
                'timezone' => wp_timezone_string()
            )
        );
        
        $payload = json_encode($payload_data);
        $timestamp = time();
        
        // Generate HMAC signature
        $signature = hash_hmac('sha256', $timestamp . ':' . $payload, $secret);
        
        // Prepare request
        $args = array(
            'method' => 'POST',
            'timeout' => $timeout,
            'httpversion' => '1.1',
            'blocking' => true,
            'headers' => array(
                'Content-Type' => 'application/json',
                'X-Signature' => $signature,
                'X-Timestamp' => $timestamp,
                'User-Agent' => 'Form-Bridge-WordPress/' . self::VERSION,
                'Accept' => 'application/json'
            ),
            'body' => $payload,
            'cookies' => array(),
            'sslverify' => true
        );
        
        // Apply filter to allow modification of request args
        $args = apply_filters('form_bridge_request_args', $args);
        
        // Send request
        $response = wp_remote_post($endpoint, $args);
        
        // Handle response
        if (is_wp_error($response)) {
            $error = 'HTTP Error: ' . $response->get_error_message();
            $this->log_submission($form_data, $form_type, false, $error);
            $this->add_to_retry_queue($form_data, $form_type, $error);
            return array('success' => false, 'error' => $error);
        }
        
        $status_code = wp_remote_retrieve_response_code($response);
        $response_body = wp_remote_retrieve_body($response);
        
        if ($status_code !== 200) {
            $error = 'HTTP ' . $status_code . ': ' . $response_body;
            $this->log_submission($form_data, $form_type, false, $error);
            $this->add_to_retry_queue($form_data, $form_type, $error);
            return array('success' => false, 'error' => $error);
        }
        
        $result = json_decode($response_body, true);
        
        if ($result && isset($result['success']) && $result['success']) {
            $this->log_submission($form_data, $form_type, true, $result);
            
            // Trigger success action
            do_action('form_bridge_success', $result, $form_data);
            
            return $result;
        } else {
            $error = 'Invalid response: ' . $response_body;
            $this->log_submission($form_data, $form_type, false, $error);
            $this->add_to_retry_queue($form_data, $form_type, $error);
            
            // Trigger failure action
            do_action('form_bridge_failed', $error, $form_data);
            
            return array('success' => false, 'error' => $error);
        }
    }
    
    /**
     * Add failed submission to retry queue
     */
    private function add_to_retry_queue($form_data, $form_type, $error) {
        if (!get_option('form_bridge_retry_failed', 1)) {
            return;
        }
        
        $queue = get_option(self::RETRY_QUEUE_OPTION, array());
        $queue[] = array(
            'form_data' => $form_data,
            'form_type' => $form_type,
            'error' => $error,
            'attempts' => 0,
            'created' => time()
        );
        
        // Keep only last 100 failed submissions
        if (count($queue) > 100) {
            $queue = array_slice($queue, -100);
        }
        
        update_option(self::RETRY_QUEUE_OPTION, $queue);
    }
    
    /**
     * Process retry queue (called by cron)
     */
    public function process_retry_queue() {
        $queue = get_option(self::RETRY_QUEUE_OPTION, array());
        if (empty($queue)) {
            return array('processed' => 0, 'succeeded' => 0);
        }
        
        $processed = 0;
        $succeeded = 0;
        $updated_queue = array();
        
        foreach ($queue as $item) {
            // Skip items older than 7 days or with 3+ attempts
            if ($item['attempts'] >= 3 || (time() - $item['created']) > 7 * DAY_IN_SECONDS) {
                continue;
            }
            
            $processed++;
            $result = $this->submit_to_form_bridge($item['form_data'], $item['form_type']);
            
            if ($result['success']) {
                $succeeded++;
                // Don't add back to queue
            } else {
                // Add back with incremented attempt count
                $item['attempts']++;
                $updated_queue[] = $item;
            }
        }
        
        update_option(self::RETRY_QUEUE_OPTION, $updated_queue);
        
        return array(
            'processed' => $processed,
            'succeeded' => $succeeded,
            'remaining' => count($updated_queue)
        );
    }
    
    /**
     * Log form submission (if enabled)
     */
    private function log_submission($form_data, $form_type, $success, $result) {
        if (!get_option('form_bridge_log_submissions', 1)) {
            return;
        }
        
        $status = $success ? 'SUCCESS' : 'FAILED';
        $submission_id = $success && isset($result['submission_id']) ? $result['submission_id'] : 'none';
        
        error_log(sprintf(
            'Form-Bridge [%s] %s submission (%s): %s',
            $status,
            $form_type,
            $submission_id,
            $success ? 'Sent successfully' : $result
        ));
    }
    
    /**
     * Get client IP address
     */
    private function get_client_ip() {
        $ip_headers = array(
            'HTTP_CLIENT_IP',
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_FORWARDED',
            'HTTP_X_CLUSTER_CLIENT_IP',
            'HTTP_FORWARDED_FOR',
            'HTTP_FORWARDED',
            'REMOTE_ADDR'
        );
        
        foreach ($ip_headers as $header) {
            if (!empty($_SERVER[$header])) {
                $ip = $_SERVER[$header];
                // Handle comma-separated IPs
                if (strpos($ip, ',') !== false) {
                    $ip = trim(explode(',', $ip)[0]);
                }
                if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
                    return $ip;
                }
            }
        }
        
        return $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    }
    
    // Form Handler Methods
    
    /**
     * Handle Contact Form 7 submissions
     */
    public function handle_cf7_submission($contact_form) {
        $submission = WPCF7_Submission::get_instance();
        if (!$submission) return;
        
        $form_data = $submission->get_posted_data();
        $form_title = $contact_form->title();
        
        $this->submit_to_form_bridge($form_data, 'contact_form_7_' . sanitize_title($form_title));
    }
    
    /**
     * Handle WPForms submissions
     */
    public function handle_wpforms_submission($fields, $entry, $form_data, $entry_id) {
        $form_submission = array();
        foreach ($fields as $field_id => $field) {
            $form_submission[$field['name']] = $field['value'];
        }
        
        $form_title = $form_data['settings']['form_title'];
        $this->submit_to_form_bridge($form_submission, 'wpforms_' . sanitize_title($form_title));
    }
    
    /**
     * Handle Gravity Forms submissions
     */
    public function handle_gravity_forms_submission($entry, $form) {
        $form_data = array();
        foreach ($form['fields'] as $field) {
            if (isset($entry[$field->id])) {
                $form_data[$field->label] = $entry[$field->id];
            }
        }
        
        $this->submit_to_form_bridge($form_data, 'gravity_forms_' . sanitize_title($form['title']));
    }
    
    /**
     * Handle Ninja Forms submissions
     */
    public function handle_ninja_forms_submission($form_data) {
        $fields = $form_data['fields'];
        $form_submission = array();
        
        foreach ($fields as $field) {
            if (isset($field['key']) && isset($field['value'])) {
                $form_submission[$field['key']] = $field['value'];
            }
        }
        
        $form_title = isset($form_data['settings']['title']) ? $form_data['settings']['title'] : 'ninja_form';
        $this->submit_to_form_bridge($form_submission, 'ninja_forms_' . sanitize_title($form_title));
    }
    
    /**
     * Handle Formidable Forms submissions
     */
    public function handle_formidable_submission($entry_id, $form_id) {
        if (!class_exists('FrmEntry') || !class_exists('FrmForm') || !class_exists('FrmField')) {
            return;
        }
        
        $entry = FrmEntry::getOne($entry_id);
        $form = FrmForm::getOne($form_id);
        
        if (!$entry || !$form) return;
        
        $form_data = array();
        foreach ($entry->metas as $field_id => $value) {
            $field = FrmField::getOne($field_id);
            if ($field) {
                $form_data[$field->name] = $value;
            }
        }
        
        $this->submit_to_form_bridge($form_data, 'formidable_' . sanitize_title($form->name));
    }
    
    /**
     * Handle Elementor Forms submissions
     */
    public function handle_elementor_submission($record, $handler) {
        $form_data = $record->get('fields');
        $form_name = $record->get_form_settings('form_name') ?: 'elementor_form';
        
        $this->submit_to_form_bridge($form_data, 'elementor_' . sanitize_title($form_name));
    }
    
    /**
     * Handle Fluent Forms submissions
     */
    public function handle_fluent_forms_submission($entryId, $formData, $form) {
        $form_title = $form->title ?: 'fluent_form';
        $this->submit_to_form_bridge($formData, 'fluent_forms_' . sanitize_title($form_title));
    }
    
    /**
     * Handle WordPress comment submissions
     */
    public function handle_comment_submission($comment_id, $comment_approved, $comment_data) {
        if ($comment_approved === 'spam') return;
        
        $form_data = array(
            'comment_author' => $comment_data['comment_author'],
            'comment_author_email' => $comment_data['comment_author_email'],
            'comment_author_url' => $comment_data['comment_author_url'],
            'comment_content' => $comment_data['comment_content'],
            'comment_post_ID' => $comment_data['comment_post_ID'],
            'comment_post_title' => get_the_title($comment_data['comment_post_ID']),
            'comment_approved' => $comment_approved
        );
        
        $this->submit_to_form_bridge($form_data, 'wordpress_comment');
    }
    
    /**
     * Handle WooCommerce order submissions
     */
    public function handle_woocommerce_order($order_id, $posted_data, $order) {
        // Only send if enabled
        if (!get_option('form_bridge_wc_enabled', 0)) {
            return;
        }
        
        $order_data = array(
            'order_id' => $order_id,
            'customer_email' => $order->get_billing_email(),
            'customer_name' => $order->get_billing_first_name() . ' ' . $order->get_billing_last_name(),
            'customer_phone' => $order->get_billing_phone(),
            'total' => $order->get_total(),
            'currency' => $order->get_currency(),
            'status' => $order->get_status(),
            'payment_method' => $order->get_payment_method(),
            'payment_method_title' => $order->get_payment_method_title(),
            'shipping_method' => $order->get_shipping_method(),
            'billing_address' => array(
                'address_1' => $order->get_billing_address_1(),
                'address_2' => $order->get_billing_address_2(),
                'city' => $order->get_billing_city(),
                'state' => $order->get_billing_state(),
                'postcode' => $order->get_billing_postcode(),
                'country' => $order->get_billing_country(),
            ),
            'items' => array()
        );
        
        // Add order items
        foreach ($order->get_items() as $item) {
            $product = $item->get_product();
            $order_data['items'][] = array(
                'name' => $item->get_name(),
                'quantity' => $item->get_quantity(),
                'total' => $item->get_total(),
                'sku' => $product ? $product->get_sku() : '',
                'price' => $product ? $product->get_price() : 0
            );
        }
        
        $this->submit_to_form_bridge($order_data, 'woocommerce_order');
    }
    
    /**
     * Handle user registration
     */
    public function handle_user_registration($user_id) {
        if (!get_option('form_bridge_user_registration', 0)) {
            return;
        }
        
        $user = get_user_by('id', $user_id);
        if (!$user) return;
        
        $user_data = array(
            'user_id' => $user_id,
            'username' => $user->user_login,
            'email' => $user->user_email,
            'display_name' => $user->display_name,
            'roles' => $user->roles,
            'registration_date' => $user->user_registered
        );
        
        $this->submit_to_form_bridge($user_data, 'user_registration');
    }
}

// Initialize the plugin
new FormBridgeConnectorEnhanced();

/**
 * Activation hook
 */
register_activation_hook(__FILE__, function() {
    // Check requirements before activation
    global $wp_version;
    
    if (version_compare($wp_version, FormBridgeConnectorEnhanced::MIN_WP_VERSION, '<')) {
        deactivate_plugins(plugin_basename(__FILE__));
        wp_die(sprintf(
            __('Form-Bridge requires WordPress %s or higher. You are running %s.', 'form-bridge'),
            FormBridgeConnectorEnhanced::MIN_WP_VERSION,
            $wp_version
        ));
    }
    
    if (version_compare(PHP_VERSION, FormBridgeConnectorEnhanced::MIN_PHP_VERSION, '<')) {
        deactivate_plugins(plugin_basename(__FILE__));
        wp_die(sprintf(
            __('Form-Bridge requires PHP %s or higher. You are running %s.', 'form-bridge'),
            FormBridgeConnectorEnhanced::MIN_PHP_VERSION,
            PHP_VERSION
        ));
    }
    
    // Set default options
    if (!get_option('form_bridge_endpoint')) {
        update_option('form_bridge_endpoint', FormBridgeConnectorEnhanced::DEFAULT_ENDPOINT);
    }
    if (!get_option('form_bridge_secret')) {
        update_option('form_bridge_secret', FormBridgeConnectorEnhanced::DEFAULT_SECRET);
    }
    if (!get_option('form_bridge_tenant_id')) {
        update_option('form_bridge_tenant_id', get_bloginfo('name') . '_' . get_current_blog_id());
    }
    
    // Set default settings
    add_option('form_bridge_enabled', 1);
    add_option('form_bridge_log_submissions', 1);
    add_option('form_bridge_timeout', 10);
    add_option('form_bridge_retry_failed', 1);
    add_option('form_bridge_user_registration', 0);
    add_option('form_bridge_wc_enabled', 0);
});

/**
 * Deactivation hook
 */
register_deactivation_hook(__FILE__, function() {
    // Clear scheduled events
    wp_clear_scheduled_hook('form_bridge_retry_failed');
});

/**
 * Uninstall hook
 */
register_uninstall_hook(__FILE__, function() {
    // Remove all plugin options
    delete_option('form_bridge_endpoint');
    delete_option('form_bridge_secret');
    delete_option('form_bridge_tenant_id');
    delete_option('form_bridge_enabled');
    delete_option('form_bridge_log_submissions');
    delete_option('form_bridge_timeout');
    delete_option('form_bridge_retry_failed');
    delete_option('form_bridge_user_registration');
    delete_option('form_bridge_wc_enabled');
    delete_option(FormBridgeConnectorEnhanced::RETRY_QUEUE_OPTION);
    
    // Clear scheduled events
    wp_clear_scheduled_hook('form_bridge_retry_failed');
});

// Convenience functions for developers

/**
 * Send custom data to Form-Bridge
 * 
 * @param array $form_data The form data to send
 * @param string $form_type The type identifier for the form
 * @return array Result array with success status
 */
function form_bridge_submit($form_data, $form_type = 'custom') {
    do_action('form_bridge_submit', $form_data, $form_type);
}

/**
 * Check if Form-Bridge is enabled and configured
 * 
 * @return bool True if enabled and configured
 */
function form_bridge_is_enabled() {
    return get_option('form_bridge_enabled', 1) && 
           get_option('form_bridge_endpoint', '') !== '' &&
           get_option('form_bridge_secret', '') !== '';
}

/**
 * Get Form-Bridge configuration
 * 
 * @return array Configuration array
 */
function form_bridge_get_config() {
    return array(
        'enabled' => get_option('form_bridge_enabled', 1),
        'endpoint' => get_option('form_bridge_endpoint', FormBridgeConnectorEnhanced::DEFAULT_ENDPOINT),
        'tenant_id' => get_option('form_bridge_tenant_id', get_bloginfo('name') . '_' . get_current_blog_id()),
        'timeout' => get_option('form_bridge_timeout', 10),
        'version' => FormBridgeConnectorEnhanced::VERSION
    );
}
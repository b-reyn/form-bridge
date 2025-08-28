<?php
/**
 * Plugin Name: Form-Bridge Connector
 * Plugin URI: https://github.com/your-repo/form-bridge
 * Description: Sends WordPress form submissions to Form-Bridge serverless backend with HMAC authentication.
 * Version: 1.0.0
 * Author: Form-Bridge Team
 * License: MIT
 * Text Domain: form-bridge
 * Domain Path: /languages
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Main Form-Bridge Plugin Class
 */
class FormBridgeConnector {
    
    /**
     * Plugin version
     */
    const VERSION = '1.0.0';
    
    /**
     * Default endpoint URL
     */
    const DEFAULT_ENDPOINT = 'https://xvzokbk6zoiq4ivaihpfmwjitu0qlaaf.lambda-url.us-east-1.on.aws/';
    
    /**
     * Default secret for development
     */
    const DEFAULT_SECRET = 'development-secret-change-in-production';
    
    /**
     * Initialize the plugin
     */
    public function __construct() {
        add_action('init', array($this, 'init'));
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('admin_init', array($this, 'init_settings'));
        
        // Hook into popular form plugins
        $this->init_form_hooks();
        
        // Add AJAX endpoints for testing
        add_action('wp_ajax_test_form_bridge', array($this, 'test_connection'));
        add_action('wp_ajax_nopriv_test_form_bridge', array($this, 'test_connection'));
    }
    
    /**
     * Plugin initialization
     */
    public function init() {
        load_plugin_textdomain('form-bridge', false, dirname(plugin_basename(__FILE__)) . '/languages');
    }
    
    /**
     * Initialize form hooks for popular plugins
     */
    private function init_form_hooks() {
        // Contact Form 7
        if (class_exists('WPCF7_ContactForm')) {
            // Use wpcf7_submit instead of wpcf7_mail_sent to catch all submissions
            add_action('wpcf7_submit', array($this, 'handle_cf7_submission'), 10, 2);
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
        
        // Generic WordPress comments (as form example)
        add_action('comment_post', array($this, 'handle_comment_submission'), 10, 3);
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
    }
    
    /**
     * Admin settings page
     */
    public function admin_page() {
        ?>
        <div class="wrap">
            <h1><?php _e('Form-Bridge Settings', 'form-bridge'); ?></h1>
            
            <div class="notice notice-info">
                <p><strong><?php _e('Form-Bridge Status:', 'form-bridge'); ?></strong> 
                   <span id="fb-status"><?php _e('Testing connection...', 'form-bridge'); ?></span>
                </p>
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
                            <p class="description">
                                <?php _e('The HMAC secret key for request authentication. Change this for production!', 'form-bridge'); ?>
                            </p>
                        </td>
                    </tr>
                    
                    <tr>
                        <th scope="row"><?php _e('Tenant ID', 'form-bridge'); ?></th>
                        <td>
                            <input type="text" name="form_bridge_tenant_id" 
                                   value="<?php echo esc_attr(get_option('form_bridge_tenant_id', get_bloginfo('name') . '_' . get_current_blog_id())); ?>" 
                                   class="regular-text" />
                            <p class="description">
                                <?php _e('Unique identifier for this WordPress site. Used for data organization.', 'form-bridge'); ?>
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
                        <th scope="row"><?php _e('Log Submissions', 'form-bridge'); ?></th>
                        <td>
                            <label>
                                <input type="checkbox" name="form_bridge_log_submissions" value="1" 
                                       <?php checked(get_option('form_bridge_log_submissions', 1)); ?> />
                                <?php _e('Log form submissions to WordPress error log for debugging', 'form-bridge'); ?>
                            </label>
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
            
            <h2><?php _e('Supported Form Plugins', 'form-bridge'); ?></h2>
            <ul>
                <li><?php echo class_exists('WPCF7_ContactForm') ? '✅' : '❌'; ?> Contact Form 7</li>
                <li><?php echo class_exists('WPForms') ? '✅' : '❌'; ?> WPForms</li>
                <li><?php echo class_exists('GFForms') ? '✅' : '❌'; ?> Gravity Forms</li>
                <li><?php echo class_exists('Ninja_Forms') ? '✅' : '❌'; ?> Ninja Forms</li>
                <li><?php echo class_exists('FrmHooksController') ? '✅' : '❌'; ?> Formidable Forms</li>
                <li>✅ WordPress Comments</li>
            </ul>
        </div>
        
        <script type="text/javascript">
        jQuery(document).ready(function($) {
            // Test connection on page load
            testConnection();
            
            $('#test-connection').click(function() {
                testConnection();
            });
            
            function testConnection() {
                $('#test-results').html('<div class="notice notice-info"><p><?php _e("Testing connection...", "form-bridge"); ?></p></div>');
                $('#fb-status').text('<?php _e("Testing...", "form-bridge"); ?>');
                
                $.ajax({
                    url: ajaxurl,
                    type: 'POST',
                    data: {
                        action: 'test_form_bridge',
                        nonce: '<?php echo wp_create_nonce("test_form_bridge"); ?>'
                    },
                    success: function(response) {
                        if (response.success) {
                            $('#test-results').html('<div class="notice notice-success"><p><strong><?php _e("✅ Connection successful!", "form-bridge"); ?></strong><br>Submission ID: ' + response.data.submission_id + '</p></div>');
                            $('#fb-status').html('<span style="color: green;">✅ <?php _e("Connected", "form-bridge"); ?></span>');
                        } else {
                            $('#test-results').html('<div class="notice notice-error"><p><strong><?php _e("❌ Connection failed:", "form-bridge"); ?></strong><br>' + response.data + '</p></div>');
                            $('#fb-status').html('<span style="color: red;">❌ <?php _e("Connection failed", "form-bridge"); ?></span>');
                        }
                    },
                    error: function() {
                        $('#test-results').html('<div class="notice notice-error"><p><?php _e("❌ AJAX request failed", "form-bridge"); ?></p></div>');
                        $('#fb-status').html('<span style="color: red;">❌ <?php _e("AJAX failed", "form-bridge"); ?></span>');
                    }
                });
            }
        });
        </script>
        <?php
    }
    
    /**
     * Test Form-Bridge connection via AJAX
     */
    public function test_connection() {
        if (!wp_verify_nonce($_POST['nonce'], 'test_form_bridge')) {
            wp_die(__('Security check failed', 'form-bridge'));
        }
        
        $test_data = array(
            'test' => true,
            'plugin_version' => self::VERSION,
            'wordpress_version' => get_bloginfo('version'),
            'site_url' => get_site_url(),
            'timestamp' => current_time('mysql')
        );
        
        $result = $this->submit_to_form_bridge($test_data, 'plugin_test');
        
        if ($result['success']) {
            wp_send_json_success($result);
        } else {
            wp_send_json_error($result['error']);
        }
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
        
        // Prepare payload
        $payload_data = array(
            'form_data' => $form_data,
            'form_type' => $form_type,
            'tenant_id' => $tenant_id,
            'site_info' => array(
                'site_url' => get_site_url(),
                'site_name' => get_bloginfo('name'),
                'wp_version' => get_bloginfo('version'),
                'plugin_version' => self::VERSION
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
            'headers' => array(
                'Content-Type' => 'application/json',
                'X-Signature' => $signature,
                'X-Timestamp' => $timestamp,
                'User-Agent' => 'Form-Bridge-WordPress/' . self::VERSION
            ),
            'body' => $payload
        );
        
        // Send request
        $response = wp_remote_post($endpoint, $args);
        
        // Handle response
        if (is_wp_error($response)) {
            $error = 'HTTP Error: ' . $response->get_error_message();
            $this->log_submission($form_data, $form_type, false, $error);
            return array('success' => false, 'error' => $error);
        }
        
        $status_code = wp_remote_retrieve_response_code($response);
        $response_body = wp_remote_retrieve_body($response);
        
        if ($status_code !== 200) {
            $error = 'HTTP ' . $status_code . ': ' . $response_body;
            $this->log_submission($form_data, $form_type, false, $error);
            return array('success' => false, 'error' => $error);
        }
        
        $result = json_decode($response_body, true);
        
        if ($result && isset($result['success']) && $result['success']) {
            $this->log_submission($form_data, $form_type, true, $result);
            return $result;
        } else {
            $error = 'Invalid response: ' . $response_body;
            $this->log_submission($form_data, $form_type, false, $error);
            return array('success' => false, 'error' => $error);
        }
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
     * Handle Contact Form 7 submissions
     */
    public function handle_cf7_submission($contact_form, $result = null) {
        $submission = WPCF7_Submission::get_instance();
        if (!$submission) return;
        
        $form_data = $submission->get_posted_data();
        $form_title = $contact_form->title();
        
        // Add submission status info
        if ($result) {
            $form_data['_cf7_status'] = $result['status'];
            $form_data['_cf7_message'] = isset($result['message']) ? $result['message'] : '';
        }
        
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
}

// Initialize the plugin
new FormBridgeConnector();

/**
 * Activation hook function
 */
function form_bridge_activate() {
    // Set default options
    if (!get_option('form_bridge_endpoint')) {
        update_option('form_bridge_endpoint', FormBridgeConnector::DEFAULT_ENDPOINT);
    }
    if (!get_option('form_bridge_secret')) {
        update_option('form_bridge_secret', FormBridgeConnector::DEFAULT_SECRET);
    }
    if (!get_option('form_bridge_tenant_id')) {
        update_option('form_bridge_tenant_id', get_bloginfo('name') . '_' . get_current_blog_id());
    }
    update_option('form_bridge_enabled', 1);
    update_option('form_bridge_log_submissions', 1);
    update_option('form_bridge_timeout', 10);
}
register_activation_hook(__FILE__, 'form_bridge_activate');

/**
 * Deactivation hook
 */
function form_bridge_deactivate() {
    // Clean up if needed (currently nothing to clean)
}
register_deactivation_hook(__FILE__, 'form_bridge_deactivate');

/**
 * Uninstall hook function
 */
function form_bridge_uninstall() {
    // Remove all plugin options
    delete_option('form_bridge_endpoint');
    delete_option('form_bridge_secret');
    delete_option('form_bridge_tenant_id');
    delete_option('form_bridge_enabled');
    delete_option('form_bridge_log_submissions');
    delete_option('form_bridge_timeout');
}
register_uninstall_hook(__FILE__, 'form_bridge_uninstall');
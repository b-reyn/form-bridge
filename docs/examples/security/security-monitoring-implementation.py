"""
Form-Bridge Security Monitoring Implementation
Comprehensive security monitoring with CloudWatch, Lambda functions, and automation
"""

import json
import boto3
import hashlib
import hmac
from datetime import datetime, timedelta
from collections import defaultdict
import ipaddress
import re

# CloudWatch and AWS clients
cloudwatch = boto3.client('cloudwatch')
logs_client = boto3.client('logs')
events_client = boto3.client('events')
sns = boto3.client('sns')
secrets_manager = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')

# ============================================================================
# SECURITY EVENT PROCESSORS
# ============================================================================

def security_event_processor(event, context):
    """
    Main security event processor Lambda function
    Analyzes incoming security events and triggers appropriate responses
    """
    
    try:
        # Parse incoming event
        security_event = json.loads(event['Records'][0]['body']) if 'Records' in event else event
        
        # Initialize processors
        auth_processor = AuthenticationProcessor()
        anomaly_detector = AnomalyDetector()
        threat_correlator = ThreatCorrelator()
        
        # Process based on event type
        event_type = security_event.get('event_type')
        
        if event_type == 'authentication_failure':
            alerts = auth_processor.process_auth_failure(security_event)
        elif event_type == 'unusual_access_pattern':
            alerts = anomaly_detector.detect_access_anomalies(security_event)
        elif event_type == 'update_failure':
            alerts = anomaly_detector.detect_update_anomalies(security_event)
        else:
            alerts = []
            
        # Correlate with recent events to reduce false positives
        correlated_alerts = threat_correlator.correlate_threats(alerts, security_event)
        
        # Process alerts
        for alert in correlated_alerts:
            process_security_alert(alert)
            
        # Log structured event for compliance
        log_security_event(security_event, alerts)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed_events': 1,
                'alerts_generated': len(correlated_alerts),
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error processing security event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


class AuthenticationProcessor:
    """Processes authentication-related security events"""
    
    def __init__(self):
        self.failure_threshold = 10  # failures per 5 minutes
        self.time_window = timedelta(minutes=5)
        self.geo_anomaly_threshold = 2  # countries in 1 hour
        self.ip_reputation_cache = {}
        
    def process_auth_failure(self, event):
        """Process authentication failure for threat detection"""
        alerts = []
        
        tenant_id = event.get('tenant_id')
        ip_address = event.get('ip_address')
        timestamp = datetime.fromisoformat(event.get('timestamp'))
        
        # Check for brute force attacks
        brute_force_alerts = self.detect_brute_force(ip_address, tenant_id, timestamp)
        alerts.extend(brute_force_alerts)
        
        # Check for credential stuffing
        credential_stuffing_alerts = self.detect_credential_stuffing(ip_address, timestamp)
        alerts.extend(credential_stuffing_alerts)
        
        # Check for geographic anomalies
        geo_alerts = self.detect_geographic_anomalies(ip_address, tenant_id, timestamp)
        alerts.extend(geo_alerts)
        
        return alerts
        
    def detect_brute_force(self, ip_address, tenant_id, timestamp):
        """Detect brute force attacks from IP or against tenant"""
        alerts = []
        
        # Query recent failures from this IP
        ip_failures = self.get_recent_failures_by_ip(ip_address, self.time_window)
        
        if ip_failures >= self.failure_threshold:
            alerts.append({
                'type': 'brute_force_by_ip',
                'severity': 'CRITICAL',
                'ip_address': ip_address,
                'failure_count': ip_failures,
                'time_window': str(self.time_window),
                'recommended_action': 'temporary_ip_ban',
                'confidence_score': min(1.0, ip_failures / (self.failure_threshold * 3))
            })
            
        # Check failures against specific tenant
        tenant_failures = self.get_recent_failures_by_tenant(tenant_id, self.time_window)
        
        if tenant_failures >= self.failure_threshold * 2:  # Higher threshold for tenant
            alerts.append({
                'type': 'brute_force_against_tenant', 
                'severity': 'HIGH',
                'tenant_id': tenant_id,
                'failure_count': tenant_failures,
                'recommended_action': 'investigate_tenant_security',
                'confidence_score': min(1.0, tenant_failures / (self.failure_threshold * 6))
            })
            
        return alerts
        
    def detect_credential_stuffing(self, ip_address, timestamp):
        """Detect credential stuffing across multiple tenants"""
        # Get recent failures from this IP across all tenants
        recent_failures = self.get_recent_cross_tenant_failures(ip_address, timedelta(minutes=15))
        
        unique_tenants = len(set(failure['tenant_id'] for failure in recent_failures))
        
        if unique_tenants >= 5:  # Same IP attacking 5+ tenants
            return [{
                'type': 'credential_stuffing',
                'severity': 'CRITICAL',
                'ip_address': ip_address,
                'affected_tenants': unique_tenants,
                'total_attempts': len(recent_failures),
                'recommended_action': 'block_ip_globally',
                'confidence_score': min(1.0, unique_tenants / 10.0)
            }]
            
        return []
        
    def detect_geographic_anomalies(self, ip_address, tenant_id, timestamp):
        """Detect geographic anomalies in access patterns"""
        # Get IP geolocation
        geo_info = self.get_ip_geolocation(ip_address)
        
        # Get recent locations for this tenant
        recent_locations = self.get_recent_tenant_locations(tenant_id, timedelta(hours=1))
        
        current_country = geo_info.get('country')
        recent_countries = set(loc['country'] for loc in recent_locations)
        
        # Alert if accessing from new country within short time
        if current_country not in recent_countries and len(recent_countries) > 0:
            return [{
                'type': 'geographic_anomaly',
                'severity': 'HIGH',
                'tenant_id': tenant_id,
                'ip_address': ip_address,
                'current_country': current_country,
                'previous_countries': list(recent_countries),
                'recommended_action': 'verify_legitimate_user',
                'confidence_score': 0.8 if len(recent_countries) > 0 else 0.5
            }]
            
        return []
        
    def get_recent_failures_by_ip(self, ip_address, time_window):
        """Query CloudWatch Logs for recent authentication failures by IP"""
        end_time = datetime.utcnow()
        start_time = end_time - time_window
        
        query = f'''
        fields @timestamp
        | filter event_type = "authentication_failure" and ip_address = "{ip_address}"
        | filter @timestamp >= {int(start_time.timestamp() * 1000)}
        | stats count() as failure_count
        '''
        
        try:
            response = logs_client.start_query(
                logGroupName='/aws/lambda/form-bridge-security',
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )
            
            # Wait for query completion and get results
            query_id = response['queryId']
            result = self.wait_for_query_completion(query_id)
            
            if result and len(result) > 0:
                return int(result[0].get('failure_count', 0))
                
        except Exception as e:
            print(f"Error querying authentication failures: {str(e)}")
            
        return 0
        
    def get_ip_geolocation(self, ip_address):
        """Get geographic information for IP address"""
        # In production, use a geolocation service like MaxMind or AWS location service
        # For demo purposes, return mock data based on IP ranges
        
        if ip_address.startswith('192.168.') or ip_address.startswith('10.'):
            return {'country': 'US', 'region': 'Internal', 'city': 'Local'}
            
        # Mock geolocation data
        return {
            'country': 'US',
            'region': 'California', 
            'city': 'San Francisco',
            'latitude': 37.7749,
            'longitude': -122.4194
        }


class AnomalyDetector:
    """Detects various security anomalies in system behavior"""
    
    def __init__(self):
        self.baseline_window = timedelta(days=7)
        self.anomaly_threshold = 3.0  # Standard deviations from baseline
        
    def detect_access_anomalies(self, event):
        """Detect unusual access patterns that may indicate compromise"""
        alerts = []
        
        tenant_id = event.get('tenant_id')
        
        # Get baseline metrics for this tenant
        baseline = self.get_baseline_metrics(tenant_id)
        current = self.get_current_metrics(tenant_id, timedelta(hours=1))
        
        # Volume anomaly detection
        if current.get('submission_rate', 0) > baseline.get('avg_submission_rate', 0) + (self.anomaly_threshold * baseline.get('std_submission_rate', 0)):
            alerts.append({
                'type': 'volume_anomaly',
                'severity': 'MEDIUM',
                'tenant_id': tenant_id,
                'current_rate': current['submission_rate'],
                'baseline_rate': baseline['avg_submission_rate'],
                'recommended_action': 'investigate_unusual_traffic',
                'confidence_score': 0.7
            })
            
        # Form diversity anomaly
        baseline_forms = set(baseline.get('common_form_ids', []))
        current_forms = set(current.get('form_ids', []))
        new_forms = current_forms - baseline_forms
        
        if len(new_forms) > 2:
            alerts.append({
                'type': 'new_form_usage',
                'severity': 'MEDIUM',
                'tenant_id': tenant_id,
                'new_forms': list(new_forms),
                'recommended_action': 'verify_form_legitimacy',
                'confidence_score': min(1.0, len(new_forms) / 5.0)
            })
            
        # Payload size anomaly
        current_payload_size = current.get('avg_payload_size', 0)
        baseline_payload_size = baseline.get('avg_payload_size', 0)
        
        if current_payload_size > baseline_payload_size * 2 and baseline_payload_size > 0:
            alerts.append({
                'type': 'payload_size_anomaly',
                'severity': 'HIGH',
                'tenant_id': tenant_id,
                'current_size': current_payload_size,
                'baseline_size': baseline_payload_size,
                'recommended_action': 'inspect_payload_content',
                'confidence_score': 0.9
            })
            
        return alerts
        
    def detect_update_anomalies(self, event):
        """Detect potential tampering with update mechanism"""
        alerts = []
        
        # Check update source legitimacy
        if event.get('source') != 'official_update_server':
            alerts.append({
                'type': 'unofficial_update_source',
                'severity': 'CRITICAL',
                'tenant_id': event.get('tenant_id'),
                'source': event.get('source'),
                'recommended_action': 'block_update_and_investigate',
                'confidence_score': 1.0
            })
            
        # Check update frequency
        tenant_id = event.get('tenant_id')
        last_update = self.get_last_update_time(tenant_id)
        
        if last_update:
            time_since_last = datetime.utcnow() - last_update
            if time_since_last < timedelta(hours=1):  # Too frequent
                alerts.append({
                    'type': 'frequent_update_anomaly',
                    'severity': 'HIGH',
                    'tenant_id': tenant_id,
                    'time_since_last': str(time_since_last),
                    'recommended_action': 'verify_update_legitimacy',
                    'confidence_score': 0.8
                })
                
        return alerts
        
    def get_baseline_metrics(self, tenant_id):
        """Get baseline metrics for anomaly detection"""
        # Query CloudWatch or DynamoDB for historical metrics
        # For demo, return mock baseline data
        return {
            'avg_submission_rate': 10.0,  # submissions per hour
            'std_submission_rate': 3.0,
            'common_form_ids': ['contact', 'newsletter', 'feedback'],
            'avg_payload_size': 1024  # bytes
        }
        
    def get_current_metrics(self, tenant_id, time_window):
        """Get current metrics for comparison"""
        # Query recent submissions for this tenant
        # For demo, return mock current data
        return {
            'submission_rate': 8.0,
            'form_ids': ['contact', 'newsletter'],
            'avg_payload_size': 900
        }


class ThreatCorrelator:
    """Correlates threats across multiple signals to reduce false positives"""
    
    def __init__(self):
        self.correlation_window = timedelta(minutes=10)
        self.whitelist_ips = self.load_ip_whitelist()
        
    def correlate_threats(self, alerts, original_event):
        """Correlate threats and filter false positives"""
        correlated_alerts = []
        
        for alert in alerts:
            # Check IP whitelist
            if alert.get('ip_address') in self.whitelist_ips:
                continue
                
            # Check if pattern matches known legitimate behavior
            if self.is_likely_false_positive(alert, original_event):
                continue
                
            # Enhance alert with correlation data
            enhanced_alert = self.enhance_alert_context(alert, original_event)
            correlated_alerts.append(enhanced_alert)
            
        return correlated_alerts
        
    def is_likely_false_positive(self, alert, original_event):
        """Determine if alert is likely a false positive"""
        
        # During maintenance windows
        if self.is_maintenance_window():
            return True
            
        # Known administrative IPs
        if alert.get('ip_address') in self.get_admin_ips():
            return True
            
        # Low confidence score
        if alert.get('confidence_score', 1.0) < 0.3:
            return True
            
        return False
        
    def enhance_alert_context(self, alert, original_event):
        """Add contextual information to alerts"""
        enhanced = alert.copy()
        
        # Add timestamp
        enhanced['detected_at'] = datetime.utcnow().isoformat()
        
        # Add related events
        related_events = self.find_related_events(alert, self.correlation_window)
        enhanced['related_event_count'] = len(related_events)
        
        # Adjust confidence based on correlation
        if len(related_events) > 1:
            enhanced['confidence_score'] = min(1.0, enhanced.get('confidence_score', 0.5) + 0.2)
            
        return enhanced
        
    def load_ip_whitelist(self):
        """Load whitelisted IP addresses"""
        return [
            '203.0.113.0/24',  # Administrative network
            '192.0.2.0/24'     # Development network
        ]


# ============================================================================
# CLOUDWATCH CONFIGURATIONS
# ============================================================================

def setup_security_monitoring_infrastructure():
    """Set up CloudWatch dashboards, alarms, and log groups"""
    
    # Create log groups
    create_security_log_groups()
    
    # Create security dashboard
    create_security_dashboard()
    
    # Set up security alarms
    create_security_alarms()
    
    # Create custom metrics
    setup_security_metrics()


def create_security_log_groups():
    """Create CloudWatch log groups for security events"""
    log_groups = [
        '/aws/lambda/form-bridge-security-processor',
        '/aws/lambda/form-bridge-auth-failures',
        '/aws/lambda/form-bridge-incident-response',
        '/formbridge/security/audit-trail',
        '/formbridge/security/threat-intelligence'
    ]
    
    for log_group in log_groups:
        try:
            logs_client.create_log_group(
                logGroupName=log_group,
                retentionInDays=90  # 90 days retention for security logs
            )
            print(f"Created log group: {log_group}")
        except logs_client.exceptions.ResourceAlreadyExistsException:
            print(f"Log group already exists: {log_group}")
        except Exception as e:
            print(f"Error creating log group {log_group}: {str(e)}")


def create_security_dashboard():
    """Create comprehensive security monitoring dashboard"""
    
    dashboard_body = {
        "widgets": [
            {
                "type": "metric",
                "x": 0, "y": 0, "width": 12, "height": 6,
                "properties": {
                    "metrics": [
                        ["FormBridge/Security", "AuthenticationSuccess", {"stat": "Sum"}],
                        [".", "AuthenticationFailure", {"stat": "Sum"}],
                        [".", "AuthenticationFailureRate", {"stat": "Average"}]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1",
                    "title": "Authentication Health",
                    "period": 300,
                    "yAxis": {"left": {"min": 0}},
                    "annotations": {
                        "horizontal": [
                            {"label": "5% Failure Threshold", "value": 5}
                        ]
                    }
                }
            },
            {
                "type": "log",
                "x": 0, "y": 6, "width": 12, "height": 6,
                "properties": {
                    "query": "SOURCE '/aws/lambda/form-bridge-security-processor'\n| filter event_type = \"authentication_failure\"\n| stats count() as failures by ip_address\n| sort failures desc\n| limit 10",
                    "region": "us-east-1",
                    "title": "Top Failed Authentication IPs",
                    "view": "table",
                    "stacked": False
                }
            },
            {
                "type": "metric",
                "x": 12, "y": 0, "width": 12, "height": 6,
                "properties": {
                    "metrics": [
                        ["FormBridge/Security", "ThreatDetectionRate", "ThreatType", "brute_force"],
                        ["...", "credential_stuffing"],
                        ["...", "geographic_anomaly"],
                        ["...", "payload_anomaly"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": "us-east-1",
                    "title": "Threat Detection by Type",
                    "period": 300
                }
            },
            {
                "type": "log",
                "x": 12, "y": 6, "width": 12, "height": 6,
                "properties": {
                    "query": "SOURCE '/formbridge/security/audit-trail'\n| filter severity in [\"CRITICAL\", \"HIGH\"]\n| stats count() as threat_count by user_context.geographic_location.country\n| sort threat_count desc\n| limit 10",
                    "region": "us-east-1",
                    "title": "Geographic Threat Distribution",
                    "view": "table"
                }
            }
        ]
    }
    
    try:
        cloudwatch.put_dashboard(
            DashboardName='FormBridge-Security-Operations',
            DashboardBody=json.dumps(dashboard_body)
        )
        print("Security dashboard created successfully")
    except Exception as e:
        print(f"Error creating security dashboard: {str(e)}")


def create_security_alarms():
    """Create CloudWatch alarms for security monitoring"""
    
    alarms = [
        {
            'AlarmName': 'FormBridge-HighAuthenticationFailureRate',
            'ComparisonOperator': 'GreaterThanThreshold',
            'EvaluationPeriods': 2,
            'MetricName': 'AuthenticationFailureRate',
            'Namespace': 'FormBridge/Security',
            'Period': 300,
            'Statistic': 'Average',
            'Threshold': 10.0,
            'ActionsEnabled': True,
            'AlarmActions': [
                'arn:aws:sns:us-east-1:123456789012:security-alerts-high'
            ],
            'AlarmDescription': 'High authentication failure rate detected',
            'TreatMissingData': 'breaching'
        },
        {
            'AlarmName': 'FormBridge-CriticalSecurityEvent',
            'ComparisonOperator': 'GreaterThanThreshold',
            'EvaluationPeriods': 1,
            'MetricName': 'CriticalAlerts',
            'Namespace': 'FormBridge/Security',
            'Period': 60,
            'Statistic': 'Sum',
            'Threshold': 0.0,
            'ActionsEnabled': True,
            'AlarmActions': [
                'arn:aws:sns:us-east-1:123456789012:security-alerts-critical'
            ],
            'AlarmDescription': 'Critical security event requiring immediate attention',
            'TreatMissingData': 'notBreaching'
        },
        {
            'AlarmName': 'FormBridge-UnusualVolumeSpike',
            'ComparisonOperator': 'GreaterThanThreshold',
            'EvaluationPeriods': 3,
            'MetricName': 'SubmissionVolumeAnomaly',
            'Namespace': 'FormBridge/Security',
            'Period': 300,
            'Statistic': 'Maximum',
            'Threshold': 3.0,  # 3 standard deviations
            'ActionsEnabled': True,
            'AlarmActions': [
                'arn:aws:sns:us-east-1:123456789012:security-alerts-medium'
            ],
            'AlarmDescription': 'Unusual submission volume spike detected'
        }
    ]
    
    for alarm in alarms:
        try:
            cloudwatch.put_metric_alarm(**alarm)
            print(f"Created alarm: {alarm['AlarmName']}")
        except Exception as e:
            print(f"Error creating alarm {alarm['AlarmName']}: {str(e)}")


def setup_security_metrics():
    """Set up custom CloudWatch metrics for security monitoring"""
    
    # Publish initial metrics to establish namespace
    initial_metrics = [
        {
            'MetricName': 'AuthenticationSuccess',
            'Value': 0,
            'Unit': 'Count'
        },
        {
            'MetricName': 'AuthenticationFailure', 
            'Value': 0,
            'Unit': 'Count'
        },
        {
            'MetricName': 'ThreatDetectionRate',
            'Value': 0,
            'Unit': 'Count/Second',
            'Dimensions': [
                {'Name': 'ThreatType', 'Value': 'brute_force'}
            ]
        }
    ]
    
    try:
        cloudwatch.put_metric_data(
            Namespace='FormBridge/Security',
            MetricData=initial_metrics
        )
        print("Security metrics namespace initialized")
    except Exception as e:
        print(f"Error initializing security metrics: {str(e)}")


# ============================================================================
# INCIDENT RESPONSE AUTOMATION
# ============================================================================

def incident_response_handler(event, context):
    """Lambda function for automated incident response"""
    
    try:
        # Parse the security alert
        alert = json.loads(event['Records'][0]['Sns']['Message']) if 'Records' in event else event
        
        responder = SecurityIncidentResponder()
        response_actions = responder.handle_security_incident(alert)
        
        # Log response actions
        log_incident_response(alert, response_actions)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'alert_processed': True,
                'actions_taken': len(response_actions),
                'response_summary': response_actions
            })
        }
        
    except Exception as e:
        print(f"Error in incident response: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


class SecurityIncidentResponder:
    """Handles automated security incident response"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.secrets = boto3.client('secretsmanager')
        
    def handle_security_incident(self, alert):
        """Route incident to appropriate response handler"""
        
        alert_type = alert.get('type')
        severity = alert.get('severity')
        
        response_actions = []
        
        if severity == 'CRITICAL':
            response_actions.extend(self.handle_critical_incident(alert))
        elif severity == 'HIGH':
            response_actions.extend(self.handle_high_severity_incident(alert))
        elif severity == 'MEDIUM':
            response_actions.extend(self.handle_medium_severity_incident(alert))
            
        return response_actions
        
    def handle_critical_incident(self, alert):
        """Handle critical security incidents with immediate response"""
        actions = []
        
        alert_type = alert.get('type')
        
        if alert_type == 'brute_force_by_ip':
            actions.extend([
                self.temporary_ip_ban(alert.get('ip_address'), 3600),  # 1 hour ban
                self.enhance_monitoring_for_ip(alert.get('ip_address')),
                self.send_critical_alert(alert)
            ])
            
        elif alert_type == 'credential_stuffing':
            actions.extend([
                self.global_ip_ban(alert.get('ip_address'), 86400),  # 24 hour ban
                self.enhance_monitoring_for_affected_tenants(alert.get('affected_tenants')),
                self.send_critical_alert(alert)
            ])
            
        elif alert_type == 'compromised_tenant':
            actions.extend([
                self.isolate_tenant(alert.get('tenant_id')),
                self.revoke_tenant_keys(alert.get('tenant_id')),
                self.create_forensic_snapshot(alert.get('tenant_id')),
                self.escalate_to_security_team(alert)
            ])
            
        return actions
        
    def temporary_ip_ban(self, ip_address, duration_seconds):
        """Implement temporary IP ban"""
        try:
            # Add IP to ban list in DynamoDB
            ban_table = self.dynamodb.Table('IPBanList')
            
            ban_table.put_item(
                Item={
                    'ip_address': ip_address,
                    'banned_at': datetime.utcnow().isoformat(),
                    'ban_duration': duration_seconds,
                    'ttl': int((datetime.utcnow() + timedelta(seconds=duration_seconds)).timestamp()),
                    'reason': 'automated_security_response'
                }
            )
            
            return {
                'action': 'temporary_ip_ban',
                'ip_address': ip_address,
                'duration': duration_seconds,
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'action': 'temporary_ip_ban',
                'ip_address': ip_address,
                'status': 'failed',
                'error': str(e)
            }
            
    def isolate_tenant(self, tenant_id):
        """Isolate tenant by disabling API access"""
        try:
            # Add to isolation table
            isolation_table = self.dynamodb.Table('TenantIsolation')
            
            isolation_table.put_item(
                Item={
                    'tenant_id': tenant_id,
                    'isolated_at': datetime.utcnow().isoformat(),
                    'isolation_reason': 'security_incident',
                    'ttl': int((datetime.utcnow() + timedelta(hours=4)).timestamp())
                }
            )
            
            return {
                'action': 'tenant_isolation',
                'tenant_id': tenant_id,
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'action': 'tenant_isolation',
                'tenant_id': tenant_id,
                'status': 'failed',
                'error': str(e)
            }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def publish_security_metric(metric_name, value, unit='Count', dimensions=None):
    """Publish custom security metric to CloudWatch"""
    
    metric_data = {
        'MetricName': metric_name,
        'Value': value,
        'Unit': unit,
        'Timestamp': datetime.utcnow()
    }
    
    if dimensions:
        metric_data['Dimensions'] = dimensions
        
    try:
        cloudwatch.put_metric_data(
            Namespace='FormBridge/Security',
            MetricData=[metric_data]
        )
    except Exception as e:
        print(f"Error publishing metric {metric_name}: {str(e)}")


def log_security_event(event, alerts):
    """Log security event with structured format for compliance"""
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_id': event.get('event_id', 'unknown'),
        'event_type': event.get('event_type'),
        'tenant_id': event.get('tenant_id'),
        'severity': determine_event_severity(event, alerts),
        'source_ip': event.get('ip_address'),
        'user_agent': event.get('user_agent'),
        'geographic_context': get_geographic_context(event.get('ip_address')),
        'alerts_generated': len(alerts),
        'alert_types': [alert.get('type') for alert in alerts]
    }
    
    # Remove PII for compliance
    sanitized_entry = sanitize_log_entry(log_entry)
    
    print(json.dumps(sanitized_entry))


def determine_event_severity(event, alerts):
    """Determine overall severity based on event and generated alerts"""
    if any(alert.get('severity') == 'CRITICAL' for alert in alerts):
        return 'CRITICAL'
    elif any(alert.get('severity') == 'HIGH' for alert in alerts):
        return 'HIGH'
    elif any(alert.get('severity') == 'MEDIUM' for alert in alerts):
        return 'MEDIUM'
    else:
        return 'LOW'


def sanitize_log_entry(log_entry):
    """Remove PII from log entries for GDPR compliance"""
    sanitized = log_entry.copy()
    
    # Hash IP address for correlation while preserving privacy
    if 'source_ip' in sanitized and sanitized['source_ip']:
        sanitized['source_ip_hash'] = hashlib.sha256(
            sanitized['source_ip'].encode()
        ).hexdigest()[:16]
        # Keep first two octets for network analysis
        ip_parts = sanitized['source_ip'].split('.')
        if len(ip_parts) == 4:
            sanitized['source_ip_network'] = f"{ip_parts[0]}.{ip_parts[1]}.x.x"
        del sanitized['source_ip']
        
    return sanitized


def get_geographic_context(ip_address):
    """Get geographic context for IP address"""
    if not ip_address:
        return None
        
    # In production, use actual geolocation service
    return {
        'country': 'US',
        'region': 'California',
        'city': 'San Francisco'
    }


# ============================================================================
# COST OPTIMIZATION FUNCTIONS
# ============================================================================

def optimize_log_retention():
    """Optimize log retention policies for cost management"""
    
    retention_policies = {
        '/aws/lambda/form-bridge-security-processor': 90,  # 90 days for security
        '/aws/lambda/form-bridge-auth-failures': 90,
        '/aws/lambda/form-bridge-incident-response': 365,  # 1 year for incidents
        '/formbridge/security/audit-trail': 2555,  # 7 years for compliance
        '/formbridge/security/threat-intelligence': 30  # 30 days for threat intel
    }
    
    for log_group, retention_days in retention_policies.items():
        try:
            logs_client.put_retention_policy(
                logGroupName=log_group,
                retentionInDays=retention_days
            )
            print(f"Set retention for {log_group}: {retention_days} days")
        except Exception as e:
            print(f"Error setting retention for {log_group}: {str(e)}")


def implement_intelligent_sampling():
    """Implement intelligent log sampling to reduce costs"""
    
    # Sample configuration based on event importance
    sampling_rates = {
        'authentication_success': 0.1,  # Sample 10% of successful auth
        'authentication_failure': 1.0,  # Log all failures
        'security_alert': 1.0,  # Log all alerts
        'normal_submission': 0.05,  # Sample 5% of normal submissions
        'suspicious_activity': 1.0,  # Log all suspicious activity
        'compliance_event': 1.0  # Log all compliance events
    }
    
    return sampling_rates


if __name__ == "__main__":
    # Set up security monitoring infrastructure
    setup_security_monitoring_infrastructure()
    print("Security monitoring infrastructure setup complete")
    
    # Optimize for cost management
    optimize_log_retention()
    print("Log retention optimization complete")
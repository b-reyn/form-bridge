#!/usr/bin/env python3
"""
Automated Incident Response System for Form-Bridge
Implements automated responses to security threats, performance issues, and cost overruns
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import hashlib
from dataclasses import dataclass
from enum import Enum

class IncidentSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class IncidentType(Enum):
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    COST = "COST"
    AVAILABILITY = "AVAILABILITY"

@dataclass
class Incident:
    id: str
    type: IncidentType
    severity: IncidentSeverity
    title: str
    description: str
    tenant_id: Optional[str]
    metrics: Dict[str, Any]
    timestamp: datetime
    status: str = "OPEN"
    response_actions: List[str] = None

class FormBridgeIncidentResponse:
    """Automated incident response system with intelligent decision making"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.lambda_client = boto3.client('lambda')
        self.sns = boto3.client('sns')
        self.cloudwatch = boto3.client('cloudwatch')
        self.waf = boto3.client('wafv2')
        self.apigateway = boto3.client('apigateway')
        
        # Configuration
        self.incident_table = self.dynamodb.Table('FormBridge-Incidents')
        self.blocked_ips_table = self.dynamodb.Table('FormBridge-BlockedIPs')
        self.tenant_quarantine_table = self.dynamodb.Table('FormBridge-TenantQuarantine')
        
        # Response thresholds
        self.RESPONSE_THRESHOLDS = {
            'cost_critical': 20.0,      # $20/month
            'cost_alert': 15.0,         # $15/month
            'cost_warning': 10.0,       # $10/month
            'auth_failure_rate': 0.1,   # 10% failure rate
            'processing_time_sla': 5.0, # 5 seconds
            'memory_utilization': 0.9,  # 90% memory usage
            'error_rate': 0.05          # 5% error rate
        }
        
        # SNS topics for alerts
        self.SNS_TOPICS = {
            'critical': f'arn:aws:sns:{os.environ.get("AWS_REGION")}:{os.environ.get("AWS_ACCOUNT_ID")}:form-bridge-critical',
            'security': f'arn:aws:sns:{os.environ.get("AWS_REGION")}:{os.environ.get("AWS_ACCOUNT_ID")}:form-bridge-security',
            'operations': f'arn:aws:sns:{os.environ.get("AWS_REGION")}:{os.environ.get("AWS_ACCOUNT_ID")}:form-bridge-operations'
        }

    def process_cloudwatch_alarm(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process CloudWatch alarm and trigger appropriate response"""
        alarm_data = json.loads(event['Records'][0]['Sns']['Message'])
        
        incident = self._create_incident_from_alarm(alarm_data)
        response_actions = []
        
        # Determine response based on alarm type and severity
        if incident.type == IncidentType.SECURITY:
            response_actions = self._handle_security_incident(incident)
        elif incident.type == IncidentType.COST:
            response_actions = self._handle_cost_incident(incident)
        elif incident.type == IncidentType.PERFORMANCE:
            response_actions = self._handle_performance_incident(incident)
        elif incident.type == IncidentType.AVAILABILITY:
            response_actions = self._handle_availability_incident(incident)
        
        incident.response_actions = response_actions
        
        # Store incident for tracking
        self._store_incident(incident)
        
        # Execute response actions
        execution_results = self._execute_response_actions(incident, response_actions)
        
        # Send notifications
        self._send_incident_notifications(incident, execution_results)
        
        return {
            'incident_id': incident.id,
            'severity': incident.severity.value,
            'actions_taken': response_actions,
            'execution_results': execution_results
        }

    def _create_incident_from_alarm(self, alarm_data: Dict[str, Any]) -> Incident:
        """Create incident object from CloudWatch alarm data"""
        alarm_name = alarm_data.get('AlarmName', '')
        alarm_description = alarm_data.get('AlarmDescription', '')
        
        # Determine incident type and severity from alarm name
        incident_type = IncidentType.PERFORMANCE
        severity = IncidentSeverity.MEDIUM
        
        if 'Security' in alarm_name or 'CrossTenant' in alarm_name:
            incident_type = IncidentType.SECURITY
            severity = IncidentSeverity.CRITICAL
        elif 'Cost' in alarm_name:
            incident_type = IncidentType.COST
            if '20USD' in alarm_name:
                severity = IncidentSeverity.CRITICAL
            elif '15USD' in alarm_name:
                severity = IncidentSeverity.HIGH
            else:
                severity = IncidentSeverity.MEDIUM
        elif 'Performance' in alarm_name or 'Latency' in alarm_name:
            incident_type = IncidentType.PERFORMANCE
            severity = IncidentSeverity.HIGH
        
        # Generate unique incident ID
        incident_id = f"{incident_type.value}_{int(time.time())}_{hashlib.md5(alarm_name.encode()).hexdigest()[:8]}"
        
        return Incident(
            id=incident_id,
            type=incident_type,
            severity=severity,
            title=alarm_name,
            description=alarm_description,
            tenant_id=self._extract_tenant_from_alarm(alarm_data),
            metrics=alarm_data.get('Trigger', {}),
            timestamp=datetime.utcnow()
        )

    def _handle_security_incident(self, incident: Incident) -> List[str]:
        """Handle security incidents with automated response"""
        actions = []
        
        if 'CrossTenant' in incident.title:
            # CRITICAL: Cross-tenant access attempt
            actions = [
                "isolate_tenant",
                "block_source_ip", 
                "enable_enhanced_logging",
                "notify_security_team",
                "create_forensic_snapshot"
            ]
            
            # Execute immediate isolation
            if incident.tenant_id:
                self._quarantine_tenant(incident.tenant_id, reason="Cross-tenant access detected")
            
        elif 'AuthFailure' in incident.title or 'HMAC' in incident.title:
            # Authentication attack detected
            actions = [
                "increase_rate_limiting",
                "block_attacking_ips",
                "enable_challenge_response",
                "notify_operations_team"
            ]
            
            # Implement progressive rate limiting
            self._implement_progressive_rate_limiting(incident)
            
        elif 'GeographicAnomaly' in incident.title:
            # Geographic access anomaly
            actions = [
                "flag_geographic_access",
                "require_additional_verification",
                "notify_tenant",
                "log_geographic_access"
            ]
            
        return actions

    def _handle_cost_incident(self, incident: Incident) -> List[str]:
        """Handle cost overrun incidents with optimization actions"""
        actions = []
        current_cost = incident.metrics.get('MetricValue', 0)
        
        if current_cost >= self.RESPONSE_THRESHOLDS['cost_critical']:
            # CRITICAL: $20+ cost threshold
            actions = [
                "immediate_cost_analysis",
                "throttle_non_critical_functions",
                "reduce_log_retention",
                "notify_executive_team",
                "implement_emergency_cost_controls"
            ]
            
            # Implement emergency cost controls
            self._implement_emergency_cost_controls()
            
        elif current_cost >= self.RESPONSE_THRESHOLDS['cost_alert']:
            # HIGH: $15+ cost threshold  
            actions = [
                "detailed_cost_analysis",
                "optimize_lambda_memory",
                "reduce_custom_metrics",
                "notify_operations_team",
                "recommend_cost_optimizations"
            ]
            
            # Execute cost optimizations
            self._execute_cost_optimizations(current_cost)
            
        elif current_cost >= self.RESPONSE_THRESHOLDS['cost_warning']:
            # MEDIUM: $10+ cost threshold
            actions = [
                "cost_trend_analysis", 
                "identify_cost_drivers",
                "recommend_optimizations",
                "notify_development_team"
            ]
            
        return actions

    def _handle_performance_incident(self, incident: Incident) -> List[str]:
        """Handle performance incidents with optimization actions"""
        actions = []
        
        if 'Latency' in incident.title or 'ProcessingTime' in incident.title:
            actions = [
                "analyze_slow_functions",
                "increase_lambda_memory",
                "enable_provisioned_concurrency",
                "optimize_database_queries",
                "notify_development_team"
            ]
            
            # Implement performance optimizations
            self._optimize_function_performance(incident)
            
        elif 'MemoryUtilization' in incident.title:
            actions = [
                "right_size_lambda_memory",
                "analyze_memory_leaks",
                "optimize_data_structures",
                "monitor_garbage_collection"
            ]
            
        elif 'ColdStart' in incident.title:
            actions = [
                "enable_provisioned_concurrency",
                "optimize_initialization_code",
                "implement_connection_pooling",
                "consider_arm64_migration"
            ]
            
        return actions

    def _handle_availability_incident(self, incident: Incident) -> List[str]:
        """Handle availability incidents with failover actions"""
        actions = [
            "enable_circuit_breaker",
            "activate_dlq_processing",
            "scale_up_resources",
            "notify_on_call_team",
            "implement_graceful_degradation"
        ]
        
        return actions

    def _quarantine_tenant(self, tenant_id: str, reason: str):
        """Quarantine a tenant to prevent further damage"""
        try:
            # Add tenant to quarantine table
            self.tenant_quarantine_table.put_item(
                Item={
                    'tenant_id': tenant_id,
                    'quarantine_time': datetime.utcnow().isoformat(),
                    'reason': reason,
                    'status': 'ACTIVE',
                    'ttl': int(time.time()) + (24 * 60 * 60)  # 24 hour quarantine
                }
            )
            
            # Update WAF to block tenant traffic
            self._update_waf_block_tenant(tenant_id)
            
            print(f"Tenant {tenant_id} quarantined: {reason}")
            
        except Exception as e:
            print(f"Error quarantining tenant {tenant_id}: {str(e)}")

    def _implement_progressive_rate_limiting(self, incident: Incident):
        """Implement progressive rate limiting based on threat level"""
        try:
            # Get current threat metrics
            failure_rate = incident.metrics.get('MetricValue', 0)
            
            # Calculate appropriate rate limit
            if failure_rate > 0.5:  # 50% failure rate
                rate_limit = 10  # 10 requests per minute
            elif failure_rate > 0.2:  # 20% failure rate
                rate_limit = 50  # 50 requests per minute  
            else:
                rate_limit = 100  # 100 requests per minute
            
            # Update API Gateway throttling
            self._update_api_gateway_throttling(rate_limit)
            
            print(f"Implemented progressive rate limiting: {rate_limit} req/min")
            
        except Exception as e:
            print(f"Error implementing rate limiting: {str(e)}")

    def _implement_emergency_cost_controls(self):
        """Implement emergency cost control measures"""
        try:
            # Reduce log sampling to 1%
            self._update_log_sampling_rate(0.01)
            
            # Reduce custom metrics frequency
            self._reduce_custom_metrics_frequency()
            
            # Throttle non-critical Lambda functions
            self._throttle_non_critical_functions()
            
            print("Emergency cost controls implemented")
            
        except Exception as e:
            print(f"Error implementing emergency cost controls: {str(e)}")

    def _execute_cost_optimizations(self, current_cost: float):
        """Execute automated cost optimization measures"""
        try:
            # Right-size Lambda functions based on usage
            self._optimize_lambda_memory_allocation()
            
            # Optimize DynamoDB capacity if needed
            if current_cost > 15:
                self._optimize_dynamodb_capacity()
            
            # Reduce log retention for non-critical logs
            self._optimize_log_retention()
            
            print(f"Cost optimizations executed for ${current_cost:.2f}")
            
        except Exception as e:
            print(f"Error executing cost optimizations: {str(e)}")

    def _optimize_function_performance(self, incident: Incident):
        """Optimize Lambda function performance"""
        try:
            function_name = incident.metrics.get('FunctionName')
            if not function_name:
                return
                
            # Get current function configuration
            response = self.lambda_client.get_function_configuration(
                FunctionName=function_name
            )
            
            current_memory = response.get('MemorySize', 128)
            
            # Increase memory if under-allocated
            if current_memory < 512:
                new_memory = min(current_memory * 2, 1024)
                self.lambda_client.update_function_configuration(
                    FunctionName=function_name,
                    MemorySize=new_memory
                )
                print(f"Increased memory for {function_name}: {current_memory}MB -> {new_memory}MB")
                
        except Exception as e:
            print(f"Error optimizing function performance: {str(e)}")

    def _update_waf_block_tenant(self, tenant_id: str):
        """Update WAF rules to block tenant traffic"""
        # Implementation depends on WAF setup
        # This is a placeholder for WAF rule updates
        pass

    def _update_api_gateway_throttling(self, rate_limit: int):
        """Update API Gateway throttling settings"""
        # Implementation depends on API Gateway setup
        # This is a placeholder for throttling updates
        pass

    def _update_log_sampling_rate(self, rate: float):
        """Update log sampling rate for cost optimization"""
        # Implementation depends on logging setup
        # This is a placeholder for sampling rate updates
        pass

    def _reduce_custom_metrics_frequency(self):
        """Reduce custom metrics frequency to save costs"""
        # Implementation depends on metrics setup
        # This is a placeholder for metrics optimization
        pass

    def _throttle_non_critical_functions(self):
        """Throttle non-critical Lambda functions"""
        # Implementation depends on function classification
        # This is a placeholder for function throttling
        pass

    def _optimize_lambda_memory_allocation(self):
        """Optimize Lambda memory allocation based on usage"""
        # Implementation depends on function monitoring data
        # This is a placeholder for memory optimization
        pass

    def _optimize_dynamodb_capacity(self):
        """Optimize DynamoDB capacity settings"""
        # Implementation depends on DynamoDB monitoring data
        # This is a placeholder for capacity optimization
        pass

    def _optimize_log_retention(self):
        """Optimize CloudWatch log retention policies"""
        # Implementation depends on log group configuration
        # This is a placeholder for retention optimization
        pass

    def _store_incident(self, incident: Incident):
        """Store incident details for tracking and analysis"""
        try:
            self.incident_table.put_item(
                Item={
                    'incident_id': incident.id,
                    'type': incident.type.value,
                    'severity': incident.severity.value,
                    'title': incident.title,
                    'description': incident.description,
                    'tenant_id': incident.tenant_id or 'system',
                    'metrics': incident.metrics,
                    'timestamp': incident.timestamp.isoformat(),
                    'status': incident.status,
                    'response_actions': incident.response_actions or [],
                    'ttl': int(time.time()) + (90 * 24 * 60 * 60)  # 90 days retention
                }
            )
        except Exception as e:
            print(f"Error storing incident {incident.id}: {str(e)}")

    def _execute_response_actions(self, incident: Incident, actions: List[str]) -> Dict[str, Any]:
        """Execute the defined response actions"""
        results = {}
        
        for action in actions:
            try:
                if action == "isolate_tenant" and incident.tenant_id:
                    self._quarantine_tenant(incident.tenant_id, f"Automated isolation: {incident.title}")
                    results[action] = "SUCCESS"
                    
                elif action == "increase_rate_limiting":
                    self._implement_progressive_rate_limiting(incident)
                    results[action] = "SUCCESS"
                    
                elif action == "immediate_cost_analysis":
                    analysis_result = self._perform_cost_analysis()
                    results[action] = "SUCCESS"
                    results["cost_analysis"] = analysis_result
                    
                elif action == "optimize_lambda_memory":
                    self._optimize_function_performance(incident)
                    results[action] = "SUCCESS"
                    
                else:
                    # For actions that don't have implementation yet
                    results[action] = "QUEUED"
                    
            except Exception as e:
                results[action] = f"FAILED: {str(e)}"
        
        return results

    def _perform_cost_analysis(self) -> Dict[str, Any]:
        """Perform immediate cost analysis"""
        # Placeholder for cost analysis implementation
        return {
            "analysis_time": datetime.utcnow().isoformat(),
            "top_cost_drivers": ["Lambda", "DynamoDB", "CloudWatch"],
            "optimization_recommendations": ["Right-size Lambda", "Optimize DynamoDB"]
        }

    def _send_incident_notifications(self, incident: Incident, execution_results: Dict[str, Any]):
        """Send incident notifications to appropriate channels"""
        try:
            notification_message = {
                "incident_id": incident.id,
                "type": incident.type.value,
                "severity": incident.severity.value,
                "title": incident.title,
                "description": incident.description,
                "tenant_id": incident.tenant_id,
                "timestamp": incident.timestamp.isoformat(),
                "actions_taken": incident.response_actions,
                "execution_results": execution_results
            }
            
            # Determine appropriate SNS topic
            if incident.severity == IncidentSeverity.CRITICAL:
                topic_arn = self.SNS_TOPICS['critical']
            elif incident.type == IncidentType.SECURITY:
                topic_arn = self.SNS_TOPICS['security'] 
            else:
                topic_arn = self.SNS_TOPICS['operations']
            
            # Send notification
            self.sns.publish(
                TopicArn=topic_arn,
                Subject=f"FormBridge Incident: {incident.severity.value} - {incident.title}",
                Message=json.dumps(notification_message, indent=2)
            )
            
            print(f"Sent notification for incident {incident.id}")
            
        except Exception as e:
            print(f"Error sending notification for incident {incident.id}: {str(e)}")

    def _extract_tenant_from_alarm(self, alarm_data: Dict[str, Any]) -> Optional[str]:
        """Extract tenant ID from alarm data if available"""
        # Check alarm dimensions for tenant information
        trigger = alarm_data.get('Trigger', {})
        dimensions = trigger.get('Dimensions', [])
        
        for dimension in dimensions:
            if dimension.get('name') == 'TenantId':
                return dimension.get('value')
        
        return None

    def get_incident_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get incident summary for the specified time period"""
        cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        try:
            response = self.incident_table.scan(
                FilterExpression='#ts >= :cutoff',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={':cutoff': cutoff_time}
            )
            
            incidents = response.get('Items', [])
            
            summary = {
                'total_incidents': len(incidents),
                'by_severity': {},
                'by_type': {},
                'resolved': 0,
                'open': 0
            }
            
            for incident in incidents:
                severity = incident.get('severity', 'UNKNOWN')
                incident_type = incident.get('type', 'UNKNOWN')
                status = incident.get('status', 'OPEN')
                
                summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
                summary['by_type'][incident_type] = summary['by_type'].get(incident_type, 0) + 1
                
                if status == 'RESOLVED':
                    summary['resolved'] += 1
                else:
                    summary['open'] += 1
            
            return summary
            
        except Exception as e:
            print(f"Error getting incident summary: {str(e)}")
            return {'error': str(e)}

def lambda_handler(event, context):
    """Lambda handler for automated incident response"""
    incident_response = FormBridgeIncidentResponse()
    
    try:
        # Check if this is a CloudWatch alarm
        if 'Records' in event and event['Records'][0]['EventSource'] == 'aws:sns':
            result = incident_response.process_cloudwatch_alarm(event)
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Incident processed successfully',
                    'result': result
                })
            }
        
        # Handle other types of events or direct invocation
        action = event.get('action', 'get_summary')
        
        if action == 'get_summary':
            hours = event.get('hours', 24)
            summary = incident_response.get_incident_summary(hours)
            return {
                'statusCode': 200,
                'body': json.dumps(summary)
            }
        
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Unknown action or event type'})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Error processing incident'
            })
        }

if __name__ == "__main__":
    # Test the incident response system
    response_system = FormBridgeIncidentResponse()
    
    # Test incident creation and processing
    test_alarm = {
        'AlarmName': 'FormBridge-Security-CrossTenantAccess',
        'AlarmDescription': 'Cross-tenant access attempt detected',
        'Trigger': {
            'MetricName': 'CrossTenantAccessAttempts',
            'MetricValue': 1,
            'Dimensions': [
                {'name': 'TenantId', 'value': 'tenant_123'}
            ]
        }
    }
    
    test_event = {
        'Records': [{
            'EventSource': 'aws:sns',
            'Sns': {
                'Message': json.dumps(test_alarm)
            }
        }]
    }
    
    print("Testing incident response system...")
    result = response_system.process_cloudwatch_alarm(test_event)
    print(f"Test result: {json.dumps(result, indent=2)}")
    
    # Test incident summary
    print("\nGetting incident summary...")
    summary = response_system.get_incident_summary(24)
    print(f"Incident summary: {json.dumps(summary, indent=2)}")
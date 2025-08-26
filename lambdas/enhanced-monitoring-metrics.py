#!/usr/bin/env python3
"""
Enhanced Monitoring Metrics for Form-Bridge Multi-Tenant Architecture
Implements custom CloudWatch metrics with cost optimization and 2025 best practices
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
import hashlib
import random

class FormBridgeMetricsPublisher:
    """Advanced metrics publisher with intelligent sampling and cost optimization"""
    
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
        self.xray_recorder = None
        
        # Initialize X-Ray if available
        try:
            from aws_xray_sdk.core import xray_recorder
            self.xray_recorder = xray_recorder
        except ImportError:
            print("X-Ray SDK not available - tracing disabled")
            
        # Cost optimization settings
        self.MAX_METRICS_PER_BATCH = 20  # CloudWatch limit
        self.SAMPLING_RATES = {
            'security': 1.0,      # 100% - never sample security events
            'business': 0.5,      # 50% - high value business metrics
            'performance': 0.3,   # 30% - performance monitoring  
            'debug': 0.1          # 10% - debug information
        }
        
        # Metric namespaces for organization
        self.NAMESPACES = {
            'security': 'FormBridge/Security',
            'performance': 'FormBridge/Performance', 
            'cost': 'FormBridge/Costs',
            'business': 'FormBridge/Business',
            'eventbridge': 'FormBridge/EventBridge',
            'lambda': 'FormBridge/Lambda',
            'dynamodb': 'FormBridge/DynamoDB'
        }

    def should_sample_metric(self, metric_category: str, tenant_id: str = None) -> bool:
        """Intelligent sampling based on category and tenant activity"""
        base_rate = self.SAMPLING_RATES.get(metric_category, 0.1)
        
        # Always sample security events
        if metric_category == 'security':
            return True
            
        # Increase sampling for high-activity tenants
        if tenant_id and self._is_high_activity_tenant(tenant_id):
            base_rate = min(base_rate * 2, 1.0)
            
        return random.random() < base_rate

    def _is_high_activity_tenant(self, tenant_id: str) -> bool:
        """Check if tenant is high-activity (simplified implementation)"""
        # Hash tenant ID for consistent but pseudo-random distribution
        tenant_hash = int(hashlib.md5(tenant_id.encode()).hexdigest()[:8], 16)
        return (tenant_hash % 100) < 20  # 20% of tenants considered "high activity"

    def publish_security_metrics(self, tenant_id: str, event_type: str, metrics: Dict[str, Any]):
        """Publish security-related metrics with full sampling"""
        if not self.should_sample_metric('security', tenant_id):
            return
            
        metric_data = []
        timestamp = datetime.utcnow()
        
        # Cross-tenant access attempts (CRITICAL)
        if event_type == 'cross_tenant_access':
            metric_data.append({
                'MetricName': 'CrossTenantAccessAttempts',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'EventType', 'Value': event_type},
                    {'Name': 'Environment', 'Value': os.environ.get('ENVIRONMENT', 'dev')}
                ]
            })
        
        # Authentication failures
        if event_type == 'hmac_validation_failure':
            metric_data.append({
                'MetricName': 'AuthenticationFailures',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'FailureType', 'Value': 'HMAC_Validation'}
                ]
            })
            
        # Rate limiting effectiveness
        if event_type == 'rate_limit_triggered':
            for layer, blocked_count in metrics.get('blocked_requests', {}).items():
                metric_data.append({
                    'MetricName': 'RateLimitBlocked',
                    'Value': blocked_count,
                    'Unit': 'Count',
                    'Timestamp': timestamp,
                    'Dimensions': [
                        {'Name': 'TenantId', 'Value': tenant_id},
                        {'Name': 'Layer', 'Value': layer}  # WAF, APIGateway, Lambda, DynamoDB
                    ]
                })
        
        self._publish_metrics(self.NAMESPACES['security'], metric_data)

    def publish_eventbridge_metrics(self, tenant_id: str, event_bus: str, metrics: Dict[str, Any]):
        """Publish EventBridge-specific metrics with enhanced 2025 capabilities"""
        if not self.should_sample_metric('performance', tenant_id):
            return
            
        metric_data = []
        timestamp = datetime.utcnow()
        
        # Event publishing metrics
        if 'events_published' in metrics:
            metric_data.append({
                'MetricName': 'EventsPublished',
                'Value': metrics['events_published'],
                'Unit': 'Count',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'EventBus', 'Value': event_bus}
                ]
            })
        
        # Event processing latency
        if 'processing_latency_ms' in metrics:
            metric_data.append({
                'MetricName': 'EventProcessingLatency',
                'Value': metrics['processing_latency_ms'],
                'Unit': 'Milliseconds',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'EventBus', 'Value': event_bus}
                ]
            })
        
        # Rule match efficiency
        if 'rule_matches' in metrics and 'total_events' in metrics:
            match_rate = metrics['rule_matches'] / max(metrics['total_events'], 1)
            metric_data.append({
                'MetricName': 'RuleMatchEfficiency',
                'Value': match_rate,
                'Unit': 'Percent',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'EventBus', 'Value': event_bus}
                ]
            })
        
        # Dead letter queue depth
        if 'dlq_depth' in metrics:
            metric_data.append({
                'MetricName': 'DeadLetterQueueDepth',
                'Value': metrics['dlq_depth'],
                'Unit': 'Count',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'EventBus', 'Value': event_bus}
                ]
            })
        
        self._publish_metrics(self.NAMESPACES['eventbridge'], metric_data)

    def publish_lambda_performance_metrics(self, function_name: str, tenant_id: str, metrics: Dict[str, Any]):
        """Publish Lambda performance metrics with ARM64 optimization tracking"""
        if not self.should_sample_metric('performance', tenant_id):
            return
            
        metric_data = []
        timestamp = datetime.utcnow()
        architecture = metrics.get('architecture', 'x86_64')
        
        # Cold start tracking
        if 'cold_start_duration_ms' in metrics:
            metric_data.append({
                'MetricName': 'ColdStartDuration',
                'Value': metrics['cold_start_duration_ms'],
                'Unit': 'Milliseconds',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'FunctionName', 'Value': function_name},
                    {'Name': 'Architecture', 'Value': architecture},
                    {'Name': 'TenantId', 'Value': tenant_id}
                ]
            })
        
        # Memory utilization efficiency
        if 'max_memory_used' in metrics and 'allocated_memory' in metrics:
            utilization = metrics['max_memory_used'] / metrics['allocated_memory']
            metric_data.append({
                'MetricName': 'MemoryUtilization',
                'Value': utilization,
                'Unit': 'Percent',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'FunctionName', 'Value': function_name},
                    {'Name': 'Architecture', 'Value': architecture}
                ]
            })
        
        # ARM64 cost savings tracking
        if architecture == 'arm64' and 'execution_cost' in metrics:
            # Estimated x86 cost (20% higher)
            estimated_x86_cost = metrics['execution_cost'] * 1.2
            savings = estimated_x86_cost - metrics['execution_cost']
            
            metric_data.append({
                'MetricName': 'ARM64CostSavings',
                'Value': savings,
                'Unit': 'None',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'FunctionName', 'Value': function_name},
                    {'Name': 'TenantId', 'Value': tenant_id}
                ]
            })
        
        # Performance regression detection
        if 'baseline_duration_ms' in metrics and 'current_duration_ms' in metrics:
            regression_ratio = metrics['current_duration_ms'] / max(metrics['baseline_duration_ms'], 1)
            if regression_ratio > 1.2:  # 20% performance degradation
                metric_data.append({
                    'MetricName': 'PerformanceRegression',
                    'Value': regression_ratio,
                    'Unit': 'None',
                    'Timestamp': timestamp,
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': function_name},
                        {'Name': 'Architecture', 'Value': architecture}
                    ]
                })
        
        self._publish_metrics(self.NAMESPACES['lambda'], metric_data)

    def publish_cost_metrics(self, tenant_id: str, service: str, cost_data: Dict[str, Any]):
        """Publish cost-related metrics for real-time cost monitoring"""
        # Cost metrics are always published (no sampling)
        metric_data = []
        timestamp = datetime.utcnow()
        
        # Service-specific costs
        if 'estimated_cost' in cost_data:
            metric_data.append({
                'MetricName': 'EstimatedServiceCost',
                'Value': cost_data['estimated_cost'],
                'Unit': 'None',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'Service', 'Value': service}
                ]
            })
        
        # Usage metrics for cost calculation
        if 'resource_usage' in cost_data:
            for resource, usage in cost_data['resource_usage'].items():
                metric_data.append({
                    'MetricName': f'{resource}Usage',
                    'Value': usage,
                    'Unit': 'Count',
                    'Timestamp': timestamp,
                    'Dimensions': [
                        {'Name': 'TenantId', 'Value': tenant_id},
                        {'Name': 'Service', 'Value': service},
                        {'Name': 'Resource', 'Value': resource}
                    ]
                })
        
        # Cost optimization opportunities
        if 'optimization_potential' in cost_data:
            metric_data.append({
                'MetricName': 'CostOptimizationPotential',
                'Value': cost_data['optimization_potential'],
                'Unit': 'None',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'Service', 'Value': service}
                ]
            })
        
        self._publish_metrics(self.NAMESPACES['cost'], metric_data)

    def publish_business_metrics(self, tenant_id: str, metrics: Dict[str, Any]):
        """Publish business KPI metrics"""
        if not self.should_sample_metric('business', tenant_id):
            return
            
        metric_data = []
        timestamp = datetime.utcnow()
        
        # Form submission volume
        if 'submissions_count' in metrics:
            metric_data.append({
                'MetricName': 'FormSubmissions',
                'Value': metrics['submissions_count'],
                'Unit': 'Count',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id},
                    {'Name': 'FormType', 'Value': metrics.get('form_type', 'Unknown')}
                ]
            })
        
        # Delivery success rate
        if 'successful_deliveries' in metrics and 'total_deliveries' in metrics:
            success_rate = metrics['successful_deliveries'] / max(metrics['total_deliveries'], 1)
            metric_data.append({
                'MetricName': 'DeliverySuccessRate',
                'Value': success_rate,
                'Unit': 'Percent',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id}
                ]
            })
        
        # Processing time (SLA monitoring)
        if 'processing_time_seconds' in metrics:
            metric_data.append({
                'MetricName': 'ProcessingTime',
                'Value': metrics['processing_time_seconds'],
                'Unit': 'Seconds',
                'Timestamp': timestamp,
                'Dimensions': [
                    {'Name': 'TenantId', 'Value': tenant_id}
                ]
            })
        
        self._publish_metrics(self.NAMESPACES['business'], metric_data)

    def _publish_metrics(self, namespace: str, metric_data: List[Dict[str, Any]]):
        """Publish metrics to CloudWatch with batching and error handling"""
        if not metric_data:
            return
            
        try:
            # Add X-Ray tracing if available
            if self.xray_recorder:
                with self.xray_recorder.in_subsegment('publish_cloudwatch_metrics'):
                    self.xray_recorder.put_annotation('namespace', namespace)
                    self.xray_recorder.put_annotation('metric_count', len(metric_data))
                    self._batch_publish_metrics(namespace, metric_data)
            else:
                self._batch_publish_metrics(namespace, metric_data)
                
        except Exception as e:
            print(f"Error publishing metrics to {namespace}: {str(e)}")
            # Don't fail the main application flow due to metrics errors
            
    def _batch_publish_metrics(self, namespace: str, metric_data: List[Dict[str, Any]]):
        """Publish metrics in batches to respect CloudWatch limits"""
        for i in range(0, len(metric_data), self.MAX_METRICS_PER_BATCH):
            batch = metric_data[i:i + self.MAX_METRICS_PER_BATCH]
            
            try:
                self.cloudwatch.put_metric_data(
                    Namespace=namespace,
                    MetricData=batch
                )
                
                # Small delay to avoid throttling
                if len(metric_data) > self.MAX_METRICS_PER_BATCH:
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Error publishing metric batch to {namespace}: {str(e)}")

    def create_composite_alarm(self, alarm_name: str, alarm_rule: str, description: str):
        """Create composite alarm to reduce alarm count and costs"""
        try:
            self.cloudwatch.put_composite_alarm(
                AlarmName=alarm_name,
                AlarmRule=alarm_rule,
                AlarmDescription=description,
                ActionsEnabled=True,
                AlarmActions=[
                    f'arn:aws:sns:{os.environ.get("AWS_REGION", "us-east-1")}:'
                    f'{os.environ.get("AWS_ACCOUNT_ID", "123456789012")}:form-bridge-alerts'
                ]
            )
        except Exception as e:
            print(f"Error creating composite alarm {alarm_name}: {str(e)}")

# Usage example and Lambda handler
def lambda_handler(event, context):
    """Example Lambda handler with comprehensive metrics"""
    metrics_publisher = FormBridgeMetricsPublisher()
    
    # Extract tenant information
    tenant_id = event.get('tenant_id', 'unknown')
    start_time = time.time()
    
    try:
        # Your business logic here
        process_form_submission(event)
        
        # Publish business metrics
        metrics_publisher.publish_business_metrics(tenant_id, {
            'submissions_count': 1,
            'form_type': event.get('form_type', 'contact'),
            'processing_time_seconds': time.time() - start_time
        })
        
        # Publish performance metrics
        metrics_publisher.publish_lambda_performance_metrics(
            context.function_name,
            tenant_id,
            {
                'architecture': 'arm64',
                'max_memory_used': context.memory_limit_in_mb * 0.7,  # Simulated
                'allocated_memory': context.memory_limit_in_mb,
                'execution_cost': 0.0001  # Simulated
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'success'})
        }
        
    except Exception as e:
        # Publish error metrics
        metrics_publisher.publish_security_metrics(tenant_id, 'processing_error', {
            'error_type': type(e).__name__,
            'error_message': str(e)
        })
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def process_form_submission(event):
    """Placeholder for business logic"""
    pass

# Metric definitions for dashboard creation
METRIC_DEFINITIONS = {
    'security_dashboard': {
        'cross_tenant_access': 'FormBridge/Security.CrossTenantAccessAttempts',
        'auth_failures': 'FormBridge/Security.AuthenticationFailures',
        'rate_limit_blocks': 'FormBridge/Security.RateLimitBlocked'
    },
    'performance_dashboard': {
        'event_processing_latency': 'FormBridge/EventBridge.EventProcessingLatency',
        'lambda_cold_starts': 'FormBridge/Lambda.ColdStartDuration',
        'memory_utilization': 'FormBridge/Lambda.MemoryUtilization'
    },
    'cost_dashboard': {
        'monthly_costs': 'FormBridge/Costs.EstimatedServiceCost',
        'arm64_savings': 'FormBridge/Lambda.ARM64CostSavings',
        'optimization_potential': 'FormBridge/Costs.CostOptimizationPotential'
    },
    'business_dashboard': {
        'form_submissions': 'FormBridge/Business.FormSubmissions',
        'delivery_success_rate': 'FormBridge/Business.DeliverySuccessRate',
        'processing_time': 'FormBridge/Business.ProcessingTime'
    }
}

if __name__ == "__main__":
    # Test the metrics publisher
    publisher = FormBridgeMetricsPublisher()
    
    # Test security metrics
    publisher.publish_security_metrics(
        'tenant_123',
        'hmac_validation_failure',
        {'source_ip': '1.2.3.4'}
    )
    
    print("Metrics publisher test completed")
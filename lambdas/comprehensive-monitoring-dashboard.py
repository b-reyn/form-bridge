#!/usr/bin/env python3
"""
Comprehensive Monitoring Dashboard for Form-Bridge
Creates and manages CloudWatch dashboards with security, performance, and cost monitoring
"""

import boto3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os

class FormBridgeDashboardManager:
    """Creates and manages comprehensive monitoring dashboards"""
    
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.account_id = os.environ.get('AWS_ACCOUNT_ID', '123456789012')
        
        # Dashboard configurations
        self.DASHBOARD_CONFIGS = {
            'security': self._get_security_dashboard_config(),
            'performance': self._get_performance_dashboard_config(),
            'cost': self._get_cost_dashboard_config(),
            'business': self._get_business_dashboard_config(),
            'executive': self._get_executive_dashboard_config()
        }

    def create_all_dashboards(self):
        """Create all monitoring dashboards"""
        results = {}
        
        for dashboard_name, config in self.DASHBOARD_CONFIGS.items():
            try:
                dashboard_body = json.dumps(config)
                
                response = self.cloudwatch.put_dashboard(
                    DashboardName=f'FormBridge-{dashboard_name.title()}',
                    DashboardBody=dashboard_body
                )
                
                results[dashboard_name] = {
                    'success': True,
                    'dashboard_arn': response.get('DashboardArn')
                }
                
                print(f"Created {dashboard_name} dashboard successfully")
                
            except Exception as e:
                results[dashboard_name] = {
                    'success': False,
                    'error': str(e)
                }
                print(f"Error creating {dashboard_name} dashboard: {str(e)}")
        
        return results

    def _get_security_dashboard_config(self) -> Dict[str, Any]:
        """Security monitoring dashboard configuration"""
        return {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Security Threats Overview",
                        "metrics": [
                            ["FormBridge/Security", "CrossTenantAccessAttempts"],
                            [".", "AuthenticationFailures"],
                            [".", "RateLimitBlocked"],
                            [".", "GeographicAnomalies"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": self.region,
                        "yAxis": {
                            "left": {"min": 0}
                        },
                        "annotations": {
                            "horizontal": [
                                {"label": "Critical Threshold", "value": 10}
                            ]
                        }
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Multi-Tenant Isolation Health",
                        "metrics": [
                            ["FormBridge/Security", "CrossTenantAccessAttempts", {"stat": "Sum"}],
                            [".", "TenantIsolationViolations", {"stat": "Sum"}],
                            [".", "UnauthorizedDataAccess", {"stat": "Sum"}]
                        ],
                        "period": 300,
                        "region": self.region,
                        "yAxis": {"left": {"min": 0}},
                        "view": "timeSeries",
                        "stacked": False,
                        "title": "Tenant Isolation Violations (Should be Zero)"
                    }
                },
                {
                    "type": "log",
                    "x": 0, "y": 6,
                    "width": 24, "height": 6,
                    "properties": {
                        "title": "Security Event Analysis",
                        "query": "SOURCE '/aws/lambda/form-bridge' | fields @timestamp, tenant_id, event_type, ip_address\n| filter event_type like /security/\n| stats count() by tenant_id, event_type\n| sort count desc\n| limit 20",
                        "region": self.region,
                        "view": "table"
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 12,
                    "width": 8, "height": 6,
                    "properties": {
                        "title": "Authentication Success Rate",
                        "metrics": [
                            ["FormBridge/Security", "AuthenticationSuccess"],
                            [".", "AuthenticationFailures"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": self.region,
                        "view": "pie"
                    }
                },
                {
                    "type": "metric",
                    "x": 8, "y": 12,
                    "width": 8, "height": 6,
                    "properties": {
                        "title": "Rate Limiting Effectiveness",
                        "metrics": [
                            ["FormBridge/Security", "RateLimitBlocked", "Layer", "WAF"],
                            [".", ".", "Layer", "APIGateway"],
                            [".", ".", "Layer", "Lambda"],
                            [".", ".", "Layer", "DynamoDB"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": self.region,
                        "view": "singleValue"
                    }
                },
                {
                    "type": "metric",
                    "x": 16, "y": 12,
                    "width": 8, "height": 6,
                    "properties": {
                        "title": "Geographic Access Patterns",
                        "metrics": [
                            ["FormBridge/Security", "GeographicAnomalies", {"stat": "Sum"}]
                        ],
                        "period": 3600,
                        "region": self.region,
                        "view": "timeSeries",
                        "yAxis": {"left": {"min": 0}}
                    }
                }
            ]
        }

    def _get_performance_dashboard_config(self) -> Dict[str, Any]:
        """Performance monitoring dashboard configuration"""
        return {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "API Response Times (p50, p90, p99)",
                        "metrics": [
                            ["AWS/Lambda", "Duration", "FunctionName", "form-bridge-ingestion", {"stat": "p50"}],
                            [".", ".", ".", ".", {"stat": "p90"}],
                            [".", ".", ".", ".", {"stat": "p99"}]
                        ],
                        "period": 300,
                        "region": self.region,
                        "yAxis": {"left": {"min": 0, "max": 5000}},
                        "annotations": {
                            "horizontal": [
                                {"label": "SLA Target (200ms)", "value": 200},
                                {"label": "Alert Threshold (1s)", "value": 1000}
                            ]
                        }
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "ARM64 Lambda Performance",
                        "metrics": [
                            ["FormBridge/Lambda", "ColdStartDuration", "Architecture", "arm64"],
                            [".", ".", "Architecture", "x86_64"],
                            [".", "MemoryUtilization", "Architecture", "arm64"],
                            [".", "ARM64CostSavings"]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": self.region,
                        "view": "timeSeries"
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "EventBridge Performance",
                        "metrics": [
                            ["FormBridge/EventBridge", "EventProcessingLatency"],
                            [".", "RuleMatchEfficiency"],
                            [".", "EventsPublished"],
                            [".", "DeadLetterQueueDepth"]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": self.region,
                        "yAxis": {"left": {"min": 0}}
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "DynamoDB Performance",
                        "metrics": [
                            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "FormBridge-Submissions"],
                            [".", "ConsumedWriteCapacityUnits", ".", "."],
                            [".", "ThrottledRequests", ".", "."],
                            [".", "SuccessfulRequestLatency", ".", ".", {"stat": "Average"}]
                        ],
                        "period": 300,
                        "region": self.region,
                        "yAxis": {"left": {"min": 0}}
                    }
                },
                {
                    "type": "log",
                    "x": 0, "y": 12,
                    "width": 24, "height": 6,
                    "properties": {
                        "title": "Performance Regression Detection",
                        "query": "SOURCE '/aws/lambda/form-bridge' | fields @timestamp, @duration, function_name, tenant_id\n| filter @duration > 1000\n| stats avg(@duration), count(), max(@duration) by tenant_id\n| sort avg desc\n| limit 20",
                        "region": self.region,
                        "view": "table"
                    }
                }
            ]
        }

    def _get_cost_dashboard_config(self) -> Dict[str, Any]:
        """Cost monitoring dashboard configuration"""
        return {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Monthly Cost Tracking",
                        "metrics": [
                            ["FormBridge/Costs", "MonthlyCost"],
                            [".", "CostPerTenant"]
                        ],
                        "period": 3600,
                        "stat": "Maximum",
                        "region": self.region,
                        "yAxis": {"left": {"min": 0}},
                        "annotations": {
                            "horizontal": [
                                {"label": "Warning ($10)", "value": 10, "color": "#ff7f0e"},
                                {"label": "Alert ($15)", "value": 15, "color": "#d62728"},
                                {"label": "Critical ($20)", "value": 20, "color": "#8c564b"}
                            ]
                        }
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Service Cost Breakdown",
                        "metrics": [
                            ["FormBridge/Costs", "ServiceCost", "Service", "AWS Lambda"],
                            [".", ".", "Service", "Amazon DynamoDB"],
                            [".", ".", "Service", "Amazon EventBridge"],
                            [".", ".", "Service", "Amazon CloudWatch"],
                            [".", ".", "Service", "Amazon S3"]
                        ],
                        "period": 3600,
                        "stat": "Maximum",
                        "region": self.region,
                        "view": "pie"
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "ARM64 Cost Savings Tracking",
                        "metrics": [
                            ["FormBridge/Lambda", "ARM64CostSavings", {"stat": "Sum"}]
                        ],
                        "period": 3600,
                        "region": self.region,
                        "view": "singleValue",
                        "sparkline": True
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Resource Usage Efficiency",
                        "metrics": [
                            ["FormBridge/Costs", "lambda_invocationsUsage", "Service", "lambda"],
                            [".", "dynamodb_readsUsage", "Service", "dynamodb"],
                            [".", "dynamodb_writesUsage", "Service", "dynamodb"],
                            [".", "eventbridge_eventsUsage", "Service", "eventbridge"]
                        ],
                        "period": 3600,
                        "stat": "Sum",
                        "region": self.region,
                        "view": "timeSeries"
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 12,
                    "width": 24, "height": 6,
                    "properties": {
                        "title": "Cost Optimization Opportunities",
                        "metrics": [
                            ["FormBridge/Costs", "CostOptimizationPotential", "Service", "Lambda"],
                            [".", ".", "Service", "DynamoDB"],
                            [".", ".", "Service", "CloudWatch"]
                        ],
                        "period": 3600,
                        "stat": "Maximum",
                        "region": self.region,
                        "view": "bar"
                    }
                }
            ]
        }

    def _get_business_dashboard_config(self) -> Dict[str, Any]:
        """Business metrics dashboard configuration"""
        return {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Form Submissions Volume",
                        "metrics": [
                            ["FormBridge/Business", "FormSubmissions"],
                            [".", "FormSubmissions", "FormType", "contact"],
                            [".", ".", "FormType", "newsletter"],
                            [".", ".", "FormType", "support"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": self.region,
                        "view": "timeSeries",
                        "yAxis": {"left": {"min": 0}}
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 0,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "SLA Performance (Processing Time)",
                        "metrics": [
                            ["FormBridge/Business", "ProcessingTime", {"stat": "p50"}],
                            [".", ".", {"stat": "p90"}],
                            [".", ".", {"stat": "p95"}]
                        ],
                        "period": 300,
                        "region": self.region,
                        "yAxis": {"left": {"min": 0}},
                        "annotations": {
                            "horizontal": [
                                {"label": "SLA Target (5s)", "value": 5}
                            ]
                        }
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Delivery Success Rate",
                        "metrics": [
                            ["FormBridge/Business", "DeliverySuccessRate"]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": self.region,
                        "view": "singleValue",
                        "sparkline": True,
                        "yAxis": {"left": {"min": 95, "max": 100}}
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Active Tenants",
                        "metrics": [
                            ["FormBridge/Business", "FormSubmissions", {"stat": "SampleCount"}]
                        ],
                        "period": 3600,
                        "region": self.region,
                        "view": "number"
                    }
                },
                {
                    "type": "log",
                    "x": 0, "y": 12,
                    "width": 24, "height": 6,
                    "properties": {
                        "title": "Top Tenants by Volume",
                        "query": "SOURCE '/aws/lambda/form-bridge' | fields tenant_id, @timestamp\n| filter @message like /form_submission/\n| stats count() as submissions by tenant_id\n| sort submissions desc\n| limit 10",
                        "region": self.region,
                        "view": "table"
                    }
                }
            ]
        }

    def _get_executive_dashboard_config(self) -> Dict[str, Any]:
        """Executive summary dashboard configuration"""
        return {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0, "y": 0,
                    "width": 6, "height": 6,
                    "properties": {
                        "title": "System Health Score",
                        "metrics": [
                            ["FormBridge/Business", "DeliverySuccessRate"]
                        ],
                        "period": 3600,
                        "stat": "Average",
                        "region": self.region,
                        "view": "singleValue",
                        "yAxis": {"left": {"min": 95, "max": 100}}
                    }
                },
                {
                    "type": "metric",
                    "x": 6, "y": 0,
                    "width": 6, "height": 6,
                    "properties": {
                        "title": "Monthly Cost",
                        "metrics": [
                            ["FormBridge/Costs", "MonthlyCost"]
                        ],
                        "period": 3600,
                        "stat": "Maximum",
                        "region": self.region,
                        "view": "singleValue"
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 0,
                    "width": 6, "height": 6,
                    "properties": {
                        "title": "Security Incidents",
                        "metrics": [
                            ["FormBridge/Security", "CrossTenantAccessAttempts", {"stat": "Sum"}]
                        ],
                        "period": 86400,
                        "region": self.region,
                        "view": "singleValue"
                    }
                },
                {
                    "type": "metric",
                    "x": 18, "y": 0,
                    "width": 6, "height": 6,
                    "properties": {
                        "title": "Daily Submissions",
                        "metrics": [
                            ["FormBridge/Business", "FormSubmissions", {"stat": "Sum"}]
                        ],
                        "period": 86400,
                        "region": self.region,
                        "view": "singleValue"
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Cost vs Budget Trend",
                        "metrics": [
                            ["FormBridge/Costs", "MonthlyCost"]
                        ],
                        "period": 86400,
                        "stat": "Maximum",
                        "region": self.region,
                        "view": "timeSeries",
                        "annotations": {
                            "horizontal": [
                                {"label": "Budget Target ($12)", "value": 12}
                            ]
                        }
                    }
                },
                {
                    "type": "metric",
                    "x": 12, "y": 6,
                    "width": 12, "height": 6,
                    "properties": {
                        "title": "Performance SLA Compliance",
                        "metrics": [
                            ["FormBridge/Business", "ProcessingTime", {"stat": "p95"}]
                        ],
                        "period": 3600,
                        "region": self.region,
                        "view": "timeSeries",
                        "yAxis": {"left": {"min": 0}},
                        "annotations": {
                            "horizontal": [
                                {"label": "SLA Target (5s)", "value": 5}
                            ]
                        }
                    }
                }
            ]
        }

    def create_custom_alarms(self):
        """Create custom CloudWatch alarms for monitoring"""
        alarms = []
        
        # Cost monitoring alarms
        cost_alarms = [
            {
                'name': 'FormBridge-CostAlert-Warning-10USD',
                'metric_name': 'MonthlyCost',
                'namespace': 'FormBridge/Costs',
                'threshold': 10.0,
                'comparison': 'GreaterThanThreshold',
                'description': 'Monthly costs exceeded $10 warning threshold'
            },
            {
                'name': 'FormBridge-CostAlert-Alert-15USD',
                'metric_name': 'MonthlyCost',
                'namespace': 'FormBridge/Costs', 
                'threshold': 15.0,
                'comparison': 'GreaterThanThreshold',
                'description': 'Monthly costs exceeded $15 alert threshold'
            },
            {
                'name': 'FormBridge-CostAlert-Critical-20USD',
                'metric_name': 'MonthlyCost',
                'namespace': 'FormBridge/Costs',
                'threshold': 20.0,
                'comparison': 'GreaterThanThreshold',
                'description': 'Monthly costs exceeded $20 critical threshold'
            }
        ]
        
        # Security alarms
        security_alarms = [
            {
                'name': 'FormBridge-Security-CrossTenantAccess',
                'metric_name': 'CrossTenantAccessAttempts',
                'namespace': 'FormBridge/Security',
                'threshold': 1,
                'comparison': 'GreaterThanOrEqualToThreshold',
                'description': 'Cross-tenant access attempt detected - CRITICAL'
            },
            {
                'name': 'FormBridge-Security-AuthFailureRate',
                'metric_name': 'AuthenticationFailures',
                'namespace': 'FormBridge/Security',
                'threshold': 10,
                'comparison': 'GreaterThanThreshold',
                'description': 'High authentication failure rate detected'
            }
        ]
        
        # Performance alarms
        performance_alarms = [
            {
                'name': 'FormBridge-Performance-HighLatency',
                'metric_name': 'ProcessingTime',
                'namespace': 'FormBridge/Business',
                'threshold': 5.0,
                'statistic': 'Average',
                'comparison': 'GreaterThanThreshold',
                'description': 'Processing time exceeded 5 second SLA'
            },
            {
                'name': 'FormBridge-Performance-DeliveryFailure',
                'metric_name': 'DeliverySuccessRate',
                'namespace': 'FormBridge/Business',
                'threshold': 95.0,
                'comparison': 'LessThanThreshold',
                'description': 'Delivery success rate below 95% SLA'
            }
        ]
        
        all_alarms = cost_alarms + security_alarms + performance_alarms
        
        for alarm_config in all_alarms:
            try:
                self.cloudwatch.put_metric_alarm(
                    AlarmName=alarm_config['name'],
                    ComparisonOperator=alarm_config['comparison'],
                    EvaluationPeriods=2,
                    MetricName=alarm_config['metric_name'],
                    Namespace=alarm_config['namespace'],
                    Period=300,
                    Statistic=alarm_config.get('statistic', 'Sum'),
                    Threshold=alarm_config['threshold'],
                    ActionsEnabled=True,
                    AlarmActions=[
                        f'arn:aws:sns:{self.region}:{self.account_id}:form-bridge-alerts'
                    ],
                    AlarmDescription=alarm_config['description'],
                    Unit='None'
                )
                
                alarms.append({'name': alarm_config['name'], 'status': 'created'})
                print(f"Created alarm: {alarm_config['name']}")
                
            except Exception as e:
                alarms.append({'name': alarm_config['name'], 'status': 'failed', 'error': str(e)})
                print(f"Error creating alarm {alarm_config['name']}: {str(e)}")
        
        return alarms

    def setup_anomaly_detection(self):
        """Setup CloudWatch Anomaly Detection for key metrics"""
        anomaly_detectors = [
            {
                'metric_name': 'FormSubmissions',
                'namespace': 'FormBridge/Business',
                'dimensions': []
            },
            {
                'metric_name': 'ProcessingTime',
                'namespace': 'FormBridge/Business',
                'dimensions': []
            },
            {
                'metric_name': 'MonthlyCost',
                'namespace': 'FormBridge/Costs',
                'dimensions': []
            }
        ]
        
        results = []
        
        for detector_config in anomaly_detectors:
            try:
                self.cloudwatch.put_anomaly_detector(
                    Namespace=detector_config['namespace'],
                    MetricName=detector_config['metric_name'],
                    Dimensions=detector_config['dimensions'],
                    Stat='Average'
                )
                
                results.append({
                    'metric': f"{detector_config['namespace']}.{detector_config['metric_name']}",
                    'status': 'created'
                })
                print(f"Created anomaly detector for {detector_config['metric_name']}")
                
            except Exception as e:
                results.append({
                    'metric': f"{detector_config['namespace']}.{detector_config['metric_name']}",
                    'status': 'failed',
                    'error': str(e)
                })
                print(f"Error creating anomaly detector for {detector_config['metric_name']}: {str(e)}")
        
        return results

def lambda_handler(event, context):
    """Lambda handler to create dashboards and monitoring setup"""
    dashboard_manager = FormBridgeDashboardManager()
    
    action = event.get('action', 'create_all')
    results = {}
    
    if action == 'create_all' or action == 'dashboards':
        results['dashboards'] = dashboard_manager.create_all_dashboards()
    
    if action == 'create_all' or action == 'alarms':
        results['alarms'] = dashboard_manager.create_custom_alarms()
    
    if action == 'create_all' or action == 'anomaly_detection':
        results['anomaly_detection'] = dashboard_manager.setup_anomaly_detection()
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Monitoring setup completed',
            'results': results
        }, indent=2)
    }

if __name__ == "__main__":
    # Test the dashboard manager
    manager = FormBridgeDashboardManager()
    
    print("Creating all monitoring dashboards...")
    dashboard_results = manager.create_all_dashboards()
    print(f"Dashboard creation results: {json.dumps(dashboard_results, indent=2)}")
    
    print("\nCreating custom alarms...")
    alarm_results = manager.create_custom_alarms()
    print(f"Alarm creation results: {json.dumps(alarm_results, indent=2)}")
    
    print("\nSetting up anomaly detection...")
    anomaly_results = manager.setup_anomaly_detection()
    print(f"Anomaly detection results: {json.dumps(anomaly_results, indent=2)}")
# Analytics Implementation Guide - Form-Bridge Platform

## DynamoDB Single-Table Design for Analytics

### Table Schema Design

#### Primary Metrics Table: `formbridge-metrics`
```python
METRICS_TABLE_SCHEMA = {
    "TableName": "formbridge-metrics",
    "BillingMode": "ON_DEMAND",
    "KeySchema": [
        {"AttributeName": "PK", "KeyType": "HASH"},
        {"AttributeName": "SK", "KeyType": "RANGE"}
    ],
    "AttributeDefinitions": [
        {"AttributeName": "PK", "AttributeType": "S"},
        {"AttributeName": "SK", "AttributeType": "S"},
        {"AttributeName": "GSI1_PK", "AttributeType": "S"},
        {"AttributeName": "GSI1_SK", "AttributeType": "S"},
        {"AttributeName": "GSI2_PK", "AttributeType": "S"},
        {"AttributeName": "GSI2_SK", "AttributeType": "S"},
        {"AttributeName": "timestamp", "AttributeType": "N"}
    ],
    "GlobalSecondaryIndexes": [
        {
            "IndexName": "GSI1",
            "KeySchema": [
                {"AttributeName": "GSI1_PK", "KeyType": "HASH"},
                {"AttributeName": "GSI1_SK", "KeyType": "RANGE"}
            ],
            "Projection": {"ProjectionType": "ALL"}
        },
        {
            "IndexName": "GSI2", 
            "KeySchema": [
                {"AttributeName": "GSI2_PK", "KeyType": "HASH"},
                {"AttributeName": "GSI2_SK", "KeyType": "RANGE"}
            ],
            "Projection": {"ProjectionType": "ALL"}
        },
        {
            "IndexName": "TimestampIndex",
            "KeySchema": [
                {"AttributeName": "timestamp", "KeyType": "HASH"}
            ],
            "Projection": {"ProjectionType": "KEYS_ONLY"}
        }
    ],
    "TimeToLiveSpecification": {
        "AttributeName": "ttl",
        "Enabled": True
    }
}
```

### Data Model Patterns

#### 1. Real-time Submission Events
```python
SUBMISSION_EVENT = {
    "PK": "TENANT#agency123#EVENT#SUBMISSION",
    "SK": f"TIMESTAMP#{int(time.time()*1000)}#ID#{submission_id}",
    "GSI1_PK": f"SITE#{site_domain}#DATE#{date_str}",
    "GSI1_SK": f"HOUR#{hour}#STATUS#{status}",
    "GSI2_PK": f"TENANT#{tenant_id}#REALTIME",
    "GSI2_SK": f"TIMESTAMP#{timestamp}",
    
    # Event data
    "event_type": "form_submission",
    "tenant_id": "agency123",
    "site_id": "site_abc_123",
    "site_domain": "example.com",
    "form_id": "contact_form_v2",
    "submission_id": "sub_xyz789",
    "status": "success",  # success, failed, processing
    "processing_time_ms": 1250,
    "destination_count": 3,
    "destinations_success": 2,
    "destinations_failed": 1,
    "timestamp": 1692134400,
    "ttl": 1699910400  # 90 days retention
}
```

#### 2. Hourly Aggregations
```python
HOURLY_AGGREGATION = {
    "PK": f"TENANT#{tenant_id}#AGG#HOURLY",
    "SK": f"DATE#{date_str}#HOUR#{hour}#SITE#{site_id}",
    "GSI1_PK": f"DATE#{date_str}#HOUR#{hour}",
    "GSI1_SK": f"TENANT#{tenant_id}#SITE#{site_id}",
    "GSI2_PK": f"SITE#{site_id}#HOURLY",
    "GSI2_SK": f"DATE#{date_str}#HOUR#{hour}",
    
    # Aggregated metrics
    "metric_type": "hourly_summary",
    "total_submissions": 156,
    "successful_submissions": 149,
    "failed_submissions": 7,
    "success_rate": 95.51,
    "avg_processing_time_ms": 1125,
    "p50_processing_time_ms": 980,
    "p95_processing_time_ms": 2100,
    "p99_processing_time_ms": 3200,
    
    # Destination breakdown
    "destinations": {
        "webhook": {"count": 89, "success": 86, "failed": 3},
        "slack": {"count": 45, "success": 44, "failed": 1},
        "email": {"count": 22, "success": 19, "failed": 3}
    },
    
    # Cost metrics
    "estimated_cost_usd": 0.0234,
    "lambda_invocations": 468,
    "dynamodb_rcu_consumed": 23,
    "dynamodb_wcu_consumed": 89,
    
    "timestamp": 1692134400,
    "ttl": 1707686400  # 2 years retention for aggregated data
}
```

#### 3. Daily Summaries
```python
DAILY_SUMMARY = {
    "PK": f"TENANT#{tenant_id}#AGG#DAILY",
    "SK": f"DATE#{date_str}#SITE#{site_id}",
    "GSI1_PK": f"DATE#{date_str}",
    "GSI1_SK": f"TENANT#{tenant_id}#VOLUME#{total_submissions:08d}",
    "GSI2_PK": f"TENANT#{tenant_id}#DAILY",
    "GSI2_SK": f"DATE#{date_str}",
    
    # Daily aggregated metrics
    "total_submissions": 3744,
    "successful_submissions": 3579,
    "failed_submissions": 165,
    "success_rate": 95.59,
    "unique_forms": 12,
    "active_destinations": 8,
    
    # Performance metrics
    "avg_processing_time_ms": 1089,
    "p99_processing_time_ms": 2890,
    "peak_hour_volume": 312,
    "peak_hour": 14,  # 2 PM
    
    # Business metrics
    "estimated_cost_usd": 0.487,
    "cost_per_submission": 0.00013,
    
    # Error analysis
    "error_breakdown": {
        "api_timeout": 89,
        "destination_unreachable": 45,
        "authentication_failed": 21,
        "payload_too_large": 10
    },
    
    "timestamp": 1692134400,
    "ttl": 1707686400  # 2 years retention
}
```

#### 4. Site Health Status
```python
SITE_HEALTH = {
    "PK": f"TENANT#{tenant_id}#HEALTH#SITE",
    "SK": f"SITE#{site_id}#STATUS#{status_timestamp}",
    "GSI1_PK": f"HEALTH#MONITOR#SITES",
    "GSI1_SK": f"TENANT#{tenant_id}#STATUS#{health_score:03d}",
    "GSI2_PK": f"SITE#{site_id}#HEALTH",
    "GSI2_SK": f"TIMESTAMP#{status_timestamp}",
    
    # Health indicators
    "health_score": 89,  # 0-100 composite score
    "status": "healthy",  # healthy, warning, critical
    "last_submission_timestamp": 1692134400,
    "submissions_24h": 234,
    "success_rate_24h": 96.15,
    "avg_response_time_24h": 1045,
    
    # Alert thresholds
    "consecutive_failures": 0,
    "error_spike_detected": False,
    "processing_time_degradation": False,
    "volume_anomaly": "none",  # none, high, low
    
    # Historical trends
    "success_rate_trend_7d": 1.2,  # percentage change
    "volume_trend_7d": -3.1,
    "performance_trend_7d": 0.8,
    
    "timestamp": 1692134400,
    "ttl": 1699910400  # 90 days retention
}
```

### Query Patterns Implementation

#### Dashboard Widget Queries

##### 1. Tenant Overview Query
```python
def get_tenant_overview(tenant_id, time_range_hours=24):
    """Get real-time overview for tenant dashboard"""
    
    # Query pattern for recent submissions
    response = dynamodb.query(
        TableName='formbridge-metrics',
        KeyConditionExpression='PK = :pk AND SK > :sk',
        ExpressionAttributeValues={
            ':pk': f'TENANT#{tenant_id}#EVENT#SUBMISSION',
            ':sk': f'TIMESTAMP#{int((time.time() - time_range_hours*3600) * 1000)}'
        },
        ScanIndexForward=False,
        Limit=1000
    )
    
    # Query hourly aggregations for trends
    hourly_response = dynamodb.query(
        TableName='formbridge-metrics',
        KeyConditionExpression='PK = :pk',
        FilterExpression='begins_with(SK, :sk_prefix)',
        ExpressionAttributeValues={
            ':pk': f'TENANT#{tenant_id}#AGG#HOURLY',
            ':sk_prefix': f'DATE#{date.today().isoformat()}'
        }
    )
    
    return process_overview_data(response, hourly_response)
```

##### 2. Site Performance Query
```python
def get_site_performance(tenant_id, site_id, days=7):
    """Get detailed site performance metrics"""
    
    daily_summaries = dynamodb.query(
        TableName='formbridge-metrics',
        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
        ExpressionAttributeValues={
            ':pk': f'TENANT#{tenant_id}#AGG#DAILY',
            ':sk_prefix': f'DATE#{(date.today() - timedelta(days=days)).isoformat()}'
        },
        FilterExpression='contains(SK, :site_id)',
        ExpressionAttributeValues={
            ':site_id': f'SITE#{site_id}'
        }
    )
    
    # Get current health status
    health_status = dynamodb.query(
        TableName='formbridge-metrics',
        IndexName='GSI2',
        KeyConditionExpression='GSI2_PK = :pk',
        ScanIndexForward=False,
        Limit=1,
        ExpressionAttributeValues={
            ':pk': f'SITE#{site_id}#HEALTH'
        }
    )
    
    return process_site_performance(daily_summaries, health_status)
```

##### 3. Cross-Tenant Analytics Query (Admin View)
```python
def get_cross_tenant_analytics(metric_type, date_range):
    """Get analytics across all tenants (admin dashboard)"""
    
    response = dynamodb.query(
        TableName='formbridge-metrics',
        IndexName='GSI1',
        KeyConditionExpression='GSI1_PK = :pk',
        ExpressionAttributeValues={
            ':pk': f'DATE#{date_range}#HOUR#{hour}'
        }
    )
    
    return process_cross_tenant_data(response)
```

## EventBridge Integration for Real-time Analytics

### Event Schema Definition

#### Core Analytics Events
```python
ANALYTICS_EVENT_SCHEMAS = {
    "form.submission.received": {
        "source": "formbridge.ingestion",
        "detail-type": "Form Submission Received",
        "detail": {
            "tenant_id": "string",
            "site_id": "string", 
            "site_domain": "string",
            "form_id": "string",
            "submission_id": "string",
            "timestamp": "number",
            "payload_size_bytes": "number",
            "source_ip": "string",
            "user_agent": "string"
        }
    },
    
    "form.submission.processed": {
        "source": "formbridge.processing",
        "detail-type": "Form Submission Processed", 
        "detail": {
            "tenant_id": "string",
            "submission_id": "string",
            "processing_time_ms": "number",
            "status": "string",  # success, failed, partial
            "destinations_attempted": "number",
            "destinations_successful": "number",
            "destinations_failed": "number",
            "error_details": "object"
        }
    },
    
    "destination.delivery.completed": {
        "source": "formbridge.delivery",
        "detail-type": "Destination Delivery Completed",
        "detail": {
            "tenant_id": "string",
            "submission_id": "string",
            "destination_id": "string",
            "destination_type": "string",
            "status": "string",  # delivered, failed, retrying
            "response_time_ms": "number",
            "retry_count": "number",
            "error_message": "string"
        }
    }
}
```

### Analytics Event Processing Architecture

#### Event Rule Configuration
```python
EVENTBRIDGE_RULES = {
    "real_time_metrics_aggregation": {
        "Name": "formbridge-realtime-analytics",
        "EventPattern": {
            "source": ["formbridge.ingestion", "formbridge.processing"],
            "detail-type": [
                "Form Submission Received",
                "Form Submission Processed"
            ]
        },
        "Targets": [
            {
                "Id": "1",
                "Arn": "arn:aws:lambda:region:account:function:analytics-stream-processor",
                "InputTransformer": {
                    "InputPathsMap": {
                        "tenant": "$.detail.tenant_id",
                        "timestamp": "$.detail.timestamp",
                        "status": "$.detail.status"
                    },
                    "InputTemplate": '{"tenant_id": "<tenant>", "event_time": <timestamp>, "status": "<status>", "raw_event": <aws.events.event>}'
                }
            }
        ]
    },
    
    "alerting_system": {
        "Name": "formbridge-alerting",
        "EventPattern": {
            "source": ["formbridge.processing"],
            "detail-type": ["Form Submission Processed"],
            "detail": {
                "status": ["failed"]
            }
        },
        "Targets": [
            {
                "Id": "1", 
                "Arn": "arn:aws:lambda:region:account:function:alert-processor",
                "DeadLetterConfig": {
                    "Arn": "arn:aws:sqs:region:account:queue:alert-dlq"
                }
            }
        ]
    }
}
```

#### Real-time Analytics Processor
```python
import json
import boto3
from datetime import datetime, timedelta
from decimal import Decimal

def lambda_handler(event, context):
    """Process real-time analytics events from EventBridge"""
    
    dynamodb = boto3.resource('dynamodb')
    metrics_table = dynamodb.Table('formbridge-metrics')
    
    try:
        # Parse incoming event
        detail = event['detail']
        tenant_id = detail['tenant_id']
        timestamp = int(detail['timestamp'])
        event_type = event['detail-type']
        
        # Create real-time event record
        event_record = create_event_record(detail, event_type, timestamp)
        
        # Update real-time metrics
        update_realtime_metrics(metrics_table, tenant_id, detail, timestamp)
        
        # Check for alert conditions
        check_alert_conditions(tenant_id, detail)
        
        # Update site health indicators
        update_site_health(metrics_table, detail)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Analytics event processed successfully')
        }
        
    except Exception as e:
        print(f"Error processing analytics event: {str(e)}")
        # Send to DLQ for retry
        raise e

def create_event_record(detail, event_type, timestamp):
    """Create individual event record in DynamoDB"""
    
    tenant_id = detail['tenant_id']
    submission_id = detail.get('submission_id', f'unknown_{timestamp}')
    
    record = {
        'PK': f'TENANT#{tenant_id}#EVENT#SUBMISSION',
        'SK': f'TIMESTAMP#{timestamp}#ID#{submission_id}',
        'GSI1_PK': f'SITE#{detail.get("site_id", "unknown")}#DATE#{datetime.fromtimestamp(timestamp/1000).date().isoformat()}',
        'GSI1_SK': f'HOUR#{datetime.fromtimestamp(timestamp/1000).hour:02d}#STATUS#{detail.get("status", "unknown")}',
        'GSI2_PK': f'TENANT#{tenant_id}#REALTIME',
        'GSI2_SK': f'TIMESTAMP#{timestamp}',
        
        'event_type': event_type.lower().replace(' ', '_'),
        'tenant_id': tenant_id,
        'site_id': detail.get('site_id'),
        'site_domain': detail.get('site_domain'),
        'form_id': detail.get('form_id'),
        'submission_id': submission_id,
        'status': detail.get('status'),
        'processing_time_ms': detail.get('processing_time_ms'),
        'timestamp': timestamp,
        'ttl': int((datetime.now() + timedelta(days=90)).timestamp())
    }
    
    return record

def update_realtime_metrics(table, tenant_id, detail, timestamp):
    """Update real-time aggregated metrics"""
    
    current_hour = datetime.fromtimestamp(timestamp/1000).replace(minute=0, second=0, microsecond=0)
    hour_key = int(current_hour.timestamp())
    
    # Update hourly aggregation with atomic counters
    table.update_item(
        Key={
            'PK': f'TENANT#{tenant_id}#AGG#REALTIME',
            'SK': f'HOUR#{hour_key}'
        },
        UpdateExpression='''
            SET #ts = :timestamp,
                #ttl = :ttl
            ADD #total = :one,
                #success = :success_inc,
                #failed = :failed_inc,
                #proc_time = :proc_time
        ''',
        ExpressionAttributeNames={
            '#ts': 'timestamp',
            '#ttl': 'ttl', 
            '#total': 'total_submissions',
            '#success': 'successful_submissions',
            '#failed': 'failed_submissions',
            '#proc_time': 'total_processing_time_ms'
        },
        ExpressionAttributeValues={
            ':timestamp': timestamp,
            ':ttl': int((datetime.now() + timedelta(hours=25)).timestamp()),
            ':one': 1,
            ':success_inc': 1 if detail.get('status') == 'success' else 0,
            ':failed_inc': 1 if detail.get('status') == 'failed' else 0,
            ':proc_time': detail.get('processing_time_ms', 0)
        }
    )
```

### WebSocket Integration for Real-time Dashboard

#### WebSocket API Configuration
```python
WEBSOCKET_CONFIG = {
    "api_name": "formbridge-realtime-dashboard",
    "routes": {
        "$connect": "websocket-connect-handler",
        "$disconnect": "websocket-disconnect-handler", 
        "subscribe": "websocket-subscribe-handler",
        "unsubscribe": "websocket-unsubscribe-handler"
    },
    "authorization": "aws_iam",
    "cors_enabled": True
}

def websocket_subscribe_handler(event, context):
    """Handle dashboard subscription requests"""
    
    connection_id = event['requestContext']['connectionId']
    body = json.loads(event['body'])
    
    tenant_id = body.get('tenant_id')
    subscription_type = body.get('type')  # 'realtime_metrics', 'alerts', 'events'
    filters = body.get('filters', {})
    
    # Store subscription in DynamoDB
    subscriptions_table = boto3.resource('dynamodb').Table('websocket-subscriptions')
    subscriptions_table.put_item(
        Item={
            'connection_id': connection_id,
            'tenant_id': tenant_id,
            'subscription_type': subscription_type,
            'filters': filters,
            'connected_at': int(time.time()),
            'ttl': int(time.time() + 86400)  # 24 hour TTL
        }
    )
    
    return {'statusCode': 200, 'body': 'Subscribed successfully'}
```

#### Real-time Metric Broadcaster
```python
def broadcast_realtime_metrics(event, context):
    """Broadcast metrics to subscribed WebSocket connections"""
    
    # Extract metrics from EventBridge event
    detail = event['detail']
    tenant_id = detail['tenant_id']
    
    # Find active subscriptions for this tenant
    subscriptions = get_active_subscriptions(tenant_id, 'realtime_metrics')
    
    # Prepare metric update
    metric_update = {
        'type': 'metric_update',
        'timestamp': int(time.time()),
        'data': {
            'tenant_id': tenant_id,
            'site_id': detail.get('site_id'),
            'current_submission_rate': calculate_current_rate(tenant_id),
            'success_rate_1h': calculate_success_rate(tenant_id, hours=1),
            'active_alerts': get_active_alert_count(tenant_id),
            'latest_event': detail
        }
    }
    
    # Broadcast to all subscribed connections
    api_gateway = boto3.client('apigatewaymanagementapi',
        endpoint_url=f"https://{websocket_api_id}.execute-api.{region}.amazonaws.com/{stage}"
    )
    
    for subscription in subscriptions:
        try:
            api_gateway.post_to_connection(
                ConnectionId=subscription['connection_id'],
                Data=json.dumps(metric_update)
            )
        except api_gateway.exceptions.GoneException:
            # Connection is closed, remove subscription
            remove_subscription(subscription['connection_id'])
```

### Cost Optimization Strategies

#### Intelligent Data Retention
```python
def setup_data_retention_policy():
    """Configure TTL and archival for cost optimization"""
    
    retention_policies = {
        'real_time_events': {
            'ttl_days': 7,
            'rationale': 'Real-time events only needed for immediate alerting'
        },
        'hourly_aggregations': {
            'ttl_days': 90, 
            'archive_to_s3': True,
            'rationale': 'Detailed hourly data for trend analysis'
        },
        'daily_summaries': {
            'ttl_days': 730,  # 2 years
            'archive_to_s3': True, 
            'rationale': 'Business intelligence and compliance'
        },
        'alert_history': {
            'ttl_days': 365,
            'archive_to_s3': False,
            'rationale': 'Operational history for pattern analysis'  
        }
    }
    
    return retention_policies

def optimize_query_costs():
    """Implement query cost optimization strategies"""
    
    strategies = {
        'read_capacity_optimization': {
            'use_eventually_consistent_reads': True,
            'implement_pagination': True,
            'cache_frequently_accessed_data': 'redis_5min_ttl'
        },
        'write_capacity_optimization': {
            'batch_write_operations': True,
            'use_conditional_writes': 'prevent_overwrites',
            'implement_write_deduplication': True
        },
        'storage_optimization': {
            'compress_large_payloads': True,
            'normalize_repeated_values': True,
            'use_sparse_attributes': True
        }
    }
    
    return strategies
```

This implementation guide provides a comprehensive foundation for building the Form-Bridge analytics system using DynamoDB single-table design and EventBridge real-time processing, optimized for both performance and cost-effectiveness.
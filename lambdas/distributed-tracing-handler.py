#!/usr/bin/env python3
"""
Distributed Tracing Handler for Form-Bridge Multi-Tenant Architecture
Implements comprehensive X-Ray tracing with correlation across EventBridge, Lambda, DynamoDB
"""

import json
import uuid
import time
import boto3
from datetime import datetime
from typing import Dict, Any, Optional, List
import os
import hashlib

# X-Ray imports with fallback
try:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch_all
    from aws_xray_sdk.ext.lambda_context import LambdaContext
    
    # Patch all AWS SDK calls for automatic tracing
    patch_all()
    XRAY_AVAILABLE = True
except ImportError:
    print("X-Ray SDK not available - distributed tracing disabled")
    XRAY_AVAILABLE = False
    
    # Mock X-Ray recorder for development
    class MockXRayRecorder:
        def capture(self, name):
            def decorator(func):
                return func
            return decorator
            
        def put_annotation(self, key, value):
            pass
            
        def put_metadata(self, key, value, namespace='default'):
            pass
            
        def in_subsegment(self, name):
            class MockSubsegment:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockSubsegment()
    
    xray_recorder = MockXRayRecorder()

class FormBridgeTracer:
    """Comprehensive distributed tracing for multi-tenant event processing"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.eventbridge = boto3.client('events')
        self.correlation_table_name = os.environ.get(
            'CORRELATION_TABLE_NAME', 
            'FormBridge-TraceCorrelation'
        )
        
    def start_trace_context(self, event: Dict[str, Any], context: Any) -> Dict[str, str]:
        """Initialize trace context for the event processing chain"""
        # Extract or generate correlation ID
        correlation_id = event.get('correlation_id') or str(uuid.uuid4())
        
        # Generate unique trace identifiers
        trace_id = correlation_id
        tenant_id = event.get('tenant_id', 'unknown')
        submission_id = event.get('submission_id') or str(uuid.uuid4())
        
        # Create trace context
        trace_context = {
            'correlation_id': correlation_id,
            'trace_id': trace_id,
            'tenant_id': tenant_id,
            'submission_id': submission_id,
            'function_name': context.function_name if hasattr(context, 'function_name') else 'unknown',
            'request_id': context.aws_request_id if hasattr(context, 'aws_request_id') else str(uuid.uuid4()),
            'start_time': datetime.utcnow().isoformat(),
            'environment': os.environ.get('ENVIRONMENT', 'dev')
        }
        
        # Add X-Ray annotations for filtering and searching
        if XRAY_AVAILABLE:
            xray_recorder.put_annotation('correlation_id', correlation_id)
            xray_recorder.put_annotation('tenant_id', tenant_id)
            xray_recorder.put_annotation('submission_id', submission_id)
            xray_recorder.put_annotation('environment', trace_context['environment'])
            
            # Add metadata for debugging
            xray_recorder.put_metadata('trace_context', trace_context, 'FormBridge')
            xray_recorder.put_metadata('event', self._sanitize_event(event), 'FormBridge')
        
        return trace_context
        
    def _sanitize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from event for tracing"""
        sanitized = event.copy()
        
        # Remove sensitive fields
        sensitive_fields = ['hmac_signature', 'api_key', 'secret', 'password', 'token']
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
                
        # Truncate large payloads
        if 'form_data' in sanitized and isinstance(sanitized['form_data'], str):
            if len(sanitized['form_data']) > 1000:
                sanitized['form_data'] = sanitized['form_data'][:1000] + '... [TRUNCATED]'
                
        return sanitized

    @xray_recorder.capture('validate_hmac_authentication')
    def trace_hmac_validation(self, trace_context: Dict[str, str], validation_result: Dict[str, Any]):
        """Trace HMAC authentication validation with security context"""
        with xray_recorder.in_subsegment('hmac_validation_details'):
            xray_recorder.put_annotation('auth_success', validation_result.get('valid', False))
            xray_recorder.put_annotation('tenant_id', trace_context['tenant_id'])
            
            if not validation_result.get('valid', False):
                # Security event - always trace authentication failures
                xray_recorder.put_annotation('security_event', 'hmac_validation_failure')
                xray_recorder.put_metadata('auth_failure_details', {
                    'reason': validation_result.get('reason', 'unknown'),
                    'timestamp': datetime.utcnow().isoformat(),
                    'tenant_id': trace_context['tenant_id'],
                    'source_ip': validation_result.get('source_ip', 'unknown')
                }, 'Security')
                
            # Store correlation data for cross-service tracing
            self._store_trace_correlation(trace_context, 'hmac_validation', validation_result)

    @xray_recorder.capture('process_eventbridge_event')  
    def trace_eventbridge_processing(self, trace_context: Dict[str, str], event_data: Dict[str, Any]):
        """Trace EventBridge event processing with detailed metrics"""
        processing_start = time.time()
        
        with xray_recorder.in_subsegment('eventbridge_event_details'):
            # Annotate event characteristics
            xray_recorder.put_annotation('event_source', event_data.get('source', 'unknown'))
            xray_recorder.put_annotation('detail_type', event_data.get('detail-type', 'unknown'))
            xray_recorder.put_annotation('event_bus', event_data.get('event_bus_name', 'default'))
            
            # Add tenant-specific annotations
            xray_recorder.put_annotation('tenant_id', trace_context['tenant_id'])
            xray_recorder.put_annotation('multi_tenant_processing', True)
            
            # Metadata for detailed analysis
            xray_recorder.put_metadata('event_processing', {
                'correlation_id': trace_context['correlation_id'],
                'processing_stage': 'eventbridge_routing',
                'tenant_isolation_verified': self._verify_tenant_isolation(trace_context, event_data),
                'event_size_bytes': len(json.dumps(event_data)),
                'processing_timestamp': datetime.utcnow().isoformat()
            }, 'EventBridge')
            
        # Store processing metrics for correlation
        processing_time = time.time() - processing_start
        self._store_trace_correlation(trace_context, 'eventbridge_processing', {
            'processing_time_ms': processing_time * 1000,
            'event_size_bytes': len(json.dumps(event_data)),
            'tenant_isolation_verified': True
        })

    @xray_recorder.capture('persist_to_dynamodb')
    def trace_dynamodb_operations(self, trace_context: Dict[str, str], operation: str, table_name: str, item_data: Dict[str, Any]):
        """Trace DynamoDB operations with multi-tenant isolation monitoring"""
        operation_start = time.time()
        
        with xray_recorder.in_subsegment(f'dynamodb_{operation.lower()}'):
            # Annotate DynamoDB operation details
            xray_recorder.put_annotation('table_name', table_name)
            xray_recorder.put_annotation('operation_type', operation)
            xray_recorder.put_annotation('tenant_id', trace_context['tenant_id'])
            
            # Verify tenant isolation in data operations
            tenant_isolation_valid = self._verify_dynamodb_tenant_isolation(
                trace_context['tenant_id'], 
                item_data
            )
            
            xray_recorder.put_annotation('tenant_isolation_valid', tenant_isolation_valid)
            
            if not tenant_isolation_valid:
                # CRITICAL: Potential cross-tenant data access
                xray_recorder.put_annotation('SECURITY_ALERT', 'CROSS_TENANT_DATA_ACCESS')
                xray_recorder.put_metadata('security_violation', {
                    'violation_type': 'cross_tenant_data_access',
                    'expected_tenant': trace_context['tenant_id'],
                    'actual_tenant': self._extract_tenant_from_item(item_data),
                    'table_name': table_name,
                    'operation': operation,
                    'timestamp': datetime.utcnow().isoformat()
                }, 'Security')
            
            # Add operation metadata
            xray_recorder.put_metadata('dynamodb_operation', {
                'correlation_id': trace_context['correlation_id'],
                'item_size_bytes': len(json.dumps(item_data, default=str)),
                'partition_key': item_data.get('PK', 'unknown'),
                'sort_key': item_data.get('SK', 'unknown'),
                'tenant_prefix_verified': item_data.get('PK', '').startswith(f'TENANT#{trace_context["tenant_id"]}')
            }, 'DynamoDB')
        
        # Store operation metrics
        operation_time = time.time() - operation_start
        self._store_trace_correlation(trace_context, f'dynamodb_{operation}', {
            'operation_time_ms': operation_time * 1000,
            'table_name': table_name,
            'tenant_isolation_valid': tenant_isolation_valid,
            'item_size_bytes': len(json.dumps(item_data, default=str))
        })

    @xray_recorder.capture('deliver_to_destination')
    def trace_destination_delivery(self, trace_context: Dict[str, str], destination: Dict[str, Any], delivery_result: Dict[str, Any]):
        """Trace delivery to external destinations (S3, webhooks, etc.)"""
        with xray_recorder.in_subsegment('destination_delivery'):
            destination_type = destination.get('type', 'unknown')
            destination_id = destination.get('id', 'unknown')
            
            xray_recorder.put_annotation('destination_type', destination_type)
            xray_recorder.put_annotation('destination_id', destination_id)
            xray_recorder.put_annotation('delivery_success', delivery_result.get('success', False))
            xray_recorder.put_annotation('tenant_id', trace_context['tenant_id'])
            
            # Add delivery details
            xray_recorder.put_metadata('delivery_details', {
                'correlation_id': trace_context['correlation_id'],
                'destination_config': self._sanitize_destination_config(destination),
                'delivery_attempt': delivery_result.get('attempt', 1),
                'response_code': delivery_result.get('response_code'),
                'response_time_ms': delivery_result.get('response_time_ms'),
                'error_message': delivery_result.get('error_message')
            }, 'Delivery')
            
            # Track delivery failures for alerting
            if not delivery_result.get('success', False):
                xray_recorder.put_annotation('delivery_failure', True)
                xray_recorder.put_metadata('delivery_failure_details', {
                    'failure_reason': delivery_result.get('error_message', 'unknown'),
                    'retry_attempt': delivery_result.get('attempt', 1),
                    'tenant_id': trace_context['tenant_id'],
                    'destination_type': destination_type
                }, 'Failures')
        
        # Store delivery metrics
        self._store_trace_correlation(trace_context, 'destination_delivery', {
            'destination_type': destination_type,
            'success': delivery_result.get('success', False),
            'response_time_ms': delivery_result.get('response_time_ms', 0),
            'attempt_number': delivery_result.get('attempt', 1)
        })

    def _verify_tenant_isolation(self, trace_context: Dict[str, str], event_data: Dict[str, Any]) -> bool:
        """Verify that event data matches the expected tenant"""
        expected_tenant = trace_context['tenant_id']
        
        # Check various fields where tenant ID might appear
        tenant_fields = ['tenant_id', 'tenantId', 'account_id', 'customer_id']
        
        for field in tenant_fields:
            if field in event_data:
                if event_data[field] != expected_tenant:
                    return False
                    
        # Check nested detail object
        if 'detail' in event_data and isinstance(event_data['detail'], dict):
            for field in tenant_fields:
                if field in event_data['detail']:
                    if event_data['detail'][field] != expected_tenant:
                        return False
        
        return True

    def _verify_dynamodb_tenant_isolation(self, expected_tenant: str, item_data: Dict[str, Any]) -> bool:
        """Verify DynamoDB item belongs to expected tenant"""
        # Check partition key format
        pk = item_data.get('PK', '')
        if pk.startswith('TENANT#'):
            item_tenant = pk.split('#')[1].split('#')[0]  # Extract tenant from TENANT#<id>#...
            return item_tenant == expected_tenant
            
        # Check explicit tenant_id field
        if 'tenant_id' in item_data:
            return item_data['tenant_id'] == expected_tenant
            
        # If no clear tenant indicator, assume valid (but log warning)
        print(f"Warning: No clear tenant identifier in DynamoDB item for tenant {expected_tenant}")
        return True

    def _extract_tenant_from_item(self, item_data: Dict[str, Any]) -> str:
        """Extract tenant ID from DynamoDB item"""
        pk = item_data.get('PK', '')
        if pk.startswith('TENANT#'):
            return pk.split('#')[1].split('#')[0]
        return item_data.get('tenant_id', 'unknown')

    def _sanitize_destination_config(self, destination: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from destination configuration"""
        sanitized = destination.copy()
        
        sensitive_fields = ['api_key', 'secret', 'token', 'password', 'webhook_secret']
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
                
        return sanitized

    def _store_trace_correlation(self, trace_context: Dict[str, str], stage: str, metrics: Dict[str, Any]):
        """Store trace correlation data for cross-service analysis"""
        try:
            correlation_item = {
                'correlation_id': trace_context['correlation_id'],
                'stage_timestamp': f"{stage}#{datetime.utcnow().isoformat()}",
                'tenant_id': trace_context['tenant_id'],
                'submission_id': trace_context['submission_id'],
                'function_name': trace_context['function_name'],
                'stage': stage,
                'metrics': metrics,
                'environment': trace_context['environment'],
                'ttl': int(time.time()) + (30 * 24 * 60 * 60)  # 30 days TTL
            }
            
            # Store in DynamoDB for correlation analysis
            table = self.dynamodb.Table(self.correlation_table_name)
            table.put_item(Item=correlation_item)
            
        except Exception as e:
            print(f"Error storing trace correlation: {str(e)}")
            # Don't fail the main process due to tracing errors

    def get_trace_timeline(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Retrieve complete trace timeline for a correlation ID"""
        try:
            table = self.dynamodb.Table(self.correlation_table_name)
            response = table.query(
                KeyConditionExpression='correlation_id = :cid',
                ExpressionAttributeValues={':cid': correlation_id},
                ScanIndexForward=True  # Sort by timestamp
            )
            
            return response.get('Items', [])
            
        except Exception as e:
            print(f"Error retrieving trace timeline: {str(e)}")
            return []

    def analyze_processing_chain(self, correlation_id: str) -> Dict[str, Any]:
        """Analyze the complete processing chain for performance and issues"""
        timeline = self.get_trace_timeline(correlation_id)
        
        if not timeline:
            return {'error': 'No trace data found'}
        
        analysis = {
            'correlation_id': correlation_id,
            'total_stages': len(timeline),
            'tenant_id': timeline[0].get('tenant_id', 'unknown'),
            'submission_id': timeline[0].get('submission_id', 'unknown'),
            'processing_stages': [],
            'total_processing_time_ms': 0,
            'security_violations': [],
            'performance_issues': []
        }
        
        # Analyze each stage
        start_time = None
        for item in timeline:
            stage_data = {
                'stage': item.get('stage'),
                'timestamp': item.get('stage_timestamp', '').split('#')[1],
                'metrics': item.get('metrics', {}),
                'function_name': item.get('function_name')
            }
            
            # Track processing time
            if 'processing_time_ms' in item.get('metrics', {}):
                analysis['total_processing_time_ms'] += item['metrics']['processing_time_ms']
            
            # Check for security violations
            if not item.get('metrics', {}).get('tenant_isolation_valid', True):
                analysis['security_violations'].append({
                    'stage': item.get('stage'),
                    'violation': 'tenant_isolation_failure',
                    'timestamp': stage_data['timestamp']
                })
            
            # Check for performance issues
            stage_time = item.get('metrics', {}).get('processing_time_ms', 0)
            if stage_time > 1000:  # Over 1 second
                analysis['performance_issues'].append({
                    'stage': item.get('stage'),
                    'issue': 'slow_processing',
                    'duration_ms': stage_time,
                    'timestamp': stage_data['timestamp']
                })
            
            analysis['processing_stages'].append(stage_data)
        
        return analysis

# Usage example and decorator
def trace_form_bridge_operation(operation_name: str):
    """Decorator for tracing Form-Bridge operations"""
    def decorator(func):
        def wrapper(event, context):
            tracer = FormBridgeTracer()
            trace_context = tracer.start_trace_context(event, context)
            
            # Add operation-specific tracing
            with xray_recorder.in_subsegment(f'operation_{operation_name}'):
                xray_recorder.put_annotation('operation', operation_name)
                xray_recorder.put_annotation('correlation_id', trace_context['correlation_id'])
                
                try:
                    result = func(event, context, tracer, trace_context)
                    xray_recorder.put_annotation('operation_success', True)
                    return result
                    
                except Exception as e:
                    xray_recorder.put_annotation('operation_success', False)
                    xray_recorder.put_annotation('error_type', type(e).__name__)
                    xray_recorder.put_metadata('error_details', {
                        'error_message': str(e),
                        'correlation_id': trace_context['correlation_id'],
                        'operation': operation_name
                    }, 'Errors')
                    raise
                    
        return wrapper
    return decorator

# Example Lambda handlers with distributed tracing
@trace_form_bridge_operation('form_ingestion')
def form_ingestion_handler(event, context, tracer, trace_context):
    """Form ingestion handler with comprehensive tracing"""
    
    # Trace HMAC validation
    tracer.trace_hmac_validation(trace_context, {
        'valid': True,
        'tenant_id': trace_context['tenant_id']
    })
    
    # Trace EventBridge processing
    tracer.trace_eventbridge_processing(trace_context, event)
    
    # Trace DynamoDB persistence
    submission_data = {
        'PK': f"TENANT#{trace_context['tenant_id']}#SUBMISSION",
        'SK': trace_context['submission_id'],
        'tenant_id': trace_context['tenant_id'],
        'form_data': event.get('form_data', {}),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    tracer.trace_dynamodb_operations(
        trace_context, 
        'PUT_ITEM', 
        'FormBridge-Submissions',
        submission_data
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'correlation_id': trace_context['correlation_id'],
            'status': 'processed'
        })
    }

@trace_form_bridge_operation('event_processing')  
def event_processing_handler(event, context, tracer, trace_context):
    """Event processing handler with tracing"""
    
    # Process EventBridge event
    tracer.trace_eventbridge_processing(trace_context, event)
    
    # Simulate delivery to destinations
    destinations = event.get('destinations', [])
    
    for destination in destinations:
        delivery_result = {
            'success': True,
            'response_time_ms': 150,
            'response_code': 200
        }
        
        tracer.trace_destination_delivery(trace_context, destination, delivery_result)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'correlation_id': trace_context['correlation_id'],
            'destinations_processed': len(destinations)
        })
    }

if __name__ == "__main__":
    # Test the tracer
    tracer = FormBridgeTracer()
    
    # Mock context and event for testing
    class MockContext:
        function_name = 'test-function'
        aws_request_id = 'test-request-123'
    
    test_event = {
        'tenant_id': 'tenant_123',
        'form_data': {'name': 'Test User', 'email': 'test@example.com'},
        'correlation_id': str(uuid.uuid4())
    }
    
    context = MockContext()
    trace_context = tracer.start_trace_context(test_event, context)
    
    print(f"Created trace context: {trace_context}")
    
    # Test correlation storage and retrieval
    tracer._store_trace_correlation(trace_context, 'test_stage', {
        'processing_time_ms': 100,
        'test_metric': 'success'
    })
    
    timeline = tracer.get_trace_timeline(trace_context['correlation_id'])
    print(f"Retrieved timeline: {len(timeline)} items")
    
    analysis = tracer.analyze_processing_chain(trace_context['correlation_id'])
    print(f"Processing analysis: {json.dumps(analysis, indent=2)}")
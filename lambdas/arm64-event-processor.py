"""
ARM64 Event Processor Lambda - Multi-Tenant Form Processing
Optimized for AWS Graviton2 with advanced connection pooling

Features:
- 20% cost savings with ARM64 architecture  
- Advanced DynamoDB connection pooling
- Multi-tenant data isolation
- Idempotent processing with conditional writes
- Comprehensive error handling and retry logic
- Performance monitoring and metrics
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ConditionalCheckFailedException, ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="event-processor")
tracer = Tracer(service="event-processor") 
metrics = Metrics(namespace="FormBridge/Processing", service="event-processor")

# Global clients for ARM64 connection reuse optimization
_dynamodb = None
_eventbridge = None
_stepfunctions = None


@dataclass
class ProcessingMetrics:
    """Performance metrics tracking for ARM64 optimization"""
    events_processed: int = 0
    events_failed: int = 0
    duplicate_events: int = 0
    database_writes: int = 0
    stepfunction_executions: int = 0
    total_processing_time_ms: int = 0
    avg_processing_time_ms: float = 0.0


class ConnectionManager:
    """Optimized connection management for ARM64 Lambda functions"""
    
    @staticmethod
    def get_dynamodb():
        """Get cached DynamoDB resource with optimized settings"""
        global _dynamodb
        if _dynamodb is None:
            _dynamodb = boto3.resource(
                'dynamodb',
                region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                config=boto3.session.Config(
                    read_timeout=60,
                    connect_timeout=10,
                    retries={'max_attempts': 3, 'mode': 'adaptive'},
                    max_pool_connections=10
                )
            )
            logger.info("DynamoDB connection initialized")
        return _dynamodb
    
    @staticmethod
    def get_eventbridge():
        """Get cached EventBridge client"""
        global _eventbridge
        if _eventbridge is None:
            _eventbridge = boto3.client(
                'events',
                region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                config=boto3.session.Config(
                    read_timeout=30,
                    connect_timeout=5,
                    retries={'max_attempts': 3, 'mode': 'adaptive'}
                )
            )
            logger.info("EventBridge connection initialized")
        return _eventbridge
    
    @staticmethod 
    def get_stepfunctions():
        """Get cached Step Functions client"""
        global _stepfunctions
        if _stepfunctions is None:
            _stepfunctions = boto3.client(
                'stepfunctions',
                region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                config=boto3.session.Config(
                    read_timeout=60,
                    connect_timeout=10,
                    retries={'max_attempts': 3, 'mode': 'adaptive'}
                )
            )
            logger.info("Step Functions connection initialized")  
        return _stepfunctions


class MultiTenantEventProcessor:
    """ARM64 optimized event processor with tenant isolation"""
    
    def __init__(self):
        self.table_name = os.environ['DYNAMODB_TABLE_NAME']
        self.stepfunction_arn = os.environ.get('DELIVERY_STATE_MACHINE_ARN')
        self.metrics = ProcessingMetrics()
        
        # Get cached connections
        self.dynamodb = ConnectionManager.get_dynamodb()
        self.table = self.dynamodb.Table(self.table_name)
        self.eventbridge = ConnectionManager.get_eventbridge()
        self.stepfunctions = ConnectionManager.get_stepfunctions()
    
    @tracer.capture_method
    async def process_submission_event(self, event_detail: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process form submission with multi-tenant isolation
        
        Args:
            event_detail: EventBridge event detail containing submission data
            
        Returns:
            Processing result with metrics
        """
        start_time = time.time()
        
        try:
            # Extract and validate tenant information
            tenant_id = event_detail.get('tenant_id')
            submission_id = event_detail.get('submission_id')
            
            if not tenant_id or not submission_id:
                raise ValueError("Missing tenant_id or submission_id")
            
            # Validate tenant ID format for security
            if not self._validate_tenant_id(tenant_id):
                raise ValueError(f"Invalid tenant_id format: {tenant_id}")
            
            logger.info("Processing submission", extra={
                'tenant_id': tenant_id,
                'submission_id': submission_id
            })
            
            # Persist submission with idempotency
            persistence_result = await self._persist_submission(event_detail)
            
            if persistence_result['status'] == 'duplicate':
                logger.info("Duplicate submission detected", extra={
                    'tenant_id': tenant_id,
                    'submission_id': submission_id
                })
                self.metrics.duplicate_events += 1
                return {
                    'status': 'success',
                    'action': 'duplicate_ignored',
                    'submission_id': submission_id
                }
            
            # Trigger delivery workflow if destinations exist
            destinations = event_detail.get('destinations', [])
            if destinations and self.stepfunction_arn:
                await self._trigger_delivery_workflow(event_detail, destinations)
                self.metrics.stepfunction_executions += 1
            
            # Publish processing event for analytics
            await self._publish_processing_event(event_detail, 'processed')
            
            processing_time = int((time.time() - start_time) * 1000)
            self.metrics.total_processing_time_ms += processing_time
            self.metrics.events_processed += 1
            
            logger.info("Submission processed successfully", extra={
                'tenant_id': tenant_id,
                'submission_id': submission_id,
                'processing_time_ms': processing_time
            })
            
            return {
                'status': 'success', 
                'action': 'processed',
                'submission_id': submission_id,
                'processing_time_ms': processing_time
            }
            
        except Exception as e:
            self.metrics.events_failed += 1
            logger.error("Submission processing failed", extra={
                'error': str(e),
                'tenant_id': event_detail.get('tenant_id'),
                'submission_id': event_detail.get('submission_id')
            })
            
            # Publish failure event for monitoring
            await self._publish_processing_event(event_detail, 'failed', str(e))
            raise
    
    @tracer.capture_method
    async def _persist_submission(self, event_detail: Dict[str, Any]) -> Dict[str, Any]:
        """Persist submission to DynamoDB with tenant isolation"""
        tenant_id = event_detail['tenant_id']
        submission_id = event_detail['submission_id']
        
        # Create tenant-isolated DynamoDB item
        current_time = datetime.utcnow().isoformat() + 'Z'
        
        item = {
            # Partition key with tenant isolation
            'PK': f"TENANT#{tenant_id}",
            'SK': f"SUB#{submission_id}",
            
            # GSI for time-based queries
            'GSI1PK': f"TENANT#{tenant_id}",  
            'GSI1SK': f"TS#{event_detail.get('submitted_at', current_time)}",
            
            # Core submission data
            'tenant_id': tenant_id,
            'submission_id': submission_id,
            'form_id': event_detail.get('form_id'),
            'source_system': event_detail.get('source_system', 'unknown'),
            'submitted_at': event_detail.get('submitted_at', current_time),
            'processed_at': current_time,
            'status': 'received',
            'size_bytes': event_detail.get('size_bytes', 0),
            
            # Payload handling
            'payload': event_detail.get('payload', {}),
            'destinations': event_detail.get('destinations', []),
            'metadata': event_detail.get('metadata', {}),
            
            # Performance and monitoring
            'retry_count': 0,
            'schema_version': event_detail.get('schema_version', '1.0'),
            
            # TTL for data lifecycle (30 days default)
            'ttl': int(time.time()) + (30 * 24 * 3600)
        }
        
        try:
            # Conditional put for idempotency (prevents duplicates)
            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(PK) AND attribute_not_exists(SK)'
            )
            
            self.metrics.database_writes += 1
            
            logger.debug("Submission persisted", extra={
                'tenant_id': tenant_id,
                'submission_id': submission_id
            })
            
            return {'status': 'created', 'item': item}
            
        except ConditionalCheckFailedException:
            # Item already exists - this is expected for duplicate events
            logger.debug("Submission already exists", extra={
                'tenant_id': tenant_id,
                'submission_id': submission_id
            })
            return {'status': 'duplicate'}
            
        except ClientError as e:
            logger.error("DynamoDB persistence failed", extra={
                'error': str(e),
                'error_code': e.response.get('Error', {}).get('Code'),
                'tenant_id': tenant_id,
                'submission_id': submission_id
            })
            raise
    
    @tracer.capture_method
    async def _trigger_delivery_workflow(self, event_detail: Dict[str, Any], 
                                       destinations: List[str]) -> None:
        """Trigger Step Functions workflow for destination delivery"""
        try:
            # Prepare workflow input with tenant context
            workflow_input = {
                'tenant_id': event_detail['tenant_id'],
                'submission_id': event_detail['submission_id'],
                'submission_data': event_detail,
                'destinations': destinations,
                'workflow_start_time': datetime.utcnow().isoformat() + 'Z'
            }
            
            # Generate unique execution name with tenant prefix
            execution_name = f"delivery-{event_detail['tenant_id']}-{event_detail['submission_id']}-{int(time.time())}"
            
            # Start Step Functions execution
            response = self.stepfunctions.start_execution(
                stateMachineArn=self.stepfunction_arn,
                name=execution_name,
                input=json.dumps(workflow_input)
            )
            
            logger.info("Delivery workflow triggered", extra={
                'tenant_id': event_detail['tenant_id'],
                'submission_id': event_detail['submission_id'],
                'execution_arn': response['executionArn'],
                'destinations_count': len(destinations)
            })
            
        except Exception as e:
            logger.error("Failed to trigger delivery workflow", extra={
                'error': str(e),
                'tenant_id': event_detail.get('tenant_id'),
                'submission_id': event_detail.get('submission_id')
            })
            # Don't re-raise - submission was persisted successfully
    
    @tracer.capture_method 
    async def _publish_processing_event(self, original_event: Dict[str, Any], 
                                      status: str, error: Optional[str] = None) -> None:
        """Publish processing event for monitoring and analytics"""
        try:
            processing_event = {
                'tenant_id': original_event.get('tenant_id'),
                'submission_id': original_event.get('submission_id'),
                'processing_status': status,
                'processed_at': datetime.utcnow().isoformat() + 'Z',
                'processor_version': '2.0-arm64',
                'error': error
            }
            
            # Publish to EventBridge
            self.eventbridge.put_events(
                Entries=[{
                    'Source': 'formbridge.processor',
                    'DetailType': f'submission.{status}',
                    'Detail': json.dumps(processing_event),
                    'EventBusName': os.environ.get('EVENT_BUS_NAME', 'default')
                }]
            )
            
        except Exception as e:
            logger.warning("Failed to publish processing event", extra={'error': str(e)})
            # Don't re-raise - this is non-critical
    
    def _validate_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant ID format for security"""
        if not tenant_id or not isinstance(tenant_id, str):
            return False
            
        # Basic validation - customize based on your tenant ID format
        if not tenant_id.startswith('t_') or len(tenant_id) < 5:
            return False
            
        # Additional security checks
        if any(char in tenant_id for char in ['..', '/', '\\', '?', '#']):
            return False
            
        return True
    
    def get_metrics(self) -> ProcessingMetrics:
        """Get current processing metrics"""
        if self.metrics.events_processed > 0:
            self.metrics.avg_processing_time_ms = (
                self.metrics.total_processing_time_ms / self.metrics.events_processed
            )
        return self.metrics


# Global processor instance for container reuse
processor = MultiTenantEventProcessor()


@logger.inject_lambda_context(log_event=False)  # Don't log sensitive event data
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    ARM64 Lambda handler for EventBridge form submission processing
    
    Processes form submissions with multi-tenant isolation and idempotency
    """
    
    results = []
    
    try:
        # Handle EventBridge records (can be multiple)
        records = event.get('Records', [event])  # Support both direct and SQS events
        
        for record in records:
            try:
                # Extract event detail
                if 'eventbridge' in record or 'detail' in record:
                    # Direct EventBridge event
                    event_detail = record.get('detail', record)
                elif 'body' in record:
                    # SQS wrapped event
                    body = json.loads(record['body'])
                    event_detail = body.get('detail', body)
                else:
                    # Raw event detail
                    event_detail = record
                
                # Process the submission
                result = await processor.process_submission_event(event_detail)
                results.append(result)
                
            except Exception as e:
                logger.error("Record processing failed", extra={
                    'error': str(e),
                    'record': str(record)[:500]  # Truncate for logging
                })
                results.append({
                    'status': 'error',
                    'error': str(e),
                    'submission_id': event_detail.get('submission_id', 'unknown')
                })
        
        # Publish performance metrics
        await _publish_performance_metrics(processor.get_metrics())
        
        # Determine overall status
        success_count = sum(1 for r in results if r['status'] == 'success')
        total_count = len(results)
        
        logger.info("Batch processing complete", extra={
            'total_records': total_count,
            'successful_records': success_count,
            'failed_records': total_count - success_count
        })
        
        return {
            'statusCode': 200 if success_count == total_count else 207,
            'body': json.dumps({
                'message': 'Processing complete',
                'total_records': total_count,
                'successful_records': success_count,
                'results': results
            })
        }
        
    except Exception as e:
        logger.exception("Lambda handler error")
        metrics.add_metric(name="HandlerErrors", unit=MetricUnit.Count, value=1)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal processing error',
                'message': str(e)
            })
        }


async def _publish_performance_metrics(perf_metrics: ProcessingMetrics) -> None:
    """Publish ARM64 performance metrics to CloudWatch"""
    try:
        cloudwatch = boto3.client('cloudwatch')
        
        metric_data = [
            {
                'MetricName': 'EventsProcessed',
                'Value': perf_metrics.events_processed,
                'Unit': 'Count'
            },
            {
                'MetricName': 'EventsFailed', 
                'Value': perf_metrics.events_failed,
                'Unit': 'Count'
            },
            {
                'MetricName': 'DuplicateEvents',
                'Value': perf_metrics.duplicate_events,
                'Unit': 'Count'
            },
            {
                'MetricName': 'DatabaseWrites',
                'Value': perf_metrics.database_writes,
                'Unit': 'Count'
            }
        ]
        
        if perf_metrics.avg_processing_time_ms > 0:
            metric_data.append({
                'MetricName': 'AvgProcessingTime',
                'Value': perf_metrics.avg_processing_time_ms,
                'Unit': 'Milliseconds'
            })
        
        cloudwatch.put_metric_data(
            Namespace='FormBridge/ARM64Performance',
            MetricData=metric_data
        )
        
    except Exception as e:
        logger.warning("Failed to publish performance metrics", extra={'error': str(e)})


if __name__ == "__main__":
    # Local testing
    import asyncio
    
    test_event = {
        'detail': {
            'tenant_id': 't_test123',
            'submission_id': str(uuid.uuid4()),
            'form_id': 'contact_form',
            'submitted_at': datetime.utcnow().isoformat() + 'Z',
            'payload': {
                'name': 'Test User',
                'email': 'test@example.com'
            },
            'destinations': ['rest:webhook1', 'email:admin'],
            'metadata': {'source': 'website'}
        }
    }
    
    result = lambda_handler(test_event, {})
    print(json.dumps(result, indent=2))
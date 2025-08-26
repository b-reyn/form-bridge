"""
EventBridge Optimized Publisher
Multi-tenant form processing with 2025 best practices

Features:
- Intelligent batching for high-volume scenarios
- S3 reference pattern for large payloads
- Comprehensive error handling and retry logic
- Custom CloudWatch metrics
- Tenant isolation validation
"""

import asyncio
import boto3
import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import logging
logger = logging.getLogger(__name__)


class PayloadType(Enum):
    INLINE = "inline"
    S3_REFERENCE = "s3_reference"


@dataclass
class EventMetrics:
    events_published: int = 0
    events_failed: int = 0
    s3_references_created: int = 0
    batch_count: int = 0
    total_processing_time_ms: int = 0
    payload_size_saved_bytes: int = 0


class S3PayloadManager:
    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.s3_client = boto3.client('s3', region_name=region)
        self.bucket_name = bucket_name
        
    async def store_large_payload(self, tenant_id: str, submission_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Store large payload in S3 and return reference"""
        try:
            payload_json = json.dumps(payload, separators=(',', ':'))
            payload_bytes = payload_json.encode('utf-8')
            payload_size = len(payload_bytes)
            
            # Create S3 key with tenant isolation
            s3_key = f"submissions/{tenant_id}/{submission_id}/payload.json"
            
            # Add metadata for better management
            metadata = {
                'tenant-id': tenant_id,
                'submission-id': submission_id,
                'created-at': datetime.utcnow().isoformat(),
                'payload-size': str(payload_size)
            }
            
            # Upload to S3 with encryption
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=payload_bytes,
                ContentType='application/json',
                Metadata=metadata,
                ServerSideEncryption='AES256',
                # Add tenant-based tagging for cost tracking
                Tagging=f'tenant_id={tenant_id}&type=form_payload'
            )
            
            return {
                "type": PayloadType.S3_REFERENCE.value,
                "bucket": self.bucket_name,
                "key": s3_key,
                "size": payload_size,
                "checksum": hashlib.sha256(payload_bytes).hexdigest()
            }
            
        except Exception as e:
            logger.error(f"Failed to store payload in S3: {e}")
            raise


class OptimizedEventPublisher:
    def __init__(
        self, 
        event_bus_name: str,
        s3_bucket_name: str,
        region: str = "us-east-1",
        batch_size_limit: int = 10,
        batch_timeout_seconds: float = 5.0,
        size_threshold_bytes: int = 200000  # 200KB
    ):
        self.events_client = boto3.client('events', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.event_bus_name = event_bus_name
        self.batch_size_limit = batch_size_limit
        self.batch_timeout_seconds = batch_timeout_seconds
        self.size_threshold_bytes = size_threshold_bytes
        
        # S3 manager for large payloads
        self.s3_manager = S3PayloadManager(s3_bucket_name, region)
        
        # Batch management
        self.batch: List[Dict] = []
        self.last_flush_time = time.time()
        self.metrics = EventMetrics()
        
        # Event schema version
        self.schema_version = "2.0"
        
    async def publish_form_submission(
        self, 
        tenant_id: str, 
        submission: Dict[str, Any],
        source: str = "formbridge.ingest"
    ) -> str:
        """
        Publish form submission event with intelligent payload management
        Returns event ID for tracking
        """
        start_time = time.time()
        
        try:
            # Validate tenant_id format
            if not self._validate_tenant_id(tenant_id):
                raise ValueError(f"Invalid tenant_id format: {tenant_id}")
            
            # Create canonical event structure
            event = await self._create_canonical_event(tenant_id, submission, source)
            
            # Add to batch
            await self._add_to_batch(event)
            
            # Check if we should flush the batch
            if self._should_flush_batch():
                await self._flush_batch()
            
            processing_time = int((time.time() - start_time) * 1000)
            self.metrics.total_processing_time_ms += processing_time
            
            return event['detail']['submission_id']
            
        except Exception as e:
            self.metrics.events_failed += 1
            logger.error(f"Failed to publish event for tenant {tenant_id}: {e}")
            raise
    
    async def _create_canonical_event(
        self, 
        tenant_id: str, 
        submission: Dict[str, Any], 
        source: str
    ) -> Dict[str, Any]:
        """Create standardized event structure with payload optimization"""
        
        submission_id = submission.get('submission_id') or self._generate_submission_id()
        
        # Check payload size and optimize if needed
        payload_json = json.dumps(submission.get('payload', {}), separators=(',', ':'))
        payload_size = len(payload_json.encode('utf-8'))
        
        if payload_size > self.size_threshold_bytes:
            # Store in S3 and create reference
            payload_ref = await self.s3_manager.store_large_payload(
                tenant_id, submission_id, submission['payload']
            )
            self.metrics.s3_references_created += 1
            self.metrics.payload_size_saved_bytes += payload_size - len(json.dumps(payload_ref))
        else:
            # Keep payload inline
            payload_ref = {
                "type": PayloadType.INLINE.value,
                "data": submission['payload'],
                "size": payload_size
            }
        
        # Create event detail
        event_detail = {
            'tenant_id': tenant_id,
            'submission_id': submission_id,
            'form_id': submission.get('form_id'),
            'schema_version': self.schema_version,
            'submitted_at': submission.get('submitted_at', datetime.utcnow().isoformat()),
            'ip': submission.get('ip'),
            'source_system': submission.get('source', 'unknown'),
            'size_bytes': payload_size,
            'payload': payload_ref,
            'destinations': submission.get('destinations', []),
            'retry_count': 0,
            'metadata': submission.get('metadata', {})
        }
        
        return {
            'Source': source,
            'DetailType': 'submission.received',
            'Detail': json.dumps(event_detail, separators=(',', ':')),
            'EventBusName': self.event_bus_name,
            'Time': datetime.utcnow()
        }
    
    async def _add_to_batch(self, event: Dict[str, Any]):
        """Add event to current batch"""
        self.batch.append(event)
    
    def _should_flush_batch(self) -> bool:
        """Determine if batch should be flushed"""
        if not self.batch:
            return False
        
        # Check batch size limit
        if len(self.batch) >= self.batch_size_limit:
            return True
        
        # Check timeout
        if time.time() - self.last_flush_time > self.batch_timeout_seconds:
            return True
        
        # Check total batch size (EventBridge has 256KB limit per entry)
        total_size = sum(len(json.dumps(event).encode('utf-8')) for event in self.batch)
        if total_size > 240000:  # 240KB safety margin
            return True
        
        return False
    
    async def _flush_batch(self):
        """Flush current batch to EventBridge"""
        if not self.batch:
            return
        
        batch_to_send = self.batch.copy()
        self.batch = []
        self.last_flush_time = time.time()
        
        try:
            response = await self._put_events_with_retry(batch_to_send)
            await self._handle_put_events_response(response, batch_to_send)
            
            self.metrics.events_published += len(batch_to_send)
            self.metrics.batch_count += 1
            
        except Exception as e:
            logger.error(f"Failed to flush batch: {e}")
            # Fallback: try individual event publishing
            await self._fallback_individual_publish(batch_to_send)
    
    async def _put_events_with_retry(
        self, 
        events: List[Dict], 
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Put events with exponential backoff retry"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = self.events_client.put_events(Entries=events)
                return response
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = (2 ** attempt) * 0.1  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    logger.warning(f"EventBridge put_events retry {attempt + 1}/{max_retries}: {e}")
        
        raise last_exception
    
    async def _handle_put_events_response(
        self, 
        response: Dict[str, Any], 
        original_events: List[Dict]
    ):
        """Handle EventBridge put_events response and manage failures"""
        if response.get('FailedEntryCount', 0) == 0:
            return  # All events succeeded
        
        # Process failed entries
        failed_events = []
        for i, entry in enumerate(response['Entries']):
            if 'ErrorCode' in entry:
                logger.error(
                    f"Event failed: {entry['ErrorCode']} - {entry.get('ErrorMessage', 'No message')}"
                )
                failed_events.append(original_events[i])
        
        self.metrics.events_failed += len(failed_events)
        
        # Implement DLQ or retry logic for failed events
        await self._handle_failed_events(failed_events)
    
    async def _handle_failed_events(self, failed_events: List[Dict]):
        """Handle events that failed to publish"""
        # In a production system, you would:
        # 1. Send to a DLQ (SQS)
        # 2. Write to DynamoDB for later retry
        # 3. Send to a monitoring system
        
        logger.error(f"Handling {len(failed_events)} failed events")
        # Implementation depends on your DLQ strategy
        pass
    
    async def _fallback_individual_publish(self, events: List[Dict]):
        """Fallback: publish events individually if batch fails"""
        logger.warning(f"Falling back to individual event publishing for {len(events)} events")
        
        for event in events:
            try:
                response = self.events_client.put_events(Entries=[event])
                if response.get('FailedEntryCount', 0) > 0:
                    self.metrics.events_failed += 1
                else:
                    self.metrics.events_published += 1
            except Exception as e:
                logger.error(f"Individual event publish failed: {e}")
                self.metrics.events_failed += 1
    
    async def flush_remaining_events(self):
        """Force flush any remaining events in batch"""
        if self.batch:
            await self._flush_batch()
    
    async def publish_custom_metrics(self):
        """Publish custom CloudWatch metrics"""
        if self.metrics.events_published == 0 and self.metrics.events_failed == 0:
            return  # No metrics to publish
        
        try:
            metric_data = [
                {
                    'MetricName': 'EventsPublished',
                    'Value': self.metrics.events_published,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'EventBus', 'Value': self.event_bus_name}
                    ]
                },
                {
                    'MetricName': 'EventsFailed',
                    'Value': self.metrics.events_failed,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'EventBus', 'Value': self.event_bus_name}
                    ]
                },
                {
                    'MetricName': 'S3ReferencesCreated',
                    'Value': self.metrics.s3_references_created,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'EventBus', 'Value': self.event_bus_name}
                    ]
                },
                {
                    'MetricName': 'BatchesPublished',
                    'Value': self.metrics.batch_count,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'EventBus', 'Value': self.event_bus_name}
                    ]
                }
            ]
            
            if self.metrics.events_published > 0:
                avg_processing_time = self.metrics.total_processing_time_ms / self.metrics.events_published
                metric_data.append({
                    'MetricName': 'AverageProcessingTime',
                    'Value': avg_processing_time,
                    'Unit': 'Milliseconds',
                    'Dimensions': [
                        {'Name': 'EventBus', 'Value': self.event_bus_name}
                    ]
                })
            
            self.cloudwatch_client.put_metric_data(
                Namespace='FormBridge/EventBridge',
                MetricData=metric_data
            )
            
            # Reset metrics after publishing
            self.metrics = EventMetrics()
            
        except Exception as e:
            logger.error(f"Failed to publish custom metrics: {e}")
    
    def _validate_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant_id format"""
        if not tenant_id or not isinstance(tenant_id, str):
            return False
        
        # Basic validation - customize based on your tenant ID format
        if not tenant_id.startswith('t_') or len(tenant_id) < 5:
            return False
        
        return True
    
    def _generate_submission_id(self) -> str:
        """Generate unique submission ID (UUID v7 for time-ordered sorting)"""
        # This is a simplified version - use proper UUID v7 library in production
        import uuid
        return str(uuid.uuid4())


# Example usage function for Lambda
async def lambda_handler(event, context):
    """Lambda handler example using the optimized publisher"""
    
    publisher = OptimizedEventPublisher(
        event_bus_name=os.environ['EVENT_BUS_NAME'],
        s3_bucket_name=os.environ['S3_BUCKET_NAME']
    )
    
    try:
        # Process form submission
        body = json.loads(event.get('body', '{}'))
        tenant_id = event.get('requestContext', {}).get('authorizer', {}).get('tenant_id')
        
        if not tenant_id:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Tenant ID required'})
            }
        
        # Publish event
        submission_id = await publisher.publish_form_submission(tenant_id, body)
        
        # Flush any remaining events
        await publisher.flush_remaining_events()
        
        # Publish metrics
        await publisher.publish_custom_metrics()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'submission_id': submission_id,
                'message': 'Form submission processed successfully'
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }


if __name__ == "__main__":
    # Example usage
    import os
    import asyncio
    
    async def main():
        publisher = OptimizedEventPublisher(
            event_bus_name="form-bridge-bus",
            s3_bucket_name="form-bridge-payloads"
        )
        
        # Example submission
        submission = {
            'form_id': 'contact_us',
            'submitted_at': datetime.utcnow().isoformat(),
            'payload': {
                'name': 'John Doe',
                'email': 'john@example.com',
                'message': 'Hello from the form!'
            },
            'destinations': ['rest:webhook1', 'db:dynamo']
        }
        
        submission_id = await publisher.publish_form_submission('t_example123', submission)
        print(f"Published submission: {submission_id}")
        
        await publisher.flush_remaining_events()
        await publisher.publish_custom_metrics()
    
    asyncio.run(main())
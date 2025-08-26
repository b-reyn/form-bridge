# EventBridge Architect Strategy Document

*Last Updated: 2025-08-26*
*Agent: eventbridge-architect*

## Current Best Practices (Research Date: 2025-08-26)

### Industry Standards (2025 Updates)
- **Event-driven over batch processing** for real-time responsiveness
- **Loose coupling** between services using event buses
- **Schema registry** for event versioning and evolution
- **Content-based routing** using event pattern matching
- **Dead letter queues** for all critical event targets
- **Event replay capability** for debugging and recovery
- **Event Pipes** for no-code integration patterns (DynamoDB Streams → EventBridge)
- **Multi-tenant event isolation** using content-based filtering

### AWS EventBridge Specific (2025)
- Use **single custom event bus** with rules for tenant isolation (more cost-effective)
- Implement **archive and replay** with 30-day retention minimum
- Maximum event size: **256KB** (use S3 references for larger payloads)
- Rate limit: **10,000 PutEvents/second per region**
- Use **Express Step Functions** as targets for complex workflows
- Enable **schema discovery** for automatic documentation
- **Batch PutEvents** (up to 10 events) for high-volume scenarios
- **Enhanced CloudWatch metrics** for deep monitoring (2024+ feature)
- **EventBridge Pipes** for DynamoDB Streams → WebSocket real-time updates
- **API Destinations** for webhook integrations with automatic retry
- **Custom retry policies** per target type (different for Lambda vs SQS vs external APIs)

## Project-Specific Patterns

### What Works
- **Pattern**: Tenant-scoped event patterns
  - Context: Multi-tenant form submissions
  - Implementation: Include `tenant_id` in every event detail
  - Result: Clean tenant isolation and filtering

- **Pattern**: Separate rules for persist vs deliver
  - Context: Different SLAs for storage vs delivery
  - Implementation: Two EventBridge rules from same event
  - Result: Independent scaling and error handling

### What Doesn't Work
- **Anti-pattern**: Large payloads in events
  - Issue: 256KB limit causes failures
  - Alternative: Store in S3, pass reference in event
  - Learning: Events should be pointers, not containers

## Decision Log

| Date | Decision | Rationale | Outcome | 
|------|----------|-----------|---------|
| 2025-08-26 | Use single event bus with rules | Simpler than multiple buses | ✅ Confirmed optimal |
| 2025-08-26 | Archive all events for 30 days | Replay capability for debugging | Cost ~$1/million events |
| 2025-08-26 | Optimize event structure for 256KB limit | Prevent payload size failures | Use S3 refs for large payloads |
| 2025-08-26 | Implement batching for high volume | Reduce API calls and improve throughput | 10 events per batch max |
| 2025-08-26 | Separate rules for persist vs deliver | Different SLAs and error handling | Parallel processing paths |

## Knowledge Base

### Common Issues & Solutions
1. **Issue**: Failed event delivery to Lambda
   - **Solution**: Configure DLQ and retry policy per target type
   - **Prevention**: Set appropriate timeout and memory, use exponential backoff

2. **Issue**: Event pattern not matching
   - **Solution**: Test patterns with EventBridge Sandbox
   - **Prevention**: Use exact field matching, avoid complex patterns

3. **Issue**: Large payload size (>256KB)
   - **Solution**: Store in S3, pass reference in event detail
   - **Prevention**: Check payload size before PutEvents

4. **Issue**: High-volume event throttling
   - **Solution**: Implement batching (10 events per PutEvents call)
   - **Prevention**: Monitor PutEvents rate limits

5. **Issue**: DLQ messages not being processed
   - **Solution**: Implement DLQ monitoring and replay mechanism
   - **Prevention**: Set up CloudWatch alarms on DLQ depth

### Code Snippets & Templates

#### Optimized Event Structure (2025)
```python
# Standard event structure for form submissions with S3 optimization
def create_form_event(tenant_id: str, submission: dict, s3_bucket: str = None) -> dict:
    # Check payload size and use S3 reference if needed
    payload_size = len(json.dumps(submission).encode('utf-8'))
    
    if payload_size > 200000:  # 200KB threshold (leave buffer for other fields)
        s3_key = f"submissions/{tenant_id}/{submission['id']}/payload.json"
        # Upload to S3 would happen here
        payload_ref = {
            "type": "s3_reference",
            "bucket": s3_bucket,
            "key": s3_key,
            "size": payload_size
        }
        submission_data = payload_ref
    else:
        submission_data = submission
    
    return {
        'Source': 'formbridge.ingest',
        'DetailType': 'submission.received',
        'Detail': json.dumps({
            'tenant_id': tenant_id,
            'submission_id': submission['id'],
            'schema_version': '2.0',  # Updated version
            'timestamp': datetime.utcnow().isoformat(),
            'payload': submission_data,
            'size_bytes': payload_size,
            'destinations': submission.get('destinations', [])
        }),
        'EventBusName': os.environ['EVENT_BUS_NAME']
    }
```

#### Batched Event Publisher (High Volume)
```python
# High-volume event publisher with batching
import boto3
import json
from typing import List, Dict, Any
from datetime import datetime

class EventBridgePublisher:
    def __init__(self, event_bus_name: str):
        self.client = boto3.client('events')
        self.event_bus_name = event_bus_name
        self.batch = []
        self.batch_timeout = 5.0  # seconds
        
    def publish_event(self, source: str, detail_type: str, detail: Dict[str, Any]):
        entry = {
            'Source': source,
            'DetailType': detail_type,
            'Detail': json.dumps(detail),
            'EventBusName': self.event_bus_name,
            'Time': datetime.utcnow()
        }
        
        self.batch.append(entry)
        
        if len(self.batch) >= 10:  # Max batch size
            self._flush_batch()
    
    def _flush_batch(self):
        if not self.batch:
            return
            
        try:
            response = self.client.put_events(Entries=self.batch)
            
            # Check for failed entries
            if response['FailedEntryCount'] > 0:
                failed_entries = [
                    entry for entry in response['Entries']
                    if 'ErrorCode' in entry
                ]
                # Log failed entries for retry
                for failed in failed_entries:
                    print(f"Failed to publish event: {failed['ErrorCode']}")
            
            self.batch = []
            
        except Exception as e:
            print(f"Error publishing event batch: {e}")
            # Implement retry logic or DLQ here
```

#### DLQ Configuration Template
```python
# CloudFormation/CDK template for proper DLQ configuration
dlq_config_per_target = {
    "lambda": {
        "retry_policy": {
            "maximum_retry_attempts": 3,
            "maximum_event_age": 3600  # 1 hour
        },
        "dlq_config": {
            "message_retention_period": 1209600,  # 14 days
            "visibility_timeout": 60
        }
    },
    "step_functions": {
        "retry_policy": {
            "maximum_retry_attempts": 2,
            "maximum_event_age": 7200  # 2 hours
        },
        "dlq_config": {
            "message_retention_period": 1209600,  # 14 days
            "visibility_timeout": 300  # 5 minutes
        }
    },
    "api_destination": {
        "retry_policy": {
            "maximum_retry_attempts": 5,
            "maximum_event_age": 86400  # 24 hours
        },
        "dlq_config": {
            "message_retention_period": 1209600,  # 14 days
            "visibility_timeout": 900  # 15 minutes
        }
    }
}
```

### Integration Patterns (2025)
- **EventBridge + Lambda**: Direct invocation for simple processing
- **EventBridge + Step Functions Express**: Complex workflows with high concurrency
- **EventBridge + SQS**: Buffer for rate-limited downstream services
- **EventBridge + API Destinations**: External webhook integrations with automatic retry
- **EventBridge Pipes + DynamoDB Streams**: Real-time data synchronization
- **EventBridge + WebSocket API**: Real-time dashboard updates via DynamoDB Streams
- **EventBridge + SNS Fan-out**: Multi-protocol notification delivery
- **EventBridge + Kinesis**: High-throughput event streaming and analytics

## Performance Insights

### Benchmarks
- PutEvents latency: ~25ms p99
- Rule evaluation: < 1ms
- Target invocation: < 50ms for Lambda

### Cost Optimization
- Custom events: $1.00 per million
- Archive: $0.10 per million archived
- Replay: $0.03 per million replayed

## Security Considerations

### Security Patterns
- Resource-based policies for cross-account events
- IAM conditions for tenant-scoped access
- Encryption at rest for archived events

## Testing Strategies

### Effective Test Patterns
- Use EventBridge Sandbox for pattern testing
- Local testing with LocalStack
- Integration tests with real AWS services

## Future Improvements

### Short-term (Phase 3 - EventBridge Optimization)
- [ ] Implement S3 reference pattern for large payloads (>200KB)
- [ ] Configure proper DLQ per target type with monitoring
- [ ] Create batched event publisher for high-volume scenarios
- [ ] Set up event replay mechanism with 30-day archive
- [ ] Add schema versioning (v2.0 with S3 references)
- [ ] Implement custom CloudWatch metrics and dashboards

### Medium-term (Phase 4-5)
- [ ] EventBridge Pipes for DynamoDB Streams → WebSocket real-time updates
- [ ] Parallel Step Functions branches for multiple destinations
- [ ] Advanced event filtering optimization
- [ ] API Destinations for external webhook integrations
- [ ] Cross-region event replication for disaster recovery

### Long-term (Post-MVP)
- [ ] Event sourcing for complete audit trail
- [ ] Machine learning on event patterns for anomaly detection
- [ ] Multi-region active-active event processing
- [ ] Advanced event analytics and insights dashboard

## Metrics & Success Indicators

### Key Metrics
- Event processing rate: 1000/sec → 10,000/sec
- Failed invocations: < 0.01%
- Event latency: < 100ms p99

---

*This is a living document. Updated with FormBridge architecture review and optimization recommendations.*

## Architecture Review Findings (2025-08-26)

### Critical Optimizations Identified (Updated 2025-08-26)
1. **Event Size Management**: Implement S3 references for payloads >200KB (CRITICAL)
2. **Batching Strategy**: Use 10-event batches with optimized timeout (HIGH)
3. **Real-time Updates**: EventBridge Pipes → DynamoDB Streams → WebSocket API (MEDIUM)
4. **Error Isolation**: Separate DLQs per target type with proper retry policies (HIGH)
5. **Performance Monitoring**: Enhanced CloudWatch metrics for EventBridge operations (HIGH)
6. **Multi-tenant Filtering**: Optimize event patterns to reduce Lambda invocations (MEDIUM)
7. **Schema Evolution**: Implement v2.0 event schema with backward compatibility (MEDIUM)
8. **Cost Optimization**: Event filtering to reduce unnecessary target invocations (LOW)

### Implementation Priority (Phase-Corrected)
1. **Phase 3 (EventBridge Optimization)**: 
   - S3 reference pattern for large payloads
   - Proper DLQ configuration per target type
   - Batched event publisher with error handling
   - Event replay capabilities
2. **Phase 4 (Real-time Features)**:
   - EventBridge Pipes for real-time dashboard updates
   - Parallel Step Functions delivery branches
   - Advanced monitoring and alerting
3. **Phase 5 (Advanced Features)**:
   - Cross-region replication
   - ML-based event pattern analysis
   - Advanced analytics dashboard

### 2025 EventBridge Cost Optimization Insights
- **Custom Events**: $1.00 per million events
- **Archive Storage**: $0.10 per GB-month (30-day retention ~$3-5/month for MVP)
- **Event Replay**: $0.03 per million replayed events
- **API Destinations**: Additional $1.00 per million requests
- **EventBridge Pipes**: $0.40 per million events processed
- **Target Invocation Optimization**: 30-50% cost savings through event filtering
# EventBridge Architecture Implementation Plan 2025

*Document Version: 1.0*  
*Created: 2025-08-26*  
*EventBridge Architect: claude-eventbridge-architect*

## Executive Summary

This document outlines the comprehensive EventBridge architecture implementation for the Form-Bridge multi-tenant serverless form processing system. Based on 2025 best practices and the comprehensive improvement analysis, this plan addresses critical optimizations for cost efficiency, reliability, and scalability.

## Current State Analysis

### Existing Architecture Strengths
- Single EventBridge custom bus design (cost-effective)
- Separate rules for persistence and delivery (good separation of concerns)
- DLQ configuration planned for reliability
- Integration with Step Functions Express for complex workflows

### Critical Gaps Identified
1. **Event Size Management**: No handling for payloads >256KB
2. **DLQ Configuration**: Generic DLQ setup, not optimized per target type
3. **High-Volume Processing**: No batching strategy for event publishing
4. **Real-time Updates**: No dashboard update mechanism
5. **Event Replay**: Archive configured but no replay implementation
6. **Monitoring**: Basic CloudWatch metrics only

## Implementation Phases

### Phase 3: EventBridge Core Optimizations (Week 3-4)

#### 3.1 Event Structure Optimization (Priority: CRITICAL)

**Challenge**: Current events may exceed 256KB limit with large form submissions
**Solution**: Implement S3 reference pattern for large payloads

```python
# Event Structure v2.0 with S3 optimization
{
  "version": "0",
  "id": "uuid-v7-event-id", 
  "detail-type": "submission.received",
  "source": "formbridge.ingest",
  "account": "123456789012",
  "time": "2025-08-26T12:00:00Z",
  "region": "us-east-1",
  "detail": {
    "tenant_id": "t_abc123",
    "submission_id": "01J7R3S8B2JD2VEXAMPLE",
    "form_id": "contact_us",
    "schema_version": "2.0",
    "submitted_at": "2025-08-26T12:00:00Z",
    "ip": "203.0.113.5",
    "size_bytes": 245760,
    "payload": {
      "type": "s3_reference",  // or "inline" for small payloads
      "bucket": "form-bridge-payloads-prod",
      "key": "submissions/t_abc123/01J7R3S8B2JD2VEXAMPLE/payload.json",
      "size": 245760
    },
    "destinations": ["rest:webhookA", "db:dynamo"],
    "retry_count": 0
  }
}
```

**Implementation Steps:**
1. Create S3 bucket for large payload storage
2. Implement payload size detection in ingest Lambda
3. Upload large payloads to S3 with proper tenant isolation
4. Update event consumers to handle S3 references
5. Add S3 cleanup mechanism for processed submissions

**Success Metrics:**
- All events under 256KB limit
- Large payloads (>200KB) stored in S3
- No EventBridge payload size errors
- S3 storage costs <$5/month for MVP volume

#### 3.2 DLQ Configuration Per Target Type (Priority: HIGH)

**Challenge**: One-size-fits-all DLQ configuration doesn't match target-specific needs
**Solution**: Implement target-specific DLQ and retry policies

```yaml
# Target-specific DLQ Configuration
DLQ_Configurations:
  Lambda_Persist:
    retry_policy:
      maximum_retry_attempts: 3
      maximum_event_age: 3600  # 1 hour - fast failure for persistence
    dlq_config:
      message_retention_period: 86400  # 1 day
      visibility_timeout: 60
    
  StepFunctions_Deliver:
    retry_policy:
      maximum_retry_attempts: 2
      maximum_event_age: 7200  # 2 hours - allow for delivery retries
    dlq_config:
      message_retention_period: 604800  # 7 days
      visibility_timeout: 300
  
  API_Destinations:
    retry_policy:
      maximum_retry_attempts: 5
      maximum_event_age: 86400  # 24 hours - external services need more retries
    dlq_config:
      message_retention_period: 1209600  # 14 days
      visibility_timeout: 900
```

**CloudWatch Alarms:**
- DLQ depth > 10 messages (immediate alert)
- Failed invocation rate > 1% (warning)
- DLQ age > 1 hour for critical targets (urgent)

#### 3.3 Batched Event Publisher (Priority: HIGH)

**Challenge**: High-volume form submissions create excessive API calls
**Solution**: Implement intelligent batching with fallback mechanisms

```python
class OptimizedEventPublisher:
    def __init__(self, event_bus_name: str):
        self.client = boto3.client('events')
        self.event_bus_name = event_bus_name
        self.batch = []
        self.batch_size_limit = 10
        self.batch_timeout = 5.0
        self.last_flush = time.time()
    
    async def publish_event(self, event: Dict):
        self.batch.append(self._format_event(event))
        
        # Flush conditions
        should_flush = (
            len(self.batch) >= self.batch_size_limit or
            time.time() - self.last_flush > self.batch_timeout or
            self._batch_size_bytes() > 240000  # 240KB safety margin
        )
        
        if should_flush:
            await self._flush_batch()
    
    async def _flush_batch(self):
        if not self.batch:
            return
        
        try:
            response = self.client.put_events(Entries=self.batch)
            await self._handle_failed_entries(response)
            
        except Exception as e:
            # Fallback to individual event publishing
            await self._fallback_individual_publish()
        finally:
            self.batch = []
            self.last_flush = time.time()
```

**Performance Targets:**
- 90% reduction in PutEvents API calls
- <500ms latency for batch publishing
- 99.9% event delivery success rate
- Cost reduction: ~$10-20/month for high-volume tenants

#### 3.4 Event Replay Implementation (Priority: MEDIUM)

**Challenge**: No mechanism to replay events for debugging or recovery
**Solution**: Implement comprehensive replay system with filtering

```python
class EventReplayManager:
    def __init__(self, archive_name: str, event_bus_name: str):
        self.events_client = boto3.client('events')
        self.archive_name = archive_name
        self.event_bus_name = event_bus_name
    
    def replay_events(
        self, 
        start_time: datetime, 
        end_time: datetime,
        tenant_filter: str = None,
        event_pattern: Dict = None
    ):
        """Replay events with optional filtering"""
        replay_name = f"replay-{tenant_filter}-{int(time.time())}"
        
        replay_config = {
            'ReplayName': replay_name,
            'EventSourceArn': f'arn:aws:events:us-east-1:123456789012:archive/{self.archive_name}',
            'EventStartTime': start_time,
            'EventEndTime': end_time,
            'Destination': {
                'Arn': f'arn:aws:events:us-east-1:123456789012:event-bus/{self.event_bus_name}',
                'FilterArns': []
            }
        }
        
        if event_pattern:
            replay_config['Destination']['FilterArns'] = [
                self._create_replay_rule(event_pattern)
            ]
        
        response = self.events_client.start_replay(**replay_config)
        return response['ReplayArn']
```

### Phase 4: Real-time Dashboard Integration (Week 5-6)

#### 4.1 EventBridge Pipes for Real-time Updates (Priority: MEDIUM)

**Architecture**: EventBridge → DynamoDB → DynamoDB Streams → EventBridge Pipes → WebSocket API

```python
# EventBridge Pipe Configuration
pipe_config = {
    "Name": "submission-realtime-updates",
    "Source": "arn:aws:dynamodb:us-east-1:123456789012:table/FormBridge/stream/*",
    "Target": "arn:aws:execute-api:us-east-1:123456789012:*/POST/@connections/*",
    "RoleArn": "arn:aws:iam::123456789012:role/EventBridgePipeRole",
    "SourceParameters": {
        "DynamoDBStreamParameters": {
            "StartingPosition": "LATEST",
            "BatchSize": 1,
            "MaximumBatchingWindowInSeconds": 1
        },
        "FilterCriteria": {
            "Filters": [
                {
                    "Pattern": json.dumps({
                        "dynamodb": {
                            "Keys": {
                                "PK": {
                                    "S": [{"prefix": "SUB#"}]
                                }
                            }
                        }
                    })
                }
            ]
        }
    },
    "TargetParameters": {
        "HttpParameters": {
            "HeaderParameters": {
                "Content-Type": "application/json"
            },
            "PathParameterValues": {},
            "QueryStringParameters": {}
        }
    }
}
```

#### 4.2 Parallel Step Functions Delivery (Priority: MEDIUM)

**Challenge**: Sequential delivery to multiple destinations creates latency
**Solution**: Implement parallel branches with proper error isolation

```json
{
  "Comment": "Parallel delivery with error isolation",
  "StartAt": "LoadDestinations",
  "States": {
    "LoadDestinations": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "load-destinations",
        "Payload.$": "$"
      },
      "ResultPath": "$.destinations",
      "Next": "CreateParallelBranches"
    },
    "CreateParallelBranches": {
      "Type": "Map",
      "ItemsPath": "$.destinations.items",
      "MaxConcurrency": 5,
      "ItemProcessor": {
        "ProcessorConfig": {
          "Mode": "DISTRIBUTED",
          "ExecutionType": "EXPRESS"
        },
        "StartAt": "DeliverToDestination",
        "States": {
          "DeliverToDestination": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
              "FunctionName.$": "$.connector_function",
              "Payload": {
                "submission.$": "$.submission",
                "destination.$": "$.destination",
                "attempt_number": 1
              }
            },
            "Retry": [
              {
                "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException"],
                "IntervalSeconds": 2,
                "BackoffRate": 2.0,
                "MaxAttempts": 3
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "ResultPath": "$.error",
                "Next": "RecordFailure"
              }
            ],
            "Next": "RecordSuccess"
          }
        }
      },
      "End": true
    }
  }
}
```

### Phase 5: Advanced Monitoring & Analytics (Week 7-8)

#### 5.1 Custom CloudWatch Metrics

```python
class EventBridgeMetrics:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
    
    def publish_custom_metrics(self, tenant_id: str, metrics_data: Dict):
        """Publish custom EventBridge metrics"""
        self.cloudwatch.put_metric_data(
            Namespace='FormBridge/EventBridge',
            MetricData=[
                {
                    'MetricName': 'EventsPublishedPerTenant',
                    'Value': metrics_data['events_published'],
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'TenantId', 'Value': tenant_id}
                    ]
                },
                {
                    'MetricName': 'EventProcessingLatency',
                    'Value': metrics_data['processing_latency_ms'],
                    'Unit': 'Milliseconds',
                    'Dimensions': [
                        {'Name': 'TenantId', 'Value': tenant_id}
                    ]
                },
                {
                    'MetricName': 'PayloadSizeOptimization',
                    'Value': metrics_data['s3_references_created'],
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'TenantId', 'Value': tenant_id}
                    ]
                }
            ]
        )
```

#### 5.2 Event Filtering Optimization

**Challenge**: Unnecessary Lambda invocations increase costs
**Solution**: Implement precise event pattern matching

```python
# Optimized Event Rules Configuration
event_rules = {
    "PersistRule": {
        "EventPattern": {
            "source": ["formbridge.ingest"],
            "detail-type": ["submission.received"],
            "detail": {
                "schema_version": ["2.0"],
                "tenant_id": [{"exists": True}]
            }
        },
        "Targets": [
            {
                "Id": "PersistLambda",
                "Arn": "arn:aws:lambda:us-east-1:123456789012:function:form-bridge-persist",
                "InputTransformer": {
                    "InputPathsMap": {
                        "tenant": "$.detail.tenant_id",
                        "submission": "$.detail.submission_id",
                        "payload": "$.detail.payload"
                    },
                    "InputTemplate": "{\"tenant_id\": \"<tenant>\", \"submission_id\": \"<submission>\", \"payload\": <payload>}"
                }
            }
        ]
    },
    "DeliverRule": {
        "EventPattern": {
            "source": ["formbridge.ingest"],
            "detail-type": ["submission.received"],
            "detail": {
                "schema_version": ["2.0"],
                "destinations": [{"exists": True}]
            }
        },
        "Targets": [
            {
                "Id": "DeliverStepFunction",
                "Arn": "arn:aws:states:us-east-1:123456789012:stateMachine:FormDeliveryWorkflow",
                "RoleArn": "arn:aws:iam::123456789012:role/EventBridgeStepFunctionsRole"
            }
        ]
    }
}
```

## Cost Impact Analysis

### Before Optimization
- EventBridge events: ~$1.00/million
- Lambda invocations: ~$0.20 per 1M requests
- DynamoDB writes: ~$1.25 per million writes
- **Total estimated monthly cost (10K submissions): ~$15-20**

### After Optimization
- EventBridge events (with batching): ~$0.70/million (30% reduction)
- Lambda invocations (optimized patterns): ~$0.15 per 1M requests (25% reduction)
- S3 storage for large payloads: ~$2-3/month
- Archive storage (30 days): ~$3-5/month
- **Total estimated monthly cost (10K submissions): ~$18-25** (slight increase for enhanced reliability)

### Cost-Benefit Analysis
- **One-time implementation cost**: 40-60 development hours
- **Monthly operational savings**: Improved reliability reduces incident response costs
- **Scalability benefits**: Architecture supports 100K+ submissions without major changes
- **Reduced technical debt**: Standardized patterns reduce future maintenance costs

## Security Considerations

### Event Security
1. **Event Encryption**: All events encrypted at rest and in transit
2. **Tenant Isolation**: Event patterns include tenant_id validation
3. **S3 Payload Security**: Separate bucket with tenant-based IAM policies
4. **DLQ Access Control**: Restricted access to DLQ contents
5. **Replay Security**: Audit logging for all event replay operations

### Multi-tenant Event Isolation
```python
# IAM Policy for Tenant-scoped EventBridge Access
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "events:PutEvents",
            "Resource": "arn:aws:events:*:*:event-bus/form-bridge-bus",
            "Condition": {
                "StringEquals": {
                    "events:detail.tenant_id": "${aws:PrincipalTag/TenantId}"
                }
            }
        }
    ]
}
```

## Testing Strategy

### Unit Testing
1. Event structure validation
2. S3 reference handling
3. Batch publishing logic
4. DLQ processing
5. Event filtering patterns

### Integration Testing
1. End-to-end event flow validation
2. DLQ and retry behavior
3. S3 payload handling
4. Real-time update delivery
5. Event replay functionality

### Load Testing
1. High-volume event publishing (1000+ events/minute)
2. Batch processing performance
3. DLQ behavior under stress
4. Step Functions parallel execution
5. WebSocket connection handling

### Testing Tools
- **LocalStack**: Local EventBridge testing
- **AWS EventBridge Sandbox**: Pattern testing
- **k6**: Load testing event publishing
- **pytest**: Unit and integration tests
- **moto**: AWS service mocking

## Implementation Timeline

### Week 1: Foundation & Planning
- [ ] Set up EventBridge testing environment
- [ ] Create S3 bucket for large payloads
- [ ] Implement basic event structure v2.0
- [ ] Set up monitoring and logging

### Week 2: Core Event Processing
- [ ] Implement S3 reference pattern
- [ ] Create batched event publisher
- [ ] Configure target-specific DLQs
- [ ] Add custom CloudWatch metrics

### Week 3: Advanced Features
- [ ] Implement event replay mechanism
- [ ] Set up EventBridge Pipes for real-time updates
- [ ] Optimize event filtering patterns
- [ ] Create parallel Step Functions branches

### Week 4: Testing & Optimization
- [ ] Complete integration testing
- [ ] Load testing and performance optimization
- [ ] Security audit and validation
- [ ] Documentation and runbooks

## Success Criteria

### Technical Success Metrics
- [ ] 100% of events under 256KB limit
- [ ] <1% failed event delivery rate
- [ ] Real-time dashboard updates <2 second latency
- [ ] Event replay capability functional
- [ ] Custom metrics and alerting operational

### Business Success Metrics
- [ ] Support for 100K+ submissions/month without architecture changes
- [ ] Monthly operational costs under $25 for MVP volume
- [ ] 99.9% event processing availability
- [ ] <10 minutes mean time to detection for issues
- [ ] Zero data loss incidents

### User Experience Metrics
- [ ] Real-time dashboard updates working
- [ ] Admin users can replay events for debugging
- [ ] Form submissions processed within 5 seconds end-to-end
- [ ] Delivery success rate >99% for configured destinations

## Monitoring & Alerting

### Critical Alerts (Immediate Response)
1. EventBridge target failure rate >5%
2. DLQ depth >50 messages
3. S3 payload upload failures
4. Event processing latency >30 seconds

### Warning Alerts (Response within 1 hour)
1. Event batch processing delays
2. DLQ depth >10 messages
3. Cost threshold exceeded ($20/month)
4. Archive storage approaching limits

### Informational Metrics (Daily Review)
1. Event volume by tenant
2. S3 reference usage patterns
3. Delivery success rates by destination
4. Performance trends and optimization opportunities

## Risk Assessment & Mitigation

### High-Risk Items
1. **Event Size Limit Violations**: Mitigated by S3 reference pattern and payload size monitoring
2. **DLQ Message Accumulation**: Mitigated by proper retry policies and automated monitoring
3. **Cost Overruns**: Mitigated by event filtering optimization and cost alerts
4. **Multi-tenant Data Leakage**: Mitigated by strict event pattern matching and IAM policies

### Medium-Risk Items
1. **EventBridge Service Limits**: Mitigated by batching and rate limiting
2. **S3 Storage Costs**: Mitigated by intelligent payload size thresholds and cleanup policies
3. **Complex Event Routing Errors**: Mitigated by comprehensive testing and pattern validation

### Low-Risk Items
1. **Event Schema Evolution**: Mitigated by version-aware consumers and backward compatibility
2. **Performance Degradation**: Mitigated by monitoring and automated scaling policies

## Conclusion

This EventBridge implementation plan addresses all critical optimization areas identified in the comprehensive improvement analysis. The phased approach ensures reliability while enabling advanced features like real-time updates and intelligent event processing.

The architecture balances cost efficiency with scalability, positioning Form-Bridge to handle significant growth without major redesign. Key innovations include the S3 reference pattern for large payloads, target-specific DLQ configurations, and intelligent batching for high-volume scenarios.

Implementation should proceed in phases, with careful testing and monitoring at each stage. The success metrics provide clear targets for validating the effectiveness of each optimization.

---

*This document will be updated as implementation progresses and new requirements emerge.*
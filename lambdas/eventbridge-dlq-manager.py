"""
EventBridge DLQ Manager
Dead Letter Queue management with target-specific configurations and monitoring

Features:
- Target-specific DLQ configurations
- Automatic DLQ monitoring and alerting
- Event replay from DLQ
- Multi-tenant DLQ isolation
- Cost-optimized retention policies
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TargetType(Enum):
    LAMBDA = "lambda"
    STEP_FUNCTIONS = "step_functions"
    API_DESTINATION = "api_destination"
    SNS = "sns"
    SQS = "sqs"


class DLQSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DLQConfig:
    target_type: TargetType
    queue_name: str
    queue_url: str
    retention_days: int
    visibility_timeout_seconds: int
    max_retry_attempts: int
    max_event_age_seconds: int
    alert_threshold: int
    severity: DLQSeverity


@dataclass
class DLQMetrics:
    queue_name: str
    message_count: int
    oldest_message_age_seconds: int
    messages_sent_last_hour: int
    messages_received_last_hour: int
    estimated_cost_per_month: float


class EventBridgeDLQManager:
    """Manages Dead Letter Queues for EventBridge targets"""
    
    def __init__(self, region: str = "us-east-1"):
        self.events_client = boto3.client('events', region_name=region)
        self.sqs_client = boto3.client('sqs', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.sns_client = boto3.client('sns', region_name=region)
        
        # Target-specific DLQ configurations based on 2025 best practices
        self.dlq_configs = self._get_dlq_configurations()
    
    def _get_dlq_configurations(self) -> Dict[TargetType, DLQConfig]:
        """Get optimized DLQ configurations for different target types"""
        return {
            TargetType.LAMBDA: DLQConfig(
                target_type=TargetType.LAMBDA,
                queue_name="form-bridge-lambda-dlq",
                queue_url="",  # Set during creation
                retention_days=1,  # Fast failure for persistence operations
                visibility_timeout_seconds=60,
                max_retry_attempts=3,
                max_event_age_seconds=3600,  # 1 hour
                alert_threshold=5,  # Alert if >5 messages
                severity=DLQSeverity.HIGH
            ),
            TargetType.STEP_FUNCTIONS: DLQConfig(
                target_type=TargetType.STEP_FUNCTIONS,
                queue_name="form-bridge-stepfunctions-dlq",
                queue_url="",
                retention_days=7,  # Allow more time for complex workflow investigation
                visibility_timeout_seconds=300,  # 5 minutes
                max_retry_attempts=2,
                max_event_age_seconds=7200,  # 2 hours
                alert_threshold=10,
                severity=DLQSeverity.MEDIUM
            ),
            TargetType.API_DESTINATION: DLQConfig(
                target_type=TargetType.API_DESTINATION,
                queue_name="form-bridge-webhook-dlq",
                queue_url="",
                retention_days=14,  # External services may need investigation time
                visibility_timeout_seconds=900,  # 15 minutes
                max_retry_attempts=5,
                max_event_age_seconds=86400,  # 24 hours
                alert_threshold=20,
                severity=DLQSeverity.MEDIUM
            ),
            TargetType.SNS: DLQConfig(
                target_type=TargetType.SNS,
                queue_name="form-bridge-sns-dlq",
                queue_url="",
                retention_days=3,
                visibility_timeout_seconds=120,
                max_retry_attempts=3,
                max_event_age_seconds=3600,
                alert_threshold=10,
                severity=DLQSeverity.LOW
            ),
            TargetType.SQS: DLQConfig(
                target_type=TargetType.SQS,
                queue_name="form-bridge-sqs-dlq",
                queue_url="",
                retention_days=7,
                visibility_timeout_seconds=30,
                max_retry_attempts=3,
                max_event_age_seconds=1800,  # 30 minutes
                alert_threshold=15,
                severity=DLQSeverity.LOW
            )
        }
    
    def create_dlq_infrastructure(self) -> Dict[str, str]:
        """Create all DLQ infrastructure with proper configurations"""
        created_queues = {}
        
        for target_type, config in self.dlq_configs.items():
            try:
                # Create SQS queue with target-specific configuration
                queue_url = self._create_sqs_dlq(config)
                config.queue_url = queue_url
                created_queues[target_type.value] = queue_url
                
                # Create CloudWatch alarms
                self._create_dlq_alarms(config)
                
                logger.info(f"Created DLQ infrastructure for {target_type.value}: {queue_url}")
                
            except Exception as e:
                logger.error(f"Failed to create DLQ for {target_type.value}: {e}")
                raise
        
        return created_queues
    
    def _create_sqs_dlq(self, config: DLQConfig) -> str:
        """Create SQS queue optimized for specific target type"""
        
        attributes = {
            'MessageRetentionPeriod': str(config.retention_days * 24 * 3600),
            'VisibilityTimeoutDefault': str(config.visibility_timeout_seconds),
            'ReceiveMessageWaitTimeSeconds': '20',  # Long polling
            'DelaySeconds': '0',
            'RedriveAllowPolicy': json.dumps({
                "redrivePermission": "allowAll"
            })
        }
        
        # Add encryption for sensitive data
        attributes['KmsMasterKeyId'] = 'alias/aws/sqs'
        attributes['KmsDataKeyReusePeriodSeconds'] = '300'
        
        # Add tags for cost tracking and management
        tags = {
            'Purpose': 'EventBridge-DLQ',
            'TargetType': config.target_type.value,
            'Environment': 'production',
            'CostCenter': 'form-bridge',
            'Retention': f'{config.retention_days}days'
        }
        
        try:
            response = self.sqs_client.create_queue(
                QueueName=config.queue_name,
                Attributes=attributes,
                Tags=tags
            )
            
            queue_url = response['QueueUrl']
            
            # Set queue policy to allow EventBridge access
            self._set_dlq_policy(queue_url, config)
            
            return queue_url
            
        except Exception as e:
            logger.error(f"Failed to create SQS DLQ {config.queue_name}: {e}")
            raise
    
    def _set_dlq_policy(self, queue_url: str, config: DLQConfig):
        """Set queue policy to allow EventBridge to send messages"""
        
        # Get queue attributes to get ARN
        queue_attrs = self.sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['QueueArn']
        )
        queue_arn = queue_attrs['Attributes']['QueueArn']
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowEventBridgeAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "events.amazonaws.com"
                    },
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": boto3.Session().get_credentials().access_key
                        }
                    }
                }
            ]
        }
        
        self.sqs_client.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                'Policy': json.dumps(policy)
            }
        )
    
    def _create_dlq_alarms(self, config: DLQConfig):
        """Create CloudWatch alarms for DLQ monitoring"""
        
        alarm_name = f"FormBridge-DLQ-{config.target_type.value}-MessageCount"
        
        # Create alarm for message count
        self.cloudwatch_client.put_metric_alarm(
            AlarmName=alarm_name,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=1,
            MetricName='ApproximateNumberOfVisibleMessages',
            Namespace='AWS/SQS',
            Period=300,  # 5 minutes
            Statistic='Average',
            Threshold=config.alert_threshold,
            ActionsEnabled=True,
            AlarmActions=[],  # Add SNS topic ARN for notifications
            AlarmDescription=f'DLQ message count for {config.target_type.value} targets',
            Dimensions=[
                {
                    'Name': 'QueueName',
                    'Value': config.queue_name
                }
            ],
            Unit='Count'
        )
        
        # Create alarm for oldest message age
        old_message_alarm = f"FormBridge-DLQ-{config.target_type.value}-OldMessages"
        self.cloudwatch_client.put_metric_alarm(
            AlarmName=old_message_alarm,
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=2,
            MetricName='ApproximateAgeOfOldestMessage',
            Namespace='AWS/SQS',
            Period=600,  # 10 minutes
            Statistic='Maximum',
            Threshold=3600,  # 1 hour
            ActionsEnabled=True,
            AlarmActions=[],  # Add SNS topic ARN
            AlarmDescription=f'Old messages in DLQ for {config.target_type.value}',
            Dimensions=[
                {
                    'Name': 'QueueName',
                    'Value': config.queue_name
                }
            ],
            Unit='Seconds'
        )
    
    def get_dlq_metrics(self, target_type: TargetType = None) -> List[DLQMetrics]:
        """Get current metrics for DLQs"""
        metrics = []
        
        configs_to_check = [self.dlq_configs[target_type]] if target_type else self.dlq_configs.values()
        
        for config in configs_to_check:
            if not config.queue_url:
                continue
                
            try:
                # Get queue attributes
                response = self.sqs_client.get_queue_attributes(
                    QueueUrl=config.queue_url,
                    AttributeNames=[
                        'ApproximateNumberOfMessages',
                        'ApproximateAgeOfOldestMessage'
                    ]
                )
                
                attrs = response.get('Attributes', {})
                message_count = int(attrs.get('ApproximateNumberOfMessages', 0))
                oldest_age = int(attrs.get('ApproximateAgeOfOldestMessage', 0))
                
                # Get CloudWatch metrics for message activity
                sent_last_hour = self._get_cloudwatch_metric(
                    config.queue_name, 'NumberOfMessagesSent', 3600
                )
                received_last_hour = self._get_cloudwatch_metric(
                    config.queue_name, 'NumberOfMessagesReceived', 3600
                )
                
                # Estimate monthly cost
                estimated_cost = self._estimate_dlq_cost(message_count, config.retention_days)
                
                metrics.append(DLQMetrics(
                    queue_name=config.queue_name,
                    message_count=message_count,
                    oldest_message_age_seconds=oldest_age,
                    messages_sent_last_hour=sent_last_hour,
                    messages_received_last_hour=received_last_hour,
                    estimated_cost_per_month=estimated_cost
                ))
                
            except Exception as e:
                logger.error(f"Failed to get metrics for {config.queue_name}: {e}")
        
        return metrics
    
    def _get_cloudwatch_metric(self, queue_name: str, metric_name: str, period_seconds: int) -> float:
        """Get CloudWatch metric value"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(seconds=period_seconds)
            
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/SQS',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'QueueName',
                        'Value': queue_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_seconds,
                Statistics=['Sum']
            )
            
            datapoints = response.get('Datapoints', [])
            return datapoints[0]['Sum'] if datapoints else 0.0
            
        except Exception as e:
            logger.error(f"Failed to get CloudWatch metric {metric_name}: {e}")
            return 0.0
    
    def _estimate_dlq_cost(self, message_count: int, retention_days: int) -> float:
        """Estimate monthly cost for DLQ based on message count and retention"""
        # SQS pricing (approximate, varies by region)
        cost_per_million_requests = 0.40
        cost_per_gb_month_storage = 0.40
        
        # Estimate message size (average)
        avg_message_size_bytes = 8192  # 8KB average
        
        # Calculate monthly requests (assuming steady state)
        monthly_requests = message_count * 30 * (86400 / (retention_days * 86400))
        request_cost = (monthly_requests / 1000000) * cost_per_million_requests
        
        # Calculate storage cost
        storage_gb = (message_count * avg_message_size_bytes) / (1024 ** 3)
        storage_cost = storage_gb * cost_per_gb_month_storage
        
        return request_cost + storage_cost
    
    def replay_dlq_messages(
        self, 
        target_type: TargetType, 
        max_messages: int = 10,
        destination_event_bus: str = None
    ) -> Dict[str, Any]:
        """Replay messages from DLQ back to EventBridge"""
        config = self.dlq_configs[target_type]
        
        if not config.queue_url:
            raise ValueError(f"DLQ not configured for {target_type.value}")
        
        destination_event_bus = destination_event_bus or "form-bridge-bus"
        
        replayed_count = 0
        failed_count = 0
        errors = []
        
        try:
            # Receive messages from DLQ
            while replayed_count < max_messages:
                response = self.sqs_client.receive_message(
                    QueueUrl=config.queue_url,
                    MaxNumberOfMessages=min(10, max_messages - replayed_count),
                    WaitTimeSeconds=2,
                    VisibilityTimeoutSeconds=30
                )
                
                messages = response.get('Messages', [])
                if not messages:
                    break
                
                for message in messages:
                    try:
                        # Parse original event from DLQ message
                        original_event = self._extract_original_event(message['Body'])
                        
                        if original_event:
                            # Replay event to EventBridge
                            self._replay_single_event(original_event, destination_event_bus)
                            replayed_count += 1
                            
                            # Delete message from DLQ
                            self.sqs_client.delete_message(
                                QueueUrl=config.queue_url,
                                ReceiptHandle=message['ReceiptHandle']
                            )
                        
                    except Exception as e:
                        failed_count += 1
                        errors.append(str(e))
                        logger.error(f"Failed to replay message: {e}")
        
        except Exception as e:
            logger.error(f"Failed to replay DLQ messages: {e}")
            errors.append(str(e))
        
        return {
            'target_type': target_type.value,
            'replayed_count': replayed_count,
            'failed_count': failed_count,
            'errors': errors
        }
    
    def _extract_original_event(self, dlq_message_body: str) -> Optional[Dict[str, Any]]:
        """Extract original EventBridge event from DLQ message"""
        try:
            dlq_data = json.loads(dlq_message_body)
            
            # EventBridge DLQ messages contain metadata and original event
            if 'Event' in dlq_data:
                return dlq_data['Event']
            
            # If it's the event itself
            if 'Source' in dlq_data and 'DetailType' in dlq_data:
                return dlq_data
                
        except Exception as e:
            logger.error(f"Failed to extract original event: {e}")
        
        return None
    
    def _replay_single_event(self, event: Dict[str, Any], destination_bus: str):
        """Replay a single event to EventBridge"""
        # Create replay entry
        replay_entry = {
            'Source': event.get('Source'),
            'DetailType': event.get('DetailType') + '.replay',
            'Detail': event.get('Detail'),
            'EventBusName': destination_bus,
            'Time': datetime.utcnow()
        }
        
        # Add replay metadata
        if isinstance(replay_entry['Detail'], str):
            detail_obj = json.loads(replay_entry['Detail'])
        else:
            detail_obj = replay_entry['Detail']
        
        detail_obj['_replay'] = {
            'replayed_at': datetime.utcnow().isoformat(),
            'original_time': event.get('Time'),
            'replay_reason': 'dlq_recovery'
        }
        
        replay_entry['Detail'] = json.dumps(detail_obj)
        
        # Send to EventBridge
        self.events_client.put_events(Entries=[replay_entry])
    
    def get_dlq_health_status(self) -> Dict[str, Any]:
        """Get overall health status of all DLQs"""
        metrics = self.get_dlq_metrics()
        
        total_messages = sum(m.message_count for m in metrics)
        total_cost = sum(m.estimated_cost_per_month for m in metrics)
        
        # Determine overall health
        critical_queues = []
        warning_queues = []
        
        for metric in metrics:
            config = next(
                (c for c in self.dlq_configs.values() if c.queue_name == metric.queue_name),
                None
            )
            
            if config and metric.message_count > config.alert_threshold:
                if config.severity in [DLQSeverity.HIGH, DLQSeverity.CRITICAL]:
                    critical_queues.append(metric.queue_name)
                else:
                    warning_queues.append(metric.queue_name)
        
        # Overall health status
        if critical_queues:
            health_status = "CRITICAL"
        elif warning_queues:
            health_status = "WARNING"
        elif total_messages > 0:
            health_status = "ATTENTION"
        else:
            health_status = "HEALTHY"
        
        return {
            'status': health_status,
            'total_messages': total_messages,
            'total_estimated_cost_per_month': total_cost,
            'critical_queues': critical_queues,
            'warning_queues': warning_queues,
            'queue_details': [
                {
                    'queue_name': m.queue_name,
                    'message_count': m.message_count,
                    'oldest_message_age_hours': m.oldest_message_age_seconds / 3600,
                    'estimated_monthly_cost': m.estimated_cost_per_month
                }
                for m in metrics
            ]
        }


def lambda_handler(event, context):
    """Lambda handler for DLQ management operations"""
    
    dlq_manager = EventBridgeDLQManager()
    
    operation = event.get('operation', 'health_check')
    
    try:
        if operation == 'health_check':
            return dlq_manager.get_dlq_health_status()
        
        elif operation == 'get_metrics':
            target_type = event.get('target_type')
            if target_type:
                target_type = TargetType(target_type)
            metrics = dlq_manager.get_dlq_metrics(target_type)
            return {'metrics': [m.__dict__ for m in metrics]}
        
        elif operation == 'replay_messages':
            target_type = TargetType(event['target_type'])
            max_messages = event.get('max_messages', 10)
            result = dlq_manager.replay_dlq_messages(target_type, max_messages)
            return result
        
        elif operation == 'create_infrastructure':
            created_queues = dlq_manager.create_dlq_infrastructure()
            return {'created_queues': created_queues}
        
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown operation: {operation}'})
            }
    
    except Exception as e:
        logger.error(f"DLQ management operation failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


if __name__ == "__main__":
    # Example usage
    dlq_manager = EventBridgeDLQManager()
    
    # Create DLQ infrastructure
    print("Creating DLQ infrastructure...")
    created_queues = dlq_manager.create_dlq_infrastructure()
    print(f"Created queues: {created_queues}")
    
    # Get health status
    print("\nDLQ Health Status:")
    health = dlq_manager.get_dlq_health_status()
    print(json.dumps(health, indent=2))
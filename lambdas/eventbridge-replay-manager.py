"""
EventBridge Event Replay Manager
Advanced event replay system for debugging and recovery

Features:
- Archive-based event replay with filtering
- Tenant-scoped replay operations
- Event pattern matching for selective replay
- Real-time replay monitoring and metrics
- Cost-optimized replay strategies
"""

import boto3
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ReplayStatus(Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING" 
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReplayReason(Enum):
    DEBUGGING = "debugging"
    DATA_RECOVERY = "data_recovery"
    TESTING = "testing"
    REPROCESSING = "reprocessing"
    DLQ_RECOVERY = "dlq_recovery"


@dataclass
class ReplayRequest:
    tenant_id: Optional[str]
    start_time: datetime
    end_time: datetime
    event_pattern: Optional[Dict[str, Any]]
    destination_bus: str
    reason: ReplayReason
    max_events: Optional[int] = None
    requested_by: str = "system"
    description: str = ""


@dataclass
class ReplaySession:
    replay_arn: str
    replay_name: str
    request: ReplayRequest
    status: ReplayStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    events_replayed: int = 0
    events_failed: int = 0
    estimated_cost: float = 0.0
    error_message: Optional[str] = None


class EventBridgeReplayManager:
    """Manages EventBridge event replay operations"""
    
    def __init__(self, region: str = "us-east-1"):
        self.events_client = boto3.client('events', region_name=region)
        self.dynamodb_client = boto3.client('dynamodb', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        
        # Configuration
        self.archive_name = "form-bridge-archive"
        self.default_event_bus = "form-bridge-bus"
        self.replay_table = "FormBridge-ReplaySessions"
        
        # Cost calculation (approximate)
        self.replay_cost_per_million = 0.03  # $0.03 per million events
    
    def create_replay_session(self, request: ReplayRequest) -> str:
        """Create a new event replay session"""
        
        # Validate request
        self._validate_replay_request(request)
        
        # Generate unique replay name
        replay_name = self._generate_replay_name(request)
        
        try:
            # Create EventBridge replay
            replay_arn = self._start_eventbridge_replay(replay_name, request)
            
            # Create session record
            session = ReplaySession(
                replay_arn=replay_arn,
                replay_name=replay_name,
                request=request,
                status=ReplayStatus.STARTING,
                created_at=datetime.utcnow(),
                estimated_cost=self._estimate_replay_cost(request)
            )
            
            # Store session in DynamoDB
            self._store_replay_session(session)
            
            logger.info(f"Created replay session: {replay_name}")
            return replay_arn
            
        except Exception as e:
            logger.error(f"Failed to create replay session: {e}")
            raise
    
    def _validate_replay_request(self, request: ReplayRequest):
        """Validate replay request parameters"""
        
        # Time range validation
        if request.start_time >= request.end_time:
            raise ValueError("Start time must be before end time")
        
        # Maximum replay window (7 days for cost control)
        max_window = timedelta(days=7)
        if request.end_time - request.start_time > max_window:
            raise ValueError(f"Replay window cannot exceed {max_window.days} days")
        
        # Future time check
        if request.end_time > datetime.utcnow():
            raise ValueError("End time cannot be in the future")
        
        # Archive retention check (30 days)
        archive_cutoff = datetime.utcnow() - timedelta(days=30)
        if request.start_time < archive_cutoff:
            raise ValueError("Events older than 30 days are not available in archive")
        
        # Tenant ID format validation
        if request.tenant_id and not request.tenant_id.startswith('t_'):
            raise ValueError("Invalid tenant_id format")
    
    def _generate_replay_name(self, request: ReplayRequest) -> str:
        """Generate unique replay name"""
        timestamp = int(time.time())
        tenant_part = f"-{request.tenant_id}" if request.tenant_id else ""
        reason_part = request.reason.value
        
        return f"replay-{reason_part}{tenant_part}-{timestamp}"
    
    def _start_eventbridge_replay(self, replay_name: str, request: ReplayRequest) -> str:
        """Start EventBridge replay operation"""
        
        # Build replay configuration
        replay_config = {
            'ReplayName': replay_name,
            'EventSourceArn': f'arn:aws:events:{boto3.Session().region_name}:*:archive/{self.archive_name}',
            'EventStartTime': request.start_time,
            'EventEndTime': request.end_time,
            'Destination': {
                'Arn': f'arn:aws:events:{boto3.Session().region_name}:*:event-bus/{request.destination_bus}',
            },
            'Description': request.description or f'Replay for {request.reason.value}'
        }
        
        # Add event pattern filter if specified
        if request.event_pattern or request.tenant_id:
            filter_rules = self._build_replay_filter(request)
            if filter_rules:
                replay_config['Destination']['FilterArns'] = filter_rules
        
        # Start replay
        response = self.events_client.start_replay(**replay_config)
        return response['ReplayArn']
    
    def _build_replay_filter(self, request: ReplayRequest) -> List[str]:
        """Build event filter rules for replay"""
        filter_rules = []
        
        # Create temporary rule for filtering if needed
        if request.event_pattern or request.tenant_id:
            # Build event pattern
            event_pattern = request.event_pattern or {}
            
            # Add tenant filter if specified
            if request.tenant_id:
                if 'detail' not in event_pattern:
                    event_pattern['detail'] = {}
                event_pattern['detail']['tenant_id'] = [request.tenant_id]
            
            # Create temporary filter rule
            rule_name = f"replay-filter-{int(time.time())}"
            
            try:
                response = self.events_client.put_rule(
                    Name=rule_name,
                    EventPattern=json.dumps(event_pattern),
                    State='ENABLED',
                    Description=f'Temporary filter for replay {request.reason.value}',
                    EventBusName=request.destination_bus
                )
                
                filter_rules.append(response['RuleArn'])
                
            except Exception as e:
                logger.warning(f"Failed to create replay filter rule: {e}")
        
        return filter_rules
    
    def _estimate_replay_cost(self, request: ReplayRequest) -> float:
        """Estimate cost of replay operation"""
        
        # Estimate event count based on time range
        # This is a rough estimate - actual costs will vary
        hours = (request.end_time - request.start_time).total_seconds() / 3600
        
        # Assume average event rate (this should be based on historical data)
        estimated_events_per_hour = 1000  # Adjust based on your traffic
        estimated_total_events = hours * estimated_events_per_hour
        
        # Apply tenant filter reduction if specified
        if request.tenant_id:
            estimated_total_events *= 0.1  # Assume 10% of events per tenant
        
        # Apply pattern filter reduction
        if request.event_pattern:
            estimated_total_events *= 0.5  # Assume 50% reduction with pattern
        
        # Apply max events limit
        if request.max_events:
            estimated_total_events = min(estimated_total_events, request.max_events)
        
        # Calculate cost
        cost = (estimated_total_events / 1000000) * self.replay_cost_per_million
        return round(cost, 4)
    
    def _store_replay_session(self, session: ReplaySession):
        """Store replay session in DynamoDB"""
        
        item = {
            'PK': {'S': f'REPLAY#{session.replay_name}'},
            'SK': {'S': 'SESSION'},
            'replay_arn': {'S': session.replay_arn},
            'replay_name': {'S': session.replay_name},
            'tenant_id': {'S': session.request.tenant_id or 'ALL'},
            'status': {'S': session.status.value},
            'reason': {'S': session.request.reason.value},
            'requested_by': {'S': session.request.requested_by},
            'created_at': {'S': session.created_at.isoformat()},
            'start_time': {'S': session.request.start_time.isoformat()},
            'end_time': {'S': session.request.end_time.isoformat()},
            'destination_bus': {'S': session.request.destination_bus},
            'estimated_cost': {'N': str(session.estimated_cost)},
            'events_replayed': {'N': str(session.events_replayed)},
            'events_failed': {'N': str(session.events_failed)}
        }
        
        if session.request.description:
            item['description'] = {'S': session.request.description}
        
        if session.request.event_pattern:
            item['event_pattern'] = {'S': json.dumps(session.request.event_pattern)}
        
        if session.error_message:
            item['error_message'] = {'S': session.error_message}
        
        try:
            self.dynamodb_client.put_item(
                TableName=self.replay_table,
                Item=item
            )
        except Exception as e:
            logger.error(f"Failed to store replay session: {e}")
            # Don't fail the replay creation if storage fails
    
    def get_replay_status(self, replay_arn: str) -> Optional[ReplaySession]:
        """Get current status of replay session"""
        
        try:
            # Get status from EventBridge
            response = self.events_client.describe_replay(
                ReplayName=replay_arn.split('/')[-1]
            )
            
            # Update session in DynamoDB
            session = self._update_replay_session_status(response)
            return session
            
        except Exception as e:
            logger.error(f"Failed to get replay status: {e}")
            return None
    
    def _update_replay_session_status(self, eventbridge_response: Dict[str, Any]) -> ReplaySession:
        """Update replay session status from EventBridge response"""
        
        replay_name = eventbridge_response['ReplayName']
        status = ReplayStatus(eventbridge_response['State'])
        
        # Get session from DynamoDB
        session = self._get_replay_session(replay_name)
        if not session:
            return None
        
        # Update status
        session.status = status
        
        if 'ReplayStartTime' in eventbridge_response and not session.started_at:
            session.started_at = eventbridge_response['ReplayStartTime']
        
        if 'ReplayEndTime' in eventbridge_response and not session.completed_at:
            session.completed_at = eventbridge_response['ReplayEndTime']
        
        # Update event counts (if available)
        if 'EventLastReplayedTime' in eventbridge_response:
            # This is approximate - EventBridge doesn't provide exact counts
            session.events_replayed = self._estimate_replayed_events(session, eventbridge_response)
        
        # Store updated session
        self._store_replay_session(session)
        
        return session
    
    def _get_replay_session(self, replay_name: str) -> Optional[ReplaySession]:
        """Get replay session from DynamoDB"""
        
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.replay_table,
                Key={
                    'PK': {'S': f'REPLAY#{replay_name}'},
                    'SK': {'S': 'SESSION'}
                }
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            
            # Reconstruct session object
            request = ReplayRequest(
                tenant_id=item.get('tenant_id', {}).get('S') if item.get('tenant_id', {}).get('S') != 'ALL' else None,
                start_time=datetime.fromisoformat(item['start_time']['S']),
                end_time=datetime.fromisoformat(item['end_time']['S']),
                event_pattern=json.loads(item['event_pattern']['S']) if 'event_pattern' in item else None,
                destination_bus=item['destination_bus']['S'],
                reason=ReplayReason(item['reason']['S']),
                requested_by=item['requested_by']['S'],
                description=item.get('description', {}).get('S', '')
            )
            
            session = ReplaySession(
                replay_arn=item['replay_arn']['S'],
                replay_name=item['replay_name']['S'],
                request=request,
                status=ReplayStatus(item['status']['S']),
                created_at=datetime.fromisoformat(item['created_at']['S']),
                events_replayed=int(item['events_replayed']['N']),
                events_failed=int(item['events_failed']['N']),
                estimated_cost=float(item['estimated_cost']['N']),
                error_message=item.get('error_message', {}).get('S')
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to get replay session: {e}")
            return None
    
    def _estimate_replayed_events(self, session: ReplaySession, eventbridge_response: Dict[str, Any]) -> int:
        """Estimate number of events replayed (approximate)"""
        
        if 'EventLastReplayedTime' not in eventbridge_response:
            return session.events_replayed
        
        last_replayed = eventbridge_response['EventLastReplayedTime']
        
        # Calculate progress based on time
        total_duration = (session.request.end_time - session.request.start_time).total_seconds()
        completed_duration = (last_replayed - session.request.start_time).total_seconds()
        
        progress = min(completed_duration / total_duration, 1.0) if total_duration > 0 else 1.0
        
        # Estimate based on expected total events
        expected_total = self._estimate_total_events_in_range(session.request)
        return int(expected_total * progress)
    
    def _estimate_total_events_in_range(self, request: ReplayRequest) -> int:
        """Estimate total events in time range"""
        hours = (request.end_time - request.start_time).total_seconds() / 3600
        estimated_events_per_hour = 1000  # Should be based on historical data
        return int(hours * estimated_events_per_hour)
    
    def list_replay_sessions(
        self, 
        tenant_id: Optional[str] = None,
        status: Optional[ReplayStatus] = None,
        limit: int = 50
    ) -> List[ReplaySession]:
        """List replay sessions with optional filtering"""
        
        sessions = []
        
        try:
            # Query DynamoDB for replay sessions
            query_params = {
                'TableName': self.replay_table,
                'IndexName': 'SK-created_at-index',  # Assuming we have this GSI
                'KeyConditionExpression': 'SK = :sk',
                'ExpressionAttributeValues': {
                    ':sk': {'S': 'SESSION'}
                },
                'ScanIndexForward': False,  # Most recent first
                'Limit': limit
            }
            
            # Add filters
            filter_expressions = []
            
            if tenant_id:
                filter_expressions.append('tenant_id = :tenant_id')
                query_params['ExpressionAttributeValues'][':tenant_id'] = {'S': tenant_id}
            
            if status:
                filter_expressions.append('#status = :status')
                query_params['ExpressionAttributeValues'][':status'] = {'S': status.value}
                query_params['ExpressionAttributeNames'] = {'#status': 'status'}
            
            if filter_expressions:
                query_params['FilterExpression'] = ' AND '.join(filter_expressions)
            
            response = self.dynamodb_client.scan(**query_params)  # Use scan for simplicity
            
            for item in response.get('Items', []):
                session = self._parse_dynamodb_session(item)
                if session:
                    sessions.append(session)
            
        except Exception as e:
            logger.error(f"Failed to list replay sessions: {e}")
        
        return sessions
    
    def _parse_dynamodb_session(self, item: Dict[str, Any]) -> Optional[ReplaySession]:
        """Parse DynamoDB item into ReplaySession object"""
        try:
            # Same logic as _get_replay_session but for scan results
            request = ReplayRequest(
                tenant_id=item.get('tenant_id', {}).get('S') if item.get('tenant_id', {}).get('S') != 'ALL' else None,
                start_time=datetime.fromisoformat(item['start_time']['S']),
                end_time=datetime.fromisoformat(item['end_time']['S']),
                event_pattern=json.loads(item['event_pattern']['S']) if 'event_pattern' in item else None,
                destination_bus=item['destination_bus']['S'],
                reason=ReplayReason(item['reason']['S']),
                requested_by=item['requested_by']['S'],
                description=item.get('description', {}).get('S', '')
            )
            
            session = ReplaySession(
                replay_arn=item['replay_arn']['S'],
                replay_name=item['replay_name']['S'],
                request=request,
                status=ReplayStatus(item['status']['S']),
                created_at=datetime.fromisoformat(item['created_at']['S']),
                events_replayed=int(item['events_replayed']['N']),
                events_failed=int(item['events_failed']['N']),
                estimated_cost=float(item['estimated_cost']['N']),
                error_message=item.get('error_message', {}).get('S')
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to parse DynamoDB session: {e}")
            return None
    
    def cancel_replay(self, replay_name: str) -> bool:
        """Cancel running replay"""
        
        try:
            self.events_client.cancel_replay(ReplayName=replay_name)
            
            # Update session status
            session = self._get_replay_session(replay_name)
            if session:
                session.status = ReplayStatus.CANCELLING
                self._store_replay_session(session)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel replay: {e}")
            return False
    
    def get_replay_metrics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get replay metrics and statistics"""
        
        sessions = self.list_replay_sessions(tenant_id=tenant_id, limit=100)
        
        # Calculate metrics
        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s.status == ReplayStatus.COMPLETED])
        failed_sessions = len([s for s in sessions if s.status == ReplayStatus.FAILED])
        running_sessions = len([s for s in sessions if s.status == ReplayStatus.RUNNING])
        
        total_events_replayed = sum(s.events_replayed for s in sessions)
        total_estimated_cost = sum(s.estimated_cost for s in sessions)
        
        # Success rate
        success_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        # Most common replay reasons
        reason_counts = {}
        for session in sessions:
            reason = session.request.reason.value
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'failed_sessions': failed_sessions,
            'running_sessions': running_sessions,
            'success_rate_percent': round(success_rate, 2),
            'total_events_replayed': total_events_replayed,
            'total_estimated_cost_usd': total_estimated_cost,
            'reason_distribution': reason_counts,
            'most_recent_sessions': [
                {
                    'replay_name': s.replay_name,
                    'tenant_id': s.request.tenant_id,
                    'status': s.status.value,
                    'reason': s.request.reason.value,
                    'created_at': s.created_at.isoformat(),
                    'events_replayed': s.events_replayed,
                    'estimated_cost': s.estimated_cost
                }
                for s in sessions[:10]
            ]
        }


def lambda_handler(event, context):
    """Lambda handler for replay management operations"""
    
    replay_manager = EventBridgeReplayManager()
    
    operation = event.get('operation')
    
    try:
        if operation == 'create_replay':
            # Create replay request
            request_data = event['replay_request']
            request = ReplayRequest(
                tenant_id=request_data.get('tenant_id'),
                start_time=datetime.fromisoformat(request_data['start_time']),
                end_time=datetime.fromisoformat(request_data['end_time']),
                event_pattern=request_data.get('event_pattern'),
                destination_bus=request_data.get('destination_bus', 'form-bridge-bus'),
                reason=ReplayReason(request_data['reason']),
                max_events=request_data.get('max_events'),
                requested_by=request_data.get('requested_by', 'lambda'),
                description=request_data.get('description', '')
            )
            
            replay_arn = replay_manager.create_replay_session(request)
            return {'replay_arn': replay_arn}
        
        elif operation == 'get_status':
            replay_arn = event['replay_arn']
            session = replay_manager.get_replay_status(replay_arn)
            return {'session': asdict(session) if session else None}
        
        elif operation == 'list_sessions':
            tenant_id = event.get('tenant_id')
            status = ReplayStatus(event['status']) if event.get('status') else None
            limit = event.get('limit', 50)
            
            sessions = replay_manager.list_replay_sessions(tenant_id, status, limit)
            return {'sessions': [asdict(s) for s in sessions]}
        
        elif operation == 'cancel_replay':
            replay_name = event['replay_name']
            success = replay_manager.cancel_replay(replay_name)
            return {'cancelled': success}
        
        elif operation == 'get_metrics':
            tenant_id = event.get('tenant_id')
            metrics = replay_manager.get_replay_metrics(tenant_id)
            return metrics
        
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown operation: {operation}'})
            }
    
    except Exception as e:
        logger.error(f"Replay operation failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


if __name__ == "__main__":
    # Example usage
    replay_manager = EventBridgeReplayManager()
    
    # Create a test replay request
    request = ReplayRequest(
        tenant_id="t_example123",
        start_time=datetime.utcnow() - timedelta(hours=24),
        end_time=datetime.utcnow() - timedelta(hours=1),
        event_pattern={
            "source": ["formbridge.ingest"],
            "detail-type": ["submission.received"]
        },
        destination_bus="form-bridge-bus",
        reason=ReplayReason.DEBUGGING,
        description="Test replay for debugging form submission issues"
    )
    
    print("Creating replay session...")
    replay_arn = replay_manager.create_replay_session(request)
    print(f"Created replay: {replay_arn}")
    
    # Get metrics
    print("\nReplay metrics:")
    metrics = replay_manager.get_replay_metrics()
    print(json.dumps(metrics, indent=2))
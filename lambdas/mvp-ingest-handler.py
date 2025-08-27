"""
MVP Form Ingestion Handler
Simplified for quick deployment - no ARM64, no PowerTools, basic auth
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone
import boto3

# Initialize AWS clients (reuse connections)
dynamodb = boto3.resource('dynamodb')
events = boto3.client('events')

# Environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'formbridge-data-dev')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'default')

def lambda_handler(event, context):
    """
    MVP Form Submission Handler
    - Basic tenant validation
    - Store in DynamoDB with simple schema
    - Publish to EventBridge
    - Fast deployment, no complex dependencies
    """
    print(f"Processing form submission request")
    
    try:
        # Extract request details
        headers = event.get('headers', {})
        body_str = event.get('body', '{}')
        
        # Parse request body
        try:
            body = json.loads(body_str)
        except json.JSONDecodeError:
            return error_response(400, "Invalid JSON in request body")
        
        # Extract tenant ID from headers (case-insensitive)
        tenant_id = None
        for key, value in headers.items():
            if key.lower() == 'x-tenant-id':
                tenant_id = value
                break
        
        if not tenant_id:
            return error_response(401, "Missing X-Tenant-ID header")
        
        # Validate required fields
        form_data = body.get('form_data')
        if not form_data:
            return error_response(400, "Missing 'form_data' field")
        
        # Generate submission ID and timestamp
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Prepare DynamoDB item (simple structure)
        table = dynamodb.Table(TABLE_NAME)
        item = {
            'PK': f'TENANT#{tenant_id}',
            'SK': f'SUBMISSION#{submission_id}',
            'GSI1PK': f'DATE#{timestamp[:10]}',  # For date-based queries
            'GSI1SK': f'TENANT#{tenant_id}#{timestamp}',
            'submission_id': submission_id,
            'tenant_id': tenant_id,
            'form_data': form_data,
            'source': body.get('source', 'api'),
            'form_type': body.get('form_type', 'generic'),
            'metadata': body.get('metadata', {}),
            'status': 'received',
            'created_at': timestamp,
            'ttl': int(time.time()) + (30 * 24 * 60 * 60)  # 30 days TTL
        }
        
        # Store in DynamoDB
        print(f"Storing submission {submission_id} for tenant {tenant_id}")
        table.put_item(Item=item)
        
        # Publish event to EventBridge
        event_detail = {
            'submission_id': submission_id,
            'tenant_id': tenant_id,
            'timestamp': timestamp,
            'form_type': body.get('form_type', 'generic'),
            'source': body.get('source', 'api'),
            'payload_size': len(json.dumps(form_data))
        }
        
        print(f"Publishing event for submission {submission_id}")
        events.put_events(
            Entries=[{
                'Source': 'formbridge.ingest',
                'DetailType': 'Form Submission Received',
                'Detail': json.dumps(event_detail),
                'EventBusName': EVENT_BUS_NAME
            }]
        )
        
        # Success response
        response_body = {
            'success': True,
            'submission_id': submission_id,
            'tenant_id': tenant_id,
            'status': 'received',
            'message': 'Form submission processed successfully'
        }
        
        print(f"Successfully processed submission {submission_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Tenant-ID'
            },
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Error processing form submission: {str(e)}")
        return error_response(500, "Internal server error", str(e) if ENVIRONMENT == 'dev' else None)

def error_response(status_code, message, detail=None):
    """Generate standardized error response"""
    response_body = {
        'success': False,
        'error': message
    }
    
    if detail:
        response_body['detail'] = detail
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Tenant-ID'
        },
        'body': json.dumps(response_body)
    }
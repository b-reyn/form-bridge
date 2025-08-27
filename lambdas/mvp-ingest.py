"""
MVP Form Ingestion Lambda
Simplified version for quick deployment
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
events = boto3.client('events')

# Environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

def lambda_handler(event, context):
    """
    Simple form submission handler
    - Validates basic request
    - Stores in DynamoDB
    - Publishes to EventBridge
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Extract tenant ID from headers (simplified authentication)
        headers = event.get('headers', {})
        tenant_id = headers.get('x-tenant-id', 'default')
        
        # Validate required fields
        if not body.get('form_data'):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'form_data is required'}),
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }
        
        # Generate submission ID
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Prepare DynamoDB item
        table = dynamodb.Table(TABLE_NAME)
        item = {
            'PK': f'TENANT#{tenant_id}',
            'SK': f'SUBMISSION#{submission_id}',
            'GSI1PK': f'DATE#{timestamp[:10]}',  # Date index
            'GSI1SK': f'TENANT#{tenant_id}#{submission_id}',
            'submission_id': submission_id,
            'tenant_id': tenant_id,
            'form_data': body['form_data'],
            'metadata': body.get('metadata', {}),
            'status': 'pending',
            'created_at': timestamp,
            'ttl': int(time.time()) + (30 * 24 * 60 * 60)  # 30 days
        }
        
        # Store in DynamoDB
        table.put_item(Item=item)
        
        # Publish to EventBridge
        event_detail = {
            'submission_id': submission_id,
            'tenant_id': tenant_id,
            'timestamp': timestamp,
            'form_type': body.get('form_type', 'generic'),
            'size': len(json.dumps(body['form_data']))
        }
        
        events.put_events(
            Entries=[
                {
                    'Source': 'formbridge',
                    'DetailType': 'Form Submission',
                    'Detail': json.dumps(event_detail),
                    'Resources': [f'tenant/{tenant_id}']
                }
            ]
        )
        
        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'submission_id': submission_id,
                'status': 'accepted',
                'message': 'Form submission received'
            }),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
        
    except Exception as e:
        print(f"Error processing submission: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e) if ENVIRONMENT == 'dev' else 'An error occurred'
            }),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
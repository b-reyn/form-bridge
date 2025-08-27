"""
MVP Event Processor
Handles EventBridge events and updates submission status
Simplified for quick deployment
"""
import json
import os
from datetime import datetime, timezone
import boto3

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'formbridge-data-dev')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

def lambda_handler(event, context):
    """
    Process EventBridge events from form ingestion
    - Update submission status in DynamoDB
    - Basic error handling
    - Simple logging
    """
    print(f"Processing EventBridge event: {json.dumps(event, default=str)}")
    
    try:
        # Extract event details
        source = event.get('source')
        detail_type = event.get('detail-type')
        detail = event.get('detail', {})
        
        if source != 'formbridge.ingest':
            print(f"Ignoring event from source: {source}")
            return {'statusCode': 200, 'body': 'Event ignored'}
        
        # Extract submission details
        submission_id = detail.get('submission_id')
        tenant_id = detail.get('tenant_id')
        
        if not submission_id or not tenant_id:
            error_msg = f"Missing required fields - submission_id: {submission_id}, tenant_id: {tenant_id}"
            print(error_msg)
            return {'statusCode': 400, 'body': error_msg}
        
        # Update submission status in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        print(f"Updating submission {submission_id} for tenant {tenant_id}")
        
        response = table.update_item(
            Key={
                'PK': f'TENANT#{tenant_id}',
                'SK': f'SUBMISSION#{submission_id}'
            },
            UpdateExpression='SET #status = :status, processed_at = :timestamp, processor_version = :version',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'processed',
                ':timestamp': timestamp,
                ':version': 'mvp-1.0'
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f"Successfully updated submission {submission_id}")
        
        # Log the updated item for debugging
        if ENVIRONMENT == 'dev':
            print(f"Updated item: {json.dumps(response.get('Attributes', {}), default=str)}")
        
        # Here you could add additional processing logic:
        # - Send notifications
        # - Trigger webhook deliveries  
        # - Start Step Functions workflows
        # - Store large payloads in S3
        # - Send to external systems
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'submission_id': submission_id,
                'tenant_id': tenant_id,
                'status': 'processed',
                'processed_at': timestamp
            })
        }
        
    except Exception as e:
        error_msg = f"Error processing event: {str(e)}"
        print(error_msg)
        
        # In production, you might want to send failed events to a DLQ
        # or trigger an alarm for investigation
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': error_msg if ENVIRONMENT == 'dev' else 'Processing failed'
            })
        }
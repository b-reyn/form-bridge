"""
MVP Form Processor Lambda
Processes form submissions from EventBridge
"""
import json
import os
from datetime import datetime, timezone
import boto3

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

def lambda_handler(event, context):
    """
    Process form submissions from EventBridge
    - Updates submission status
    - Performs basic processing
    - Could trigger additional workflows
    """
    try:
        # Extract event details
        detail = event.get('detail', {})
        submission_id = detail.get('submission_id')
        tenant_id = detail.get('tenant_id')
        
        if not submission_id or not tenant_id:
            print(f"Missing required fields: submission_id={submission_id}, tenant_id={tenant_id}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required fields'})
            }
        
        # Update submission status in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        response = table.update_item(
            Key={
                'PK': f'TENANT#{tenant_id}',
                'SK': f'SUBMISSION#{submission_id}'
            },
            UpdateExpression='SET #status = :status, processed_at = :timestamp',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'processed',
                ':timestamp': timestamp
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f"Successfully processed submission {submission_id} for tenant {tenant_id}")
        
        # Here you could add additional processing logic:
        # - Send to external systems
        # - Trigger notifications
        # - Start Step Functions workflows
        # - Store large payloads in S3
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'submission_id': submission_id,
                'status': 'processed',
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error processing submission: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Processing failed',
                'message': str(e) if ENVIRONMENT == 'dev' else 'An error occurred'
            })
        }
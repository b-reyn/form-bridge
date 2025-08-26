#!/usr/bin/env python3
"""
Setup test infrastructure for Form-Bridge testing
Creates necessary AWS resources in LocalStack for testing
"""

import os
import json
import time
import boto3
from datetime import datetime
from typing import Dict, List, Any


class TestInfrastructureSetup:
    """Setup AWS infrastructure in LocalStack for testing"""
    
    def __init__(self):
        self.endpoint_url = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        self.region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        
        # Initialize AWS clients for LocalStack
        self.session_config = {
            'endpoint_url': self.endpoint_url,
            'region_name': self.region,
            'aws_access_key_id': 'test',
            'aws_secret_access_key': 'test'
        }
        
        self.dynamodb = boto3.resource('dynamodb', **self.session_config)
        self.eventbridge = boto3.client('events', **self.session_config)
        self.lambda_client = boto3.client('lambda', **self.session_config)
        self.apigateway = boto3.client('apigateway', **self.session_config)
        self.secretsmanager = boto3.client('secretsmanager', **self.session_config)
        
    def setup_all(self):
        """Setup all test infrastructure"""
        print("🚀 Setting up Form-Bridge test infrastructure...")
        
        try:
            self.wait_for_localstack()
            self.setup_dynamodb_tables()
            self.setup_eventbridge_resources()
            self.setup_secrets()
            self.setup_lambda_functions()
            self.setup_api_gateway()
            self.verify_infrastructure()
            
            print("✅ Test infrastructure setup completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Infrastructure setup failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def wait_for_localstack(self, max_retries: int = 30):
        """Wait for LocalStack to be ready"""
        import requests
        
        print("⏳ Waiting for LocalStack to be ready...")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.endpoint_url}/health", timeout=5)
                if response.status_code == 200:
                    health_data = response.json()
                    print(f"✅ LocalStack is ready! Services: {list(health_data.get('services', {}).keys())}")
                    return
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"🔄 Attempt {attempt + 1}/{max_retries}: LocalStack not ready yet...")
                    time.sleep(2)
                else:
                    raise Exception(f"LocalStack failed to start after {max_retries} attempts: {e}")
    
    def setup_dynamodb_tables(self):
        """Create DynamoDB tables for testing"""
        print("📊 Setting up DynamoDB tables...")
        
        # Main FormBridge table with multi-tenant design
        table_config = {
            'TableName': 'formbridge-test',
            'KeySchema': [
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2SK', 'AttributeType': 'S'},
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'GSI2',
                    'KeySchema': [
                        {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            'BillingMode': 'PAY_PER_REQUEST',
            'StreamSpecification': {
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            }
        }
        
        try:
            table = self.dynamodb.create_table(**table_config)
            table.wait_until_exists()
            print(f"✅ Created table: {table_config['TableName']}")
            
            # Create sample test data
            self._populate_test_data()
            
        except Exception as e:
            if 'ResourceInUseException' in str(e) or 'already exists' in str(e):
                print(f"ℹ️ Table already exists: {table_config['TableName']}")
            else:
                raise e
    
    def _populate_test_data(self):
        """Populate test data for various test scenarios"""
        print("📝 Populating test data...")
        
        table = self.dynamodb.Table('formbridge-test')
        
        # Test tenants
        test_tenants = [
            {'id': 't_test_tenant_1', 'name': 'Test Tenant 1'},
            {'id': 't_test_tenant_2', 'name': 'Test Tenant 2'},
            {'id': 't_test_tenant_3', 'name': 'Test Tenant 3'},
        ]
        
        for tenant in test_tenants:
            # Tenant configuration
            table.put_item(Item={
                'PK': f"TENANT#{tenant['id']}",
                'SK': 'CONFIG',
                'tenant_id': tenant['id'],
                'tenant_name': tenant['name'],
                'created_at': datetime.utcnow().isoformat(),
                'rate_limit': {'requests_per_minute': 100},
                'features': {'wordpress_plugin': True, 'analytics': True},
                'ttl': int(time.time()) + (7 * 24 * 60 * 60)  # 7 days TTL
            })
            
            # Sample form submissions
            for i in range(5):
                submission_id = f"test_submission_{i:03d}"
                table.put_item(Item={
                    'PK': f"TENANT#{tenant['id']}#SUBMISSION#{submission_id}",
                    'SK': f"META#{datetime.utcnow().isoformat()}",
                    'tenant_id': tenant['id'],
                    'submission_id': submission_id,
                    'form_id': 'contact_form',
                    'submitted_at': datetime.utcnow().isoformat(),
                    'payload': {
                        'name': f'Test User {i}',
                        'email': f'test{i}@example.com',
                        'message': f'Test message {i}'
                    },
                    'GSI1PK': f"{tenant['id']}#FORM#contact_form",
                    'GSI1SK': datetime.utcnow().isoformat(),
                    'GSI2PK': f"{tenant['id']}#STATUS#pending",
                    'GSI2SK': datetime.utcnow().isoformat(),
                    'ttl': int(time.time()) + (30 * 24 * 60 * 60)  # 30 days TTL
                })
        
        print("✅ Test data populated")
    
    def setup_eventbridge_resources(self):
        """Setup EventBridge custom bus and rules"""
        print("🎯 Setting up EventBridge resources...")
        
        # Create custom event bus
        bus_name = 'formbridge-test-bus'
        try:
            self.eventbridge.create_event_bus(Name=bus_name)
            print(f"✅ Created event bus: {bus_name}")
        except Exception as e:
            if 'already exists' in str(e) or 'ResourceAlreadyExistsException' in str(e):
                print(f"ℹ️ Event bus already exists: {bus_name}")
            else:
                print(f"⚠️ Failed to create event bus: {e}")
        
        # Create event rules for different tenant patterns
        rules = [
            {
                'Name': 'formbridge-submission-rule',
                'EventPattern': json.dumps({
                    'source': ['formbridge.submissions'],
                    'detail-type': ['Form Submission']
                }),
                'Description': 'Route form submissions to processors'
            },
            {
                'Name': 'formbridge-webhook-rule',
                'EventPattern': json.dumps({
                    'source': ['formbridge.webhooks'],
                    'detail-type': ['Webhook Delivery']
                }),
                'Description': 'Route webhook delivery events'
            },
            {
                'Name': 'formbridge-analytics-rule',
                'EventPattern': json.dumps({
                    'source': ['formbridge.analytics'],
                    'detail-type': ['Analytics Event']
                }),
                'Description': 'Route analytics events'
            }
        ]
        
        for rule in rules:
            try:
                self.eventbridge.put_rule(
                    Name=rule['Name'],
                    EventPattern=rule['EventPattern'],
                    Description=rule['Description'],
                    EventBusName=bus_name,
                    State='ENABLED'
                )
                print(f"✅ Created event rule: {rule['Name']}")
            except Exception as e:
                print(f"⚠️ Failed to create rule {rule['Name']}: {e}")
    
    def setup_secrets(self):
        """Setup secrets for tenant authentication"""
        print("🔐 Setting up secrets...")
        
        test_secrets = [
            {
                'name': 'formbridge/tenants/t_test_tenant_1',
                'value': {
                    'api_key': 'test_api_key_1',
                    'secret_key': 'test_secret_key_1_for_hmac_signing',
                    'webhook_signing_key': 'test_webhook_key_1'
                }
            },
            {
                'name': 'formbridge/tenants/t_test_tenant_2',
                'value': {
                    'api_key': 'test_api_key_2',
                    'secret_key': 'test_secret_key_2_for_hmac_signing',
                    'webhook_signing_key': 'test_webhook_key_2'
                }
            },
            {
                'name': 'formbridge/tenants/t_test_tenant_3',
                'value': {
                    'api_key': 'test_api_key_3',
                    'secret_key': 'test_secret_key_3_for_hmac_signing',
                    'webhook_signing_key': 'test_webhook_key_3'
                }
            },
            {
                'name': 'formbridge/config/global',
                'value': {
                    'encryption_key': 'test_encryption_key_for_sensitive_data',
                    'jwt_secret': 'test_jwt_secret_for_token_signing',
                    'admin_api_key': 'test_admin_api_key'
                }
            }
        ]
        
        for secret in test_secrets:
            try:
                self.secretsmanager.create_secret(
                    Name=secret['name'],
                    Description=f"Test secret for {secret['name']}",
                    SecretString=json.dumps(secret['value'])
                )
                print(f"✅ Created secret: {secret['name']}")
            except Exception as e:
                if 'already exists' in str(e) or 'ResourceExistsException' in str(e):
                    print(f"ℹ️ Secret already exists: {secret['name']}")
                    # Update existing secret
                    try:
                        self.secretsmanager.update_secret(
                            SecretId=secret['name'],
                            SecretString=json.dumps(secret['value'])
                        )
                        print(f"📝 Updated secret: {secret['name']}")
                    except Exception as update_e:
                        print(f"⚠️ Failed to update secret {secret['name']}: {update_e}")
                else:
                    print(f"⚠️ Failed to create secret {secret['name']}: {e}")
    
    def setup_lambda_functions(self):
        """Setup Lambda functions for testing"""
        print("⚡ Setting up Lambda functions...")
        
        # Create mock Lambda functions for testing
        functions = [
            {
                'FunctionName': 'formbridge-hmac-authorizer-test',
                'Runtime': 'python3.12',
                'Role': 'arn:aws:iam::000000000000:role/lambda-role',
                'Handler': 'lambda_function.lambda_handler',
                'Code': {'ZipFile': self._get_mock_lambda_code('hmac_authorizer')},
                'Description': 'Test HMAC authorizer function',
                'Timeout': 30,
                'MemorySize': 512,
                'Environment': {
                    'Variables': {
                        'FORMBRIDGE_ENV': 'test',
                        'SECRETS_ENDPOINT': self.endpoint_url
                    }
                }
            },
            {
                'FunctionName': 'formbridge-event-processor-test',
                'Runtime': 'python3.12',
                'Role': 'arn:aws:iam::000000000000:role/lambda-role',
                'Handler': 'lambda_function.lambda_handler',
                'Code': {'ZipFile': self._get_mock_lambda_code('event_processor')},
                'Description': 'Test event processor function',
                'Timeout': 60,
                'MemorySize': 768,
                'Environment': {
                    'Variables': {
                        'FORMBRIDGE_ENV': 'test',
                        'DYNAMODB_ENDPOINT': self.endpoint_url,
                        'EVENTBRIDGE_ENDPOINT': self.endpoint_url
                    }
                }
            },
            {
                'FunctionName': 'formbridge-smart-connector-test',
                'Runtime': 'python3.12',
                'Role': 'arn:aws:iam::000000000000:role/lambda-role',
                'Handler': 'lambda_function.lambda_handler',
                'Code': {'ZipFile': self._get_mock_lambda_code('smart_connector')},
                'Description': 'Test smart connector function',
                'Timeout': 300,
                'MemorySize': 1024,
                'Environment': {
                    'Variables': {
                        'FORMBRIDGE_ENV': 'test',
                        'SECRETS_ENDPOINT': self.endpoint_url
                    }
                }
            }
        ]
        
        for func in functions:
            try:
                response = self.lambda_client.create_function(**func)
                print(f"✅ Created Lambda function: {func['FunctionName']}")
                
                # Wait for function to be ready
                waiter = self.lambda_client.get_waiter('function_active')
                waiter.wait(FunctionName=func['FunctionName'])
                
            except Exception as e:
                if 'already exists' in str(e) or 'ResourceConflictException' in str(e):
                    print(f"ℹ️ Function already exists: {func['FunctionName']}")
                    # Update function code
                    try:
                        self.lambda_client.update_function_code(
                            FunctionName=func['FunctionName'],
                            ZipFile=func['Code']['ZipFile']
                        )
                        print(f"📝 Updated function: {func['FunctionName']}")
                    except Exception as update_e:
                        print(f"⚠️ Failed to update function {func['FunctionName']}: {update_e}")
                else:
                    print(f"⚠️ Failed to create function {func['FunctionName']}: {e}")
    
    def _get_mock_lambda_code(self, function_type: str) -> bytes:
        """Generate mock Lambda function code for testing"""
        
        if function_type == 'hmac_authorizer':
            code = '''
import json
import time

def lambda_handler(event, context):
    # Mock HMAC authorizer for testing
    return {
        "principalId": "test-user",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": "*"
                }
            ]
        },
        "context": {
            "tenant_id": event.get("headers", {}).get("X-Tenant-ID"),
            "validated_at": str(time.time())
        }
    }
'''
        elif function_type == 'event_processor':
            code = '''
import json
import time

def lambda_handler(event, context):
    # Mock event processor for testing
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Event processed successfully",
            "processed_at": time.time(),
            "event_count": len(event.get("Records", [])),
            "test_mode": True
        })
    }
'''
        elif function_type == 'smart_connector':
            code = '''
import json
import time

def lambda_handler(event, context):
    # Mock smart connector for testing
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Webhook delivered successfully",
            "delivered_at": time.time(),
            "destination": "test-webhook",
            "test_mode": True
        })
    }
'''
        else:
            code = '''
import json

def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Mock function response"})
    }
'''
        
        # Create a simple ZIP file with the Lambda code
        import zipfile
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('lambda_function.py', code)
        
        return zip_buffer.getvalue()
    
    def setup_api_gateway(self):
        """Setup API Gateway for testing"""
        print("🌐 Setting up API Gateway...")
        
        try:
            # Create REST API
            api = self.apigateway.create_rest_api(
                name='formbridge-test-api',
                description='Form-Bridge test API',
                endpointConfiguration={'types': ['REGIONAL']}
            )
            
            api_id = api['id']
            print(f"✅ Created API Gateway: {api_id}")
            
            # Get root resource
            resources = self.apigateway.get_resources(restApiId=api_id)
            root_id = None
            for resource in resources['items']:
                if resource['path'] == '/':
                    root_id = resource['id']
                    break
            
            if root_id:
                # Create /submit resource
                submit_resource = self.apigateway.create_resource(
                    restApiId=api_id,
                    parentId=root_id,
                    pathPart='submit'
                )
                
                # Create POST method
                self.apigateway.put_method(
                    restApiId=api_id,
                    resourceId=submit_resource['id'],
                    httpMethod='POST',
                    authorizationType='CUSTOM',
                    authorizerId='test-authorizer'
                )
                
                print("✅ Created API Gateway endpoints")
            
        except Exception as e:
            if 'already exists' in str(e) or 'TooManyRequestsException' in str(e):
                print("ℹ️ API Gateway resources already exist or rate limited")
            else:
                print(f"⚠️ Failed to setup API Gateway: {e}")
    
    def verify_infrastructure(self):
        """Verify all infrastructure components are working"""
        print("🔍 Verifying infrastructure...")
        
        # Verify DynamoDB
        try:
            table = self.dynamodb.Table('formbridge-test')
            response = table.scan(Limit=1)
            print("✅ DynamoDB table is accessible")
        except Exception as e:
            print(f"❌ DynamoDB verification failed: {e}")
            
        # Verify EventBridge
        try:
            buses = self.eventbridge.list_event_buses()
            bus_names = [bus['Name'] for bus in buses['EventBuses']]
            if 'formbridge-test-bus' in bus_names:
                print("✅ EventBridge bus is accessible")
            else:
                print("⚠️ EventBridge bus not found")
        except Exception as e:
            print(f"❌ EventBridge verification failed: {e}")
            
        # Verify Secrets Manager
        try:
            secrets = self.secretsmanager.list_secrets()
            secret_names = [secret['Name'] for secret in secrets['SecretList']]
            if any('formbridge' in name for name in secret_names):
                print("✅ Secrets Manager is accessible")
            else:
                print("⚠️ No FormBridge secrets found")
        except Exception as e:
            print(f"❌ Secrets Manager verification failed: {e}")
            
        # Verify Lambda
        try:
            functions = self.lambda_client.list_functions()
            function_names = [func['FunctionName'] for func in functions['Functions']]
            formbridge_functions = [name for name in function_names if 'formbridge' in name]
            if formbridge_functions:
                print(f"✅ Lambda functions are accessible: {len(formbridge_functions)} functions")
            else:
                print("⚠️ No FormBridge Lambda functions found")
        except Exception as e:
            print(f"❌ Lambda verification failed: {e}")


def main():
    """Main execution function"""
    print("🏗️ Form-Bridge Test Infrastructure Setup")
    print("=" * 50)
    
    setup = TestInfrastructureSetup()
    success = setup.setup_all()
    
    if success:
        print("\n🎉 All infrastructure components ready for testing!")
        print(f"LocalStack endpoint: {setup.endpoint_url}")
        print("You can now run the test suite.")
        return 0
    else:
        print("\n💥 Infrastructure setup failed!")
        print("Please check the errors above and retry.")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
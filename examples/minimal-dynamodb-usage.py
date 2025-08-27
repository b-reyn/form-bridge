#!/usr/bin/env python3
"""
Minimal DynamoDB Usage Example for Form-Bridge MVP

This script demonstrates how to use the bare-bones DynamoDB table
that was designed for reliable deployment.
"""

import boto3
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal
import uuid

class FormBridgeMinimalDB:
    """
    Minimal DynamoDB operations for Form-Bridge MVP
    
    This class provides basic operations for the simplified table structure
    without any of the advanced features that were removed for deployment.
    """
    
    def __init__(self, table_name: str = 'formbridge-data-dev'):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
    
    # ============================================
    # Tenant Management
    # ============================================
    
    def create_tenant_config(self, tenant_id: str, config: Dict) -> None:
        """Create or update tenant configuration"""
        try:
            self.table.put_item(
                Item={
                    'PK': f'TENANT#{tenant_id}',
                    'SK': 'CONFIG#main',
                    'GSI1PK': 'CONFIG#active',
                    'GSI1SK': f'TENANT#{tenant_id}',
                    'tenant_id': tenant_id,
                    'tenant_name': config.get('name', ''),
                    'api_key_hash': config.get('api_key_hash', ''),
                    'destinations': config.get('destinations', []),
                    'settings': config.get('settings', {}),
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }
            )
            print(f"✅ Created tenant config: {tenant_id}")
        except Exception as e:
            print(f"❌ Error creating tenant config: {e}")
    
    def get_tenant_config(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant configuration"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'TENANT#{tenant_id}',
                    'SK': 'CONFIG#main'
                }
            )
            return response.get('Item')
        except Exception as e:
            print(f"❌ Error getting tenant config: {e}")
            return None
    
    # ============================================
    # Destination Management  
    # ============================================
    
    def create_destination(self, tenant_id: str, dest_id: str, 
                          dest_config: Dict) -> None:
        """Create a delivery destination for a tenant"""
        try:
            self.table.put_item(
                Item={
                    'PK': f'TENANT#{tenant_id}',
                    'SK': f'DEST#{dest_id}',
                    'GSI1PK': f'TENANT#{tenant_id}',
                    'GSI1SK': f'DEST#{dest_config.get("type", "webhook")}#{datetime.utcnow().isoformat()}',
                    'tenant_id': tenant_id,
                    'destination_id': dest_id,
                    'destination_type': dest_config.get('type', 'webhook'),
                    'endpoint_url': dest_config.get('url', ''),
                    'auth_config': dest_config.get('auth', {}),
                    'enabled': dest_config.get('enabled', True),
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            print(f"✅ Created destination: {dest_id} for tenant {tenant_id}")
        except Exception as e:
            print(f"❌ Error creating destination: {e}")
    
    def get_tenant_destinations(self, tenant_id: str) -> List[Dict]:
        """Get all destinations for a tenant"""
        try:
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :dest)',
                ExpressionAttributeValues={
                    ':pk': f'TENANT#{tenant_id}',
                    ':dest': 'DEST#'
                }
            )
            return response.get('Items', [])
        except Exception as e:
            print(f"❌ Error getting destinations: {e}")
            return []
    
    # ============================================
    # Form Submission Management
    # ============================================
    
    def store_submission(self, tenant_id: str, form_data: Dict) -> str:
        """Store a form submission"""
        submission_id = str(uuid.uuid4())[:12]  # Short ID for demo
        timestamp = datetime.utcnow().isoformat()
        
        try:
            self.table.put_item(
                Item={
                    'PK': f'TENANT#{tenant_id}',
                    'SK': f'SUB#{submission_id}',
                    'GSI1PK': f'TENANT#{tenant_id}',
                    'GSI1SK': f'TS#{timestamp}',
                    'tenant_id': tenant_id,
                    'submission_id': submission_id,
                    'form_id': form_data.get('form_id', 'unknown'),
                    'payload': form_data.get('data', {}),
                    'status': 'pending',
                    'source_ip': form_data.get('source_ip', ''),
                    'user_agent': form_data.get('user_agent', ''),
                    'created_at': timestamp,
                    'updated_at': timestamp
                }
            )
            print(f"✅ Stored submission: {submission_id}")
            return submission_id
        except Exception as e:
            print(f"❌ Error storing submission: {e}")
            return ""
    
    def get_submission(self, tenant_id: str, submission_id: str) -> Optional[Dict]:
        """Get a specific submission"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'TENANT#{tenant_id}',
                    'SK': f'SUB#{submission_id}'
                }
            )
            return response.get('Item')
        except Exception as e:
            print(f"❌ Error getting submission: {e}")
            return None
    
    def update_submission_status(self, tenant_id: str, submission_id: str, 
                               status: str) -> None:
        """Update submission status"""
        try:
            self.table.update_item(
                Key={
                    'PK': f'TENANT#{tenant_id}',
                    'SK': f'SUB#{submission_id}'
                },
                UpdateExpression='SET #status = :status, updated_at = :updated',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': status,
                    ':updated': datetime.utcnow().isoformat()
                }
            )
            print(f"✅ Updated submission {submission_id} status to: {status}")
        except Exception as e:
            print(f"❌ Error updating submission status: {e}")
    
    def list_recent_submissions(self, tenant_id: str, limit: int = 20) -> List[Dict]:
        """List recent submissions for a tenant using GSI"""
        try:
            response = self.table.query(
                IndexName='TenantIndex',
                KeyConditionExpression='GSI1PK = :tenant',
                ExpressionAttributeValues={
                    ':tenant': f'TENANT#{tenant_id}'
                },
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            # Filter only submissions (exclude config/destinations)
            submissions = [
                item for item in response.get('Items', [])
                if item.get('SK', '').startswith('SUB#')
            ]
            return submissions
        except Exception as e:
            print(f"❌ Error listing submissions: {e}")
            return []
    
    # ============================================
    # Utility Methods
    # ============================================
    
    def validate_table_access(self) -> bool:
        """Test basic table connectivity"""
        try:
            response = self.table.describe_table()
            print(f"✅ Table access validated: {response['Table']['TableName']}")
            print(f"   Status: {response['Table']['TableStatus']}")
            print(f"   Item Count: {response['Table']['ItemCount']}")
            return True
        except Exception as e:
            print(f"❌ Table access failed: {e}")
            return False
    
    def cleanup_test_data(self, tenant_id: str = 'test123') -> None:
        """Clean up test data (be careful with this!)"""
        try:
            # Get all items for the test tenant
            response = self.table.query(
                KeyConditionExpression='PK = :pk',
                ExpressionAttributeValues={
                    ':pk': f'TENANT#{tenant_id}'
                }
            )
            
            # Delete each item
            with self.table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(
                        Key={
                            'PK': item['PK'],
                            'SK': item['SK']
                        }
                    )
            
            print(f"✅ Cleaned up test data for tenant: {tenant_id}")
        except Exception as e:
            print(f"❌ Error cleaning up test data: {e}")

# ============================================
# Example Usage and Testing
# ============================================

def main():
    """Demonstrate minimal DynamoDB operations"""
    
    # Initialize the database client
    db = FormBridgeMinimalDB('formbridge-data-dev')
    
    print("🚀 Form-Bridge Minimal DynamoDB Demo")
    print("=" * 50)
    
    # Test table access
    if not db.validate_table_access():
        print("Cannot access table. Check AWS credentials and table name.")
        return
    
    # Test tenant and submission operations
    tenant_id = 'demo123'
    
    # 1. Create tenant configuration
    print("\n📋 Creating tenant configuration...")
    tenant_config = {
        'name': 'Demo Tenant',
        'api_key_hash': 'demo_hash_12345',
        'destinations': [
            {'id': 'webhook1', 'type': 'webhook', 'url': 'https://example.com/hook'}
        ],
        'settings': {
            'max_submissions_per_hour': 100,
            'retention_days': 30
        }
    }
    db.create_tenant_config(tenant_id, tenant_config)
    
    # 2. Create destination
    print("\n🎯 Creating destination...")
    db.create_destination(tenant_id, 'webhook1', {
        'type': 'webhook',
        'url': 'https://webhook.site/12345',
        'auth': {'type': 'bearer', 'token': 'secret123'},
        'enabled': True
    })
    
    # 3. Store some test submissions
    print("\n📝 Storing test submissions...")
    submission_ids = []
    
    for i in range(3):
        form_data = {
            'form_id': 'contact_form',
            'data': {
                'name': f'Test User {i+1}',
                'email': f'user{i+1}@example.com',
                'message': f'This is test message number {i+1}'
            },
            'source_ip': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 Test Browser'
        }
        
        sub_id = db.store_submission(tenant_id, form_data)
        if sub_id:
            submission_ids.append(sub_id)
            time.sleep(0.1)  # Small delay to ensure different timestamps
    
    # 4. Test retrieval operations
    print("\n🔍 Testing retrieval operations...")
    
    # Get tenant config
    config = db.get_tenant_config(tenant_id)
    if config:
        print(f"   Tenant: {config.get('tenant_name')}")
    
    # Get destinations
    destinations = db.get_tenant_destinations(tenant_id)
    print(f"   Destinations: {len(destinations)}")
    
    # Get specific submission
    if submission_ids:
        submission = db.get_submission(tenant_id, submission_ids[0])
        if submission:
            print(f"   Sample submission: {submission.get('form_id')} - {submission.get('status')}")
    
    # List recent submissions
    recent = db.list_recent_submissions(tenant_id, limit=10)
    print(f"   Recent submissions: {len(recent)}")
    
    # 5. Update submission status
    print("\n✏️ Updating submission status...")
    if submission_ids:
        db.update_submission_status(tenant_id, submission_ids[0], 'delivered')
    
    # 6. Final summary
    print("\n📊 Final Summary:")
    recent_updated = db.list_recent_submissions(tenant_id)
    for sub in recent_updated[:3]:  # Show first 3
        print(f"   📄 {sub.get('submission_id')}: {sub.get('status')} ({sub.get('form_id')})")
    
    print("\n✅ Demo completed successfully!")
    print("\n🧹 To clean up test data, uncomment the cleanup line below:")
    print("# db.cleanup_test_data(tenant_id)")
    
    # Uncomment to clean up test data:
    # db.cleanup_test_data(tenant_id)

if __name__ == '__main__':
    main()
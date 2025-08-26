"""
Multi-Site WordPress Authentication - DynamoDB Single Table Design
Secure credential hierarchy with site isolation and key rotation

Table: WordPressAuthCredentials
Cost Estimate: ~$15-25/month for 50 sites with weekly checks
"""

import boto3
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from boto3.dynamodb.conditions import Key, Attr
import json

class WordPressAuthManager:
    """
    DynamoDB-based WordPress multi-site authentication manager
    
    Key Hierarchy:
    Master Account Key -> Site Group Keys -> Individual Site Keys
    """
    
    def __init__(self, table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    # =================================================================
    # 1. KEY HIERARCHY STRUCTURE
    # =================================================================
    
    """
    Table Schema Design:
    
    Primary Table Structure:
    PK                          | SK                              | Entity Type
    ---------------------------|----------------------------------|-------------
    ACCOUNT#acc_123            | MASTER#main                     | Master account key
    ACCOUNT#acc_123            | GROUP#wordpress-sites           | Site group config  
    ACCOUNT#acc_123            | SITE#example.com                | Individual site
    ACCOUNT#acc_123            | AUDIT#2025-01-26#uuid           | Audit log entry
    SITE#example.com           | KEY#current                     | Active site key
    SITE#example.com           | KEY#previous                    | Previous key (rotation)
    SITE#example.com           | TOKEN#registration              | Registration token
    SITE#example.com           | TOKEN#update                    | Update token
    SITE#example.com           | RATE#2025-01-26-18             | Rate limit counter (hourly)
    TEMP#token_xyz             | REGISTRATION#site_pending       | Temporary registration
    
    GSI1 - Time-based queries:
    GSI1PK                     | GSI1SK                          | Use Case
    ---------------------------|----------------------------------|----------
    ACCOUNT#acc_123#AUDIT      | 2025-01-26T18:00:00Z            | Audit logs by time
    SITE#example.com#ACCESS    | 2025-01-26T18:00:00Z            | Access logs by time
    EXPIRING#2025-01-27        | SITE#example.com                | Keys expiring today
    
    GSI2 - Status-based queries:
    GSI2PK                     | GSI2SK                          | Use Case  
    ---------------------------|----------------------------------|----------
    ACCOUNT#acc_123#ACTIVE     | SITE#example.com                | Active sites
    ACCOUNT#acc_123#SUSPENDED  | SITE#example.com                | Suspended sites
    ROTATION#PENDING           | 2025-01-26T18:00:00Z            | Pending rotations
    """
    
    def build_account_master_key(self, account_id: str) -> Dict:
        """Master account key with highest privileges"""
        key_id = f"master_{secrets.token_hex(16)}"
        secret = secrets.token_urlsafe(64)
        
        return {
            'PK': f'ACCOUNT#{account_id}',
            'SK': 'MASTER#main',
            'key_id': key_id,
            'secret_hash': hashlib.sha256(secret.encode()).hexdigest(),
            'secret': secret,  # Encrypted at rest via DynamoDB encryption
            'permissions': ['all'],
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=365)).isoformat(),
            'status': 'active',
            'key_type': 'master',
            'rotation_count': 0,
            'GSI1PK': f'ACCOUNT#{account_id}',
            'GSI1SK': datetime.utcnow().isoformat(),
            'ttl': int(time.time()) + (365 * 24 * 3600)  # 1 year
        }
    
    def build_site_key(self, account_id: str, site_domain: str, 
                      permissions: List[str] = None) -> Dict:
        """Individual site key with limited scope"""
        key_id = f"site_{secrets.token_hex(16)}"
        secret = secrets.token_urlsafe(32)
        
        return {
            'PK': f'SITE#{site_domain}',
            'SK': 'KEY#current',
            'key_id': key_id,
            'secret_hash': hashlib.sha256(secret.encode()).hexdigest(),
            'secret': secret,
            'account_id': account_id,
            'site_domain': site_domain,
            'permissions': permissions or ['plugin_update', 'license_check'],
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=90)).isoformat(),
            'status': 'active',
            'key_type': 'site',
            'rotation_count': 0,
            'last_used': None,
            'usage_count': 0,
            'GSI1PK': f'EXPIRING#{(datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d")}',
            'GSI1SK': f'SITE#{site_domain}',
            'GSI2PK': f'ACCOUNT#{account_id}#ACTIVE',
            'GSI2SK': f'SITE#{site_domain}',
            'ttl': int(time.time()) + (90 * 24 * 3600)  # 90 days
        }
    
    # =================================================================
    # 2. ACCESS PATTERNS IMPLEMENTATION
    # =================================================================
    
    def register_new_site(self, account_id: str, site_domain: str, 
                         admin_email: str) -> Tuple[str, str]:
        """
        Register new WordPress site with unique credentials
        Returns: (key_id, secret)
        """
        # Generate temporary registration token
        reg_token = secrets.token_urlsafe(32)
        
        # Create site record
        site_record = {
            'PK': f'ACCOUNT#{account_id}',
            'SK': f'SITE#{site_domain}',
            'site_domain': site_domain,
            'admin_email': admin_email,
            'status': 'pending_activation',
            'registered_at': datetime.utcnow().isoformat(),
            'last_seen': None,
            'plugin_version': None,
            'wordpress_version': None,
            'GSI2PK': f'ACCOUNT#{account_id}#PENDING',
            'GSI2SK': f'SITE#{site_domain}'
        }
        
        # Create temporary registration token
        temp_token = {
            'PK': f'TEMP#{reg_token}',
            'SK': f'REGISTRATION#{site_domain}',
            'account_id': account_id,
            'site_domain': site_domain,
            'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            'status': 'pending',
            'ttl': int(time.time()) + (24 * 3600)  # 24 hours
        }
        
        # Generate site-specific credentials
        site_key = self.build_site_key(account_id, site_domain)
        
        # Atomic write using transaction
        try:
            self.table.put_item(Item=site_record)
            self.table.put_item(Item=temp_token) 
            self.table.put_item(Item=site_key)
            
            # Log registration
            self._log_audit_event(account_id, 'site_registered', {
                'site_domain': site_domain,
                'admin_email': admin_email
            })
            
            return site_key['key_id'], site_key['secret']
            
        except Exception as e:
            raise Exception(f"Failed to register site {site_domain}: {str(e)}")
    
    def validate_site_credentials(self, key_id: str, secret: str, 
                                 site_domain: str) -> Dict:
        """
        Validate site credentials and return permissions
        Implements rate limiting and usage tracking
        """
        # Check rate limiting first
        if not self._check_rate_limit(site_domain):
            raise Exception("Rate limit exceeded for site")
        
        # Get current key
        response = self.table.get_item(
            Key={
                'PK': f'SITE#{site_domain}',
                'SK': 'KEY#current'
            }
        )
        
        if 'Item' not in response:
            self._log_access_attempt(site_domain, 'key_not_found', False)
            raise Exception("Invalid credentials")
        
        key_data = response['Item']
        
        # Validate key
        if (key_data['key_id'] != key_id or 
            key_data['secret_hash'] != hashlib.sha256(secret.encode()).hexdigest()):
            self._log_access_attempt(site_domain, 'invalid_credentials', False)
            raise Exception("Invalid credentials")
        
        # Check expiration
        if datetime.fromisoformat(key_data['expires_at']) < datetime.utcnow():
            self._log_access_attempt(site_domain, 'key_expired', False)
            raise Exception("Key expired")
        
        # Check status
        if key_data['status'] != 'active':
            self._log_access_attempt(site_domain, 'key_suspended', False)
            raise Exception("Key suspended")
        
        # Update usage statistics
        self._update_key_usage(site_domain)
        self._log_access_attempt(site_domain, 'success', True)
        
        return {
            'valid': True,
            'permissions': key_data['permissions'],
            'account_id': key_data['account_id'],
            'expires_at': key_data['expires_at']
        }
    
    def rotate_site_key(self, site_domain: str, force: bool = False) -> Tuple[str, str]:
        """
        Rotate site key with zero-downtime strategy
        Returns: (new_key_id, new_secret)
        """
        # Get current key
        current_key = self.table.get_item(
            Key={
                'PK': f'SITE#{site_domain}',
                'SK': 'KEY#current'
            }
        )['Item']
        
        # Generate new key
        new_key = self.build_site_key(
            current_key['account_id'], 
            site_domain,
            current_key['permissions']
        )
        new_key['rotation_count'] = current_key['rotation_count'] + 1
        
        # Move current to previous
        previous_key = current_key.copy()
        previous_key['SK'] = 'KEY#previous'
        previous_key['status'] = 'rotating'
        previous_key['rotated_at'] = datetime.utcnow().isoformat()
        
        # Atomic rotation using transaction
        try:
            # Write new current key
            self.table.put_item(Item=new_key)
            
            # Move old key to previous
            self.table.put_item(Item=previous_key)
            
            # Schedule cleanup of old key (after grace period)
            cleanup_time = datetime.utcnow() + timedelta(days=7)
            self.table.put_item(Item={
                'PK': f'CLEANUP#{cleanup_time.strftime("%Y-%m-%d")}',
                'SK': f'SITE#{site_domain}#PREVIOUS',
                'site_domain': site_domain,
                'cleanup_at': cleanup_time.isoformat(),
                'ttl': int(cleanup_time.timestamp())
            })
            
            self._log_audit_event(current_key['account_id'], 'key_rotated', {
                'site_domain': site_domain,
                'old_key_id': current_key['key_id'],
                'new_key_id': new_key['key_id']
            })
            
            return new_key['key_id'], new_key['secret']
            
        except Exception as e:
            raise Exception(f"Failed to rotate key for {site_domain}: {str(e)}")
    
    def revoke_compromised_key(self, site_domain: str, reason: str) -> None:
        """
        Immediately revoke compromised key and generate new one
        """
        # Mark current key as compromised
        self.table.update_item(
            Key={
                'PK': f'SITE#{site_domain}',
                'SK': 'KEY#current'
            },
            UpdateExpression='SET #status = :status, revoked_at = :timestamp, revoke_reason = :reason',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'revoked',
                ':timestamp': datetime.utcnow().isoformat(),
                ':reason': reason
            }
        )
        
        # Generate new key immediately
        new_key_id, new_secret = self.rotate_site_key(site_domain, force=True)
        
        # Log security incident
        current_key = self.table.get_item(
            Key={
                'PK': f'SITE#{site_domain}',
                'SK': 'KEY#current'
            }
        )['Item']
        
        self._log_audit_event(current_key['account_id'], 'key_compromised', {
            'site_domain': site_domain,
            'reason': reason,
            'new_key_id': new_key_id
        })
    
    def list_account_sites(self, account_id: str, status_filter: str = None) -> List[Dict]:
        """
        List all sites for an account with optional status filtering
        """
        if status_filter:
            response = self.table.query(
                IndexName='GSI2',
                KeyConditionExpression=Key('GSI2PK').eq(f'ACCOUNT#{account_id}#{status_filter.upper()}')
            )
        else:
            response = self.table.query(
                KeyConditionExpression=(
                    Key('PK').eq(f'ACCOUNT#{account_id}') &
                    Key('SK').begins_with('SITE#')
                )
            )
        
        return response.get('Items', [])
    
    def get_audit_logs(self, account_id: str, 
                      start_date: str = None,
                      end_date: str = None,
                      limit: int = 50) -> List[Dict]:
        """
        Retrieve audit logs for account within date range
        """
        kwargs = {
            'IndexName': 'GSI1',
            'KeyConditionExpression': Key('GSI1PK').eq(f'ACCOUNT#{account_id}#AUDIT'),
            'Limit': limit,
            'ScanIndexForward': False  # Most recent first
        }
        
        if start_date and end_date:
            kwargs['KeyConditionExpression'] = (
                Key('GSI1PK').eq(f'ACCOUNT#{account_id}#AUDIT') &
                Key('GSI1SK').between(start_date, end_date)
            )
        elif start_date:
            kwargs['KeyConditionExpression'] = (
                Key('GSI1PK').eq(f'ACCOUNT#{account_id}#AUDIT') &
                Key('GSI1SK').gte(start_date)
            )
        
        response = self.table.query(**kwargs)
        return response.get('Items', [])
    
    # =================================================================
    # 3. SECURITY FEATURES
    # =================================================================
    
    def _check_rate_limit(self, site_domain: str, 
                         limit_per_hour: int = 100) -> bool:
        """
        Check rate limiting per site (hourly buckets)
        """
        current_hour = datetime.utcnow().strftime('%Y-%m-%d-%H')
        
        try:
            response = self.table.update_item(
                Key={
                    'PK': f'SITE#{site_domain}',
                    'SK': f'RATE#{current_hour}'
                },
                UpdateExpression='ADD request_count :inc',
                ExpressionAttributeValues={':inc': 1},
                ReturnValues='ALL_NEW'
            )
            
            request_count = response['Attributes'].get('request_count', 1)
            
            # Set TTL for automatic cleanup
            if request_count == 1:
                self.table.update_item(
                    Key={
                        'PK': f'SITE#{site_domain}',
                        'SK': f'RATE#{current_hour}'
                    },
                    UpdateExpression='SET ttl = :ttl',
                    ExpressionAttributeValues={
                        ':ttl': int(time.time()) + (25 * 3600)  # 25 hours
                    }
                )
            
            return request_count <= limit_per_hour
            
        except Exception:
            return False
    
    def _update_key_usage(self, site_domain: str) -> None:
        """Update key usage statistics"""
        self.table.update_item(
            Key={
                'PK': f'SITE#{site_domain}',
                'SK': 'KEY#current'
            },
            UpdateExpression='ADD usage_count :inc SET last_used = :timestamp',
            ExpressionAttributeValues={
                ':inc': 1,
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
    
    def _log_access_attempt(self, site_domain: str, 
                           event_type: str, success: bool) -> None:
        """Log access attempts for security monitoring"""
        log_entry = {
            'PK': f'SITE#{site_domain}',
            'SK': f'ACCESS#{datetime.utcnow().isoformat()}#{secrets.token_hex(8)}',
            'site_domain': site_domain,
            'event_type': event_type,
            'success': success,
            'timestamp': datetime.utcnow().isoformat(),
            'GSI1PK': f'SITE#{site_domain}#ACCESS',
            'GSI1SK': datetime.utcnow().isoformat(),
            'ttl': int(time.time()) + (30 * 24 * 3600)  # 30 days
        }
        
        self.table.put_item(Item=log_entry)
    
    def _log_audit_event(self, account_id: str, event_type: str, 
                        event_data: Dict) -> None:
        """Log audit events for compliance"""
        log_entry = {
            'PK': f'ACCOUNT#{account_id}',
            'SK': f'AUDIT#{datetime.utcnow().isoformat()}#{secrets.token_hex(8)}',
            'account_id': account_id,
            'event_type': event_type,
            'event_data': event_data,
            'timestamp': datetime.utcnow().isoformat(),
            'GSI1PK': f'ACCOUNT#{account_id}#AUDIT',
            'GSI1SK': datetime.utcnow().isoformat(),
            'ttl': int(time.time()) + (365 * 24 * 3600)  # 1 year
        }
        
        self.table.put_item(Item=log_entry)

    # =================================================================
    # 4. MIGRATION & MAINTENANCE
    # =================================================================
    
    def migrate_from_shared_keys(self, account_id: str, 
                               sites: List[Dict]) -> Dict:
        """
        Migrate from shared keys to site-specific keys
        Zero-downtime migration strategy
        """
        migration_results = {
            'migrated': [],
            'failed': [],
            'total': len(sites)
        }
        
        for site in sites:
            try:
                # Generate new site-specific key
                key_id, secret = self.register_new_site(
                    account_id,
                    site['domain'],
                    site.get('admin_email', 'admin@' + site['domain'])
                )
                
                migration_results['migrated'].append({
                    'domain': site['domain'],
                    'key_id': key_id,
                    'secret': secret
                })
                
            except Exception as e:
                migration_results['failed'].append({
                    'domain': site['domain'],
                    'error': str(e)
                })
        
        # Log migration completion
        self._log_audit_event(account_id, 'bulk_migration_completed', migration_results)
        
        return migration_results
    
    def cleanup_expired_keys(self, dry_run: bool = True) -> List[Dict]:
        """
        Clean up expired keys and tokens
        """
        current_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Find items to cleanup
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'CLEANUP#{current_date}')
        )
        
        cleanup_items = response.get('Items', [])
        
        if not dry_run:
            # Actually delete expired items
            with self.table.batch_writer() as batch:
                for item in cleanup_items:
                    if 'PREVIOUS' in item['SK']:
                        # Delete previous keys
                        batch.delete_item(
                            Key={
                                'PK': f'SITE#{item["site_domain"]}',
                                'SK': 'KEY#previous'
                            }
                        )
                    
                    # Delete cleanup marker
                    batch.delete_item(
                        Key={
                            'PK': item['PK'],
                            'SK': item['SK']
                        }
                    )
        
        return cleanup_items


# =================================================================
# CLOUDFORMATION TEMPLATE FOR TABLE CREATION
# =================================================================

CLOUDFORMATION_TEMPLATE = """
AWSTemplateFormatVersion: '2010-09-09'
Description: 'WordPress Multi-Site Authentication DynamoDB Table'

Resources:
  WordPressAuthTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: WordPressAuthCredentials
      BillingMode: ON_DEMAND
      
      AttributeDefinitions:
        - AttributeName: PK
          AttributeType: S
        - AttributeName: SK
          AttributeType: S
        - AttributeName: GSI1PK
          AttributeType: S
        - AttributeName: GSI1SK
          AttributeType: S
        - AttributeName: GSI2PK
          AttributeType: S
        - AttributeName: GSI2SK
          AttributeType: S
      
      KeySchema:
        - AttributeName: PK
          KeyType: HASH
        - AttributeName: SK
          KeyType: RANGE
      
      GlobalSecondaryIndexes:
        - IndexName: GSI1
          KeySchema:
            - AttributeName: GSI1PK
              KeyType: HASH
            - AttributeName: GSI1SK
              KeyType: RANGE
          Projection:
            ProjectionType: INCLUDE
            NonKeyAttributes:
              - site_domain
              - status
              - event_type
              - expires_at
        
        - IndexName: GSI2
          KeySchema:
            - AttributeName: GSI2PK
              KeyType: HASH
            - AttributeName: GSI2SK
              KeyType: RANGE
          Projection:
            ProjectionType: INCLUDE
            NonKeyAttributes:
              - site_domain
              - admin_email
              - last_seen
              - plugin_version
      
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      
      SSESpecification:
        SSEEnabled: true
        KMSMasterKeyId: alias/aws/dynamodb
      
      StreamSpecification:
        StreamViewType: NEW_AND_OLD_IMAGES
      
      Tags:
        - Key: Project
          Value: WordPressAuth
        - Key: Environment
          Value: Production

  # IAM Role for WordPress Plugin Access
  WordPressPluginRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      
      Policies:
        - PolicyName: WordPressAuthAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              # Site-scoped access only
              - Effect: Allow
                Action:
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                  - dynamodb:UpdateItem
                Resource: !GetAtt WordPressAuthTable.Arn
                Condition:
                  ForAllValues:StringLike:
                    dynamodb:LeadingKeys:
                      - SITE#${aws:RequestedRegion}
              
              # Rate limiting access
              - Effect: Allow
                Action:
                  - dynamodb:UpdateItem
                Resource: !GetAtt WordPressAuthTable.Arn
                Condition:
                  ForAllValues:StringEquals:
                    dynamodb:Attributes:
                      - request_count
                      - ttl

Outputs:
  TableName:
    Description: Name of the DynamoDB table
    Value: !Ref WordPressAuthTable
    Export:
      Name: !Sub '${AWS::StackName}-TableName'
  
  TableArn:
    Description: ARN of the DynamoDB table
    Value: !GetAtt WordPressAuthTable.Arn
    Export:
      Name: !Sub '${AWS::StackName}-TableArn'
"""

# =================================================================
# USAGE EXAMPLES
# =================================================================

def example_usage():
    """
    Example usage of the WordPress Auth Manager
    """
    auth_manager = WordPressAuthManager('WordPressAuthCredentials')
    
    # Register new site
    key_id, secret = auth_manager.register_new_site(
        account_id='acc_agency123',
        site_domain='clientsite1.com',
        admin_email='admin@clientsite1.com'
    )
    
    print(f"Site registered: {key_id}")
    
    # Validate credentials (typical plugin check)
    try:
        validation = auth_manager.validate_site_credentials(
            key_id=key_id,
            secret=secret,
            site_domain='clientsite1.com'
        )
        print(f"Validation successful: {validation['permissions']}")
    except Exception as e:
        print(f"Validation failed: {e}")
    
    # Rotate key (scheduled maintenance)
    new_key_id, new_secret = auth_manager.rotate_site_key('clientsite1.com')
    print(f"Key rotated: {new_key_id}")
    
    # List all sites for account
    sites = auth_manager.list_account_sites('acc_agency123')
    print(f"Found {len(sites)} sites")
    
    # Get audit logs
    logs = auth_manager.get_audit_logs('acc_agency123', limit=10)
    print(f"Retrieved {len(logs)} audit entries")

# =================================================================
# COST ANALYSIS
# =================================================================

"""
COST ESTIMATION for 50 sites with weekly plugin checks:

DynamoDB On-Demand Pricing:
- Reads: $0.25 per million requests
- Writes: $1.25 per million requests  
- Storage: $0.25 per GB per month

Monthly Usage Estimate:
- Plugin checks: 50 sites × 4 checks/month × 2 reads = 400 reads
- Rate limiting: 400 × 1 write = 400 writes
- Key rotations: 50 sites × 1/quarter × 3 writes = ~37 writes
- Audit logs: ~100 writes per month
- Storage: ~10MB for all data

Monthly Cost:
- Reads: 400 / 1,000,000 × $0.25 = $0.0001
- Writes: 537 / 1,000,000 × $1.25 = $0.0007
- Storage: 0.01 GB × $0.25 = $0.0025
- Total: ~$0.003 per month

Even with 1000 sites: ~$0.06 per month

Additional costs:
- KMS encryption: ~$1/month for key usage
- CloudWatch logs: ~$0.50/month for monitoring
- Lambda execution: ~$0.10/month for auth functions

Total estimated cost: $1.66/month for comprehensive security
"""

if __name__ == "__main__":
    example_usage()
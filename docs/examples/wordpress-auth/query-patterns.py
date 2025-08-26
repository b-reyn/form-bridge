"""
WordPress Authentication - Advanced Query Patterns & Migration Strategies
Comprehensive examples for all access patterns with performance optimization
"""

import boto3
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime, timedelta
import json

class AdvancedWordPressQueries:
    """
    Advanced query patterns for WordPress authentication system
    Optimized for performance and cost efficiency
    """
    
    def __init__(self, table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    # =================================================================
    # COMPLEX QUERY PATTERNS
    # =================================================================
    
    def get_sites_expiring_soon(self, days_ahead: int = 7) -> dict:
        """
        Find all sites with keys expiring in next N days
        Uses GSI1 for efficient time-based querying
        """
        expiry_dates = []
        base_date = datetime.utcnow()
        
        for i in range(days_ahead):
            check_date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            expiry_dates.append(check_date)
        
        expiring_sites = {}
        
        for date in expiry_dates:
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq(f'EXPIRING#{date}'),
                ProjectionExpression='GSI1SK, expires_at, account_id',
                Limit=100
            )
            
            for item in response['Items']:
                site_domain = item['GSI1SK'].replace('SITE#', '')
                expiring_sites[site_domain] = {
                    'expires_at': item['expires_at'],
                    'account_id': item['account_id'],
                    'days_until_expiry': (
                        datetime.fromisoformat(item['expires_at']) - datetime.utcnow()
                    ).days
                }
        
        return expiring_sites
    
    def get_high_traffic_sites(self, account_id: str, 
                              min_requests: int = 1000) -> list:
        """
        Find sites with high API usage for capacity planning
        Aggregates rate limit data across time periods
        """
        # Get all sites for account first
        sites = self.list_account_sites_minimal(account_id)
        high_traffic_sites = []
        
        for site in sites:
            site_domain = site['site_domain']
            
            # Query rate limit records for last 24 hours
            current_time = datetime.utcnow()
            rate_records = []
            
            for hour_offset in range(24):
                hour_key = (current_time - timedelta(hours=hour_offset)).strftime('%Y-%m-%d-%H')
                
                try:
                    response = self.table.get_item(
                        Key={
                            'PK': f'SITE#{site_domain}',
                            'SK': f'RATE#{hour_key}'
                        },
                        ProjectionExpression='request_count'
                    )
                    
                    if 'Item' in response:
                        rate_records.append(response['Item']['request_count'])
                        
                except Exception:
                    continue
            
            total_requests = sum(rate_records)
            if total_requests >= min_requests:
                high_traffic_sites.append({
                    'site_domain': site_domain,
                    'total_requests_24h': total_requests,
                    'avg_requests_per_hour': total_requests / max(len(rate_records), 1),
                    'peak_hour_requests': max(rate_records) if rate_records else 0
                })
        
        return sorted(high_traffic_sites, key=lambda x: x['total_requests_24h'], reverse=True)
    
    def get_security_incidents(self, account_id: str = None, 
                              days_back: int = 30) -> list:
        """
        Query security-related events across all or specific account
        """
        start_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        security_events = []
        
        if account_id:
            # Account-specific security events
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=(
                    Key('GSI1PK').eq(f'ACCOUNT#{account_id}#AUDIT') &
                    Key('GSI1SK').gte(start_date)
                ),
                FilterExpression=Attr('event_type').is_in([
                    'key_compromised', 'invalid_credentials', 
                    'key_expired', 'rate_limit_exceeded'
                ]),
                ScanIndexForward=False  # Most recent first
            )
            security_events.extend(response['Items'])
        else:
            # Global security scanning (expensive - use sparingly)
            response = self.table.scan(
                FilterExpression=(
                    Attr('event_type').is_in([
                        'key_compromised', 'invalid_credentials',
                        'key_expired', 'rate_limit_exceeded'
                    ]) &
                    Attr('timestamp').gte(start_date)
                ),
                ProjectionExpression='PK, event_type, timestamp, event_data'
            )
            security_events.extend(response['Items'])
        
        return security_events
    
    def batch_validate_sites(self, site_credentials: list) -> dict:
        """
        Efficiently validate multiple site credentials in batch
        Uses BatchGetItem for optimal performance
        """
        if len(site_credentials) > 100:
            raise ValueError("Batch size cannot exceed 100 items")
        
        # Build batch keys
        batch_keys = []
        for cred in site_credentials:
            batch_keys.append({
                'PK': f'SITE#{cred["site_domain"]}',
                'SK': 'KEY#current'
            })
        
        # Batch get current keys
        response = self.dynamodb.batch_get_item(
            RequestItems={
                self.table.table_name: {
                    'Keys': batch_keys,
                    'ProjectionExpression': 'PK, SK, key_id, secret_hash, expires_at, #status, permissions',
                    'ExpressionAttributeNames': {'#status': 'status'}
                }
            }
        )
        
        # Process results
        validation_results = {'valid': [], 'invalid': [], 'expired': [], 'missing': []}
        found_items = {item['PK']: item for item in response['Responses'][self.table.table_name]}
        
        for cred in site_credentials:
            pk = f'SITE#{cred["site_domain"]}'
            
            if pk not in found_items:
                validation_results['missing'].append(cred['site_domain'])
                continue
            
            item = found_items[pk]
            
            # Check expiration
            if datetime.fromisoformat(item['expires_at']) < datetime.utcnow():
                validation_results['expired'].append({
                    'site_domain': cred['site_domain'],
                    'expired_at': item['expires_at']
                })
                continue
            
            # Validate credentials
            import hashlib
            expected_hash = hashlib.sha256(cred['secret'].encode()).hexdigest()
            
            if (item['key_id'] == cred['key_id'] and 
                item['secret_hash'] == expected_hash and
                item['status'] == 'active'):
                
                validation_results['valid'].append({
                    'site_domain': cred['site_domain'],
                    'permissions': item['permissions']
                })
            else:
                validation_results['invalid'].append(cred['site_domain'])
        
        return validation_results
    
    # =================================================================
    # MIGRATION STRATEGIES
    # =================================================================
    
    def zero_downtime_migration(self, old_shared_key: str, 
                               account_mapping: dict) -> dict:
        """
        Zero-downtime migration from shared key to site-specific keys
        
        Strategy:
        1. Create new site-specific keys alongside old shared key
        2. Allow both keys to work during transition period
        3. Monitor usage and switch over sites gradually
        4. Deprecate old shared key after all sites migrated
        """
        migration_log = {
            'started_at': datetime.utcnow().isoformat(),
            'phases': {},
            'total_sites': sum(len(sites) for sites in account_mapping.values()),
            'migrated_count': 0,
            'errors': []
        }
        
        # Phase 1: Create new site-specific keys
        migration_log['phases']['key_generation'] = {
            'started_at': datetime.utcnow().isoformat(),
            'status': 'in_progress'
        }
        
        new_credentials = {}
        
        try:
            for account_id, sites in account_mapping.items():
                new_credentials[account_id] = {}
                
                for site_info in sites:
                    # Generate new site key
                    site_key = self.build_site_key(
                        account_id, 
                        site_info['domain'],
                        site_info.get('permissions', ['plugin_update', 'license_check'])
                    )
                    
                    # Store with migration marker
                    site_key['migration_batch'] = datetime.utcnow().isoformat()
                    site_key['old_shared_key_hash'] = hashlib.sha256(old_shared_key.encode()).hexdigest()
                    
                    self.table.put_item(Item=site_key)
                    
                    new_credentials[account_id][site_info['domain']] = {
                        'key_id': site_key['key_id'],
                        'secret': site_key['secret'],
                        'created_at': site_key['created_at']
                    }
                    
                    migration_log['migrated_count'] += 1
            
            migration_log['phases']['key_generation']['status'] = 'completed'
            migration_log['phases']['key_generation']['completed_at'] = datetime.utcnow().isoformat()
            
        except Exception as e:
            migration_log['phases']['key_generation']['status'] = 'failed'
            migration_log['phases']['key_generation']['error'] = str(e)
            migration_log['errors'].append(f"Key generation failed: {e}")
            return migration_log
        
        # Phase 2: Create compatibility layer for dual-key support
        migration_log['phases']['compatibility_setup'] = {
            'started_at': datetime.utcnow().isoformat(),
            'status': 'in_progress'
        }
        
        try:
            # Store shared key compatibility info
            shared_key_record = {
                'PK': 'MIGRATION#SHARED_KEY',
                'SK': f'COMPATIBILITY#{datetime.utcnow().isoformat()}',
                'shared_key_hash': hashlib.sha256(old_shared_key.encode()).hexdigest(),
                'migration_batch': datetime.utcnow().isoformat(),
                'accounts': list(account_mapping.keys()),
                'status': 'active',
                'expires_at': (datetime.utcnow() + timedelta(days=30)).isoformat(),
                'ttl': int(time.time()) + (30 * 24 * 3600)
            }
            
            self.table.put_item(Item=shared_key_record)
            
            migration_log['phases']['compatibility_setup']['status'] = 'completed'
            migration_log['phases']['compatibility_setup']['completed_at'] = datetime.utcnow().isoformat()
            
        except Exception as e:
            migration_log['phases']['compatibility_setup']['status'] = 'failed'
            migration_log['phases']['compatibility_setup']['error'] = str(e)
            migration_log['errors'].append(f"Compatibility setup failed: {e}")
        
        # Phase 3: Monitor and track adoption
        migration_log['phases']['monitoring'] = {
            'started_at': datetime.utcnow().isoformat(),
            'status': 'ongoing',
            'instructions': [
                "Monitor site usage patterns for next 30 days",
                "Track which sites are using old vs new keys",
                "Send migration notices to site administrators",
                "Plan deprecation of shared key after 95% adoption"
            ]
        }
        
        migration_log['completed_at'] = datetime.utcnow().isoformat()
        migration_log['new_credentials'] = new_credentials
        
        return migration_log
    
    def track_migration_progress(self, migration_batch: str) -> dict:
        """
        Track progress of ongoing migration
        """
        # Get all migrated keys from batch
        migrated_sites = self.table.scan(
            FilterExpression=Attr('migration_batch').eq(migration_batch),
            ProjectionExpression='site_domain, last_used, usage_count, created_at'
        )['Items']
        
        # Get shared key usage
        shared_key_usage = self.table.query(
            KeyConditionExpression=Key('PK').eq('MIGRATION#SHARED_KEY'),
            FilterExpression=Attr('migration_batch').eq(migration_batch)
        )['Items']
        
        total_sites = len(migrated_sites)
        sites_using_new_keys = len([s for s in migrated_sites if s.get('last_used')])
        adoption_rate = (sites_using_new_keys / total_sites * 100) if total_sites > 0 else 0
        
        return {
            'migration_batch': migration_batch,
            'total_migrated_sites': total_sites,
            'sites_using_new_keys': sites_using_new_keys,
            'adoption_rate_percent': adoption_rate,
            'sites_not_migrated': [
                s['site_domain'] for s in migrated_sites 
                if not s.get('last_used')
            ],
            'ready_for_deprecation': adoption_rate >= 95.0,
            'shared_key_info': shared_key_usage[0] if shared_key_usage else None
        }
    
    def finalize_migration(self, migration_batch: str, 
                          force: bool = False) -> dict:
        """
        Finalize migration by removing shared key compatibility
        """
        progress = self.track_migration_progress(migration_batch)
        
        if not force and not progress['ready_for_deprecation']:
            return {
                'status': 'not_ready',
                'message': f"Only {progress['adoption_rate_percent']:.1f}% adoption rate",
                'recommendation': 'Wait for 95% adoption or use force=True'
            }
        
        # Remove shared key compatibility
        try:
            # Delete shared key record
            shared_key_items = self.table.query(
                KeyConditionExpression=Key('PK').eq('MIGRATION#SHARED_KEY'),
                FilterExpression=Attr('migration_batch').eq(migration_batch)
            )['Items']
            
            for item in shared_key_items:
                self.table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']}
                )
            
            # Update migrated keys to remove migration markers
            migrated_sites = self.table.scan(
                FilterExpression=Attr('migration_batch').eq(migration_batch)
            )['Items']
            
            for site in migrated_sites:
                self.table.update_item(
                    Key={'PK': site['PK'], 'SK': site['SK']},
                    UpdateExpression='REMOVE migration_batch, old_shared_key_hash'
                )
            
            return {
                'status': 'completed',
                'finalized_at': datetime.utcnow().isoformat(),
                'sites_finalized': len(migrated_sites),
                'shared_keys_removed': len(shared_key_items)
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'recommendation': 'Check logs and retry'
            }
    
    # =================================================================
    # ROLLBACK PROCEDURES
    # =================================================================
    
    def emergency_rollback(self, migration_batch: str, 
                          shared_key_backup: str) -> dict:
        """
        Emergency rollback procedure for failed migrations
        """
        rollback_log = {
            'started_at': datetime.utcnow().isoformat(),
            'migration_batch': migration_batch,
            'status': 'in_progress'
        }
        
        try:
            # 1. Restore shared key compatibility
            shared_key_record = {
                'PK': 'MIGRATION#SHARED_KEY',
                'SK': f'ROLLBACK#{datetime.utcnow().isoformat()}',
                'shared_key_hash': hashlib.sha256(shared_key_backup.encode()).hexdigest(),
                'status': 'emergency_restored',
                'restored_at': datetime.utcnow().isoformat(),
                'original_batch': migration_batch,
                'expires_at': (datetime.utcnow() + timedelta(days=7)).isoformat(),
                'ttl': int(time.time()) + (7 * 24 * 3600)
            }
            
            self.table.put_item(Item=shared_key_record)
            
            # 2. Mark migrated keys as suspended (don't delete for audit)
            migrated_sites = self.table.scan(
                FilterExpression=Attr('migration_batch').eq(migration_batch)
            )['Items']
            
            suspended_count = 0
            for site in migrated_sites:
                self.table.update_item(
                    Key={'PK': site['PK'], 'SK': site['SK']},
                    UpdateExpression='SET #status = :status, rollback_at = :timestamp',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': 'rollback_suspended',
                        ':timestamp': datetime.utcnow().isoformat()
                    }
                )
                suspended_count += 1
            
            rollback_log.update({
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat(),
                'shared_key_restored': True,
                'sites_suspended': suspended_count,
                'next_steps': [
                    'Shared key is restored and active for 7 days',
                    'Investigate migration issues before retrying',
                    'Suspended site keys are preserved for audit'
                ]
            })
            
        except Exception as e:
            rollback_log.update({
                'status': 'failed',
                'error': str(e),
                'emergency_contact': 'Manual intervention required'
            })
        
        return rollback_log
    
    # =================================================================
    # HELPER METHODS
    # =================================================================
    
    def list_account_sites_minimal(self, account_id: str) -> list:
        """Minimal site listing for internal operations"""
        response = self.table.query(
            KeyConditionExpression=(
                Key('PK').eq(f'ACCOUNT#{account_id}') &
                Key('SK').begins_with('SITE#')
            ),
            ProjectionExpression='SK, site_domain, #status',
            ExpressionAttributeNames={'#status': 'status'}
        )
        
        return [
            {
                'site_domain': item['SK'].replace('SITE#', ''),
                'status': item.get('status', 'unknown')
            }
            for item in response['Items']
        ]

# =================================================================
# PERFORMANCE TESTING & BENCHMARKS
# =================================================================

def performance_benchmark():
    """
    Benchmark key operations for capacity planning
    """
    import time
    from concurrent.futures import ThreadPoolExecutor
    
    auth_manager = AdvancedWordPressQueries('WordPressAuthCredentials')
    
    # Test batch validation performance
    test_credentials = [
        {'site_domain': f'site{i}.com', 'key_id': f'key_{i}', 'secret': f'secret_{i}'}
        for i in range(50)
    ]
    
    start_time = time.time()
    results = auth_manager.batch_validate_sites(test_credentials)
    end_time = time.time()
    
    print(f"Batch validation (50 sites): {end_time - start_time:.3f} seconds")
    print(f"Average per site: {(end_time - start_time) / 50 * 1000:.1f} ms")
    
    # Test concurrent access patterns
    def simulate_plugin_check(site_id):
        return auth_manager.validate_site_credentials(
            f'key_{site_id}', f'secret_{site_id}', f'site{site_id}.com'
        )
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(simulate_plugin_check, i) for i in range(100)]
        results = [f.result() for f in futures]
    end_time = time.time()
    
    print(f"Concurrent validation (100 sites, 10 threads): {end_time - start_time:.3f} seconds")
    print(f"Throughput: {100 / (end_time - start_time):.1f} validations/second")

if __name__ == "__main__":
    performance_benchmark()
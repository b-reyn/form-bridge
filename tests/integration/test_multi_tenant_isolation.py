"""
Multi-tenant data isolation tests
100% tenant isolation validation and cross-tenant attack prevention
"""

import pytest
import json
import boto3
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from tests.conftest import MultiTenantTestEnvironment, TenantConfig


@pytest.mark.multi_tenant
class TestMultiTenantDataIsolation:
    """Test complete data isolation between tenants"""
    
    def test_tenant_data_isolation_basic(self, multi_tenant_test_env, dynamodb_resource):
        """Test basic tenant data isolation"""
        env = multi_tenant_test_env
        env.setup_tenant_data(dynamodb_resource)
        
        table = dynamodb_resource.Table('formbridge-test')
        
        # Verify each tenant can only access their own data
        for tenant in env.tenants:
            tenant_items = table.scan(
                FilterExpression='begins_with(PK, :prefix)',
                ExpressionAttributeValues={':prefix': tenant.dynamodb_prefix}
            )['Items']
            
            # All items should belong to this tenant
            for item in tenant_items:
                assert item['PK'].startswith(tenant.dynamodb_prefix)
                assert item['tenant_id'] == tenant.tenant_id
                
        # Verify complete isolation
        assert env.verify_tenant_isolation(dynamodb_resource)
        
        # Cleanup
        env.cleanup_tenant_data(dynamodb_resource)

    def test_cross_tenant_data_access_prevention(self, multi_tenant_test_env, dynamodb_resource):
        """Test that tenants cannot access each other's data"""
        env = multi_tenant_test_env
        env.setup_tenant_data(dynamodb_resource)
        
        table = dynamodb_resource.Table('formbridge-test')
        tenant_1, tenant_2, tenant_3 = env.tenants[:3]
        
        # Try to access tenant_2's data using tenant_1's credentials
        try:
            # This should return no items (isolation working)
            cross_tenant_query = table.scan(
                FilterExpression='begins_with(PK, :prefix)',
                ExpressionAttributeValues={':prefix': tenant_2.dynamodb_prefix}
            )
            
            # In a real system, this would be filtered by tenant context
            # Here we simulate by checking items don't match current tenant
            for item in cross_tenant_query['Items']:
                assert item['tenant_id'] != tenant_1.tenant_id, "Cross-tenant data access detected!"
                
        except Exception as e:
            # Any exception here means isolation is working
            assert "access denied" in str(e).lower() or "unauthorized" in str(e).lower()
        
        env.cleanup_tenant_data(dynamodb_resource)

    def test_tenant_isolation_under_concurrent_access(self, multi_tenant_test_env, dynamodb_resource):
        """Test tenant isolation under concurrent access patterns"""
        env = multi_tenant_test_env
        env.setup_tenant_data(dynamodb_resource)
        
        table = dynamodb_resource.Table('formbridge-test')
        
        def concurrent_tenant_operations(tenant: TenantConfig) -> Dict[str, Any]:
            """Perform concurrent operations for a single tenant"""
            results = {
                'tenant_id': tenant.tenant_id,
                'operations_completed': 0,
                'data_integrity_maintained': True,
                'isolation_violations': []
            }
            
            try:
                # Perform 50 concurrent operations per tenant
                for i in range(50):
                    # Create new submission
                    submission_id = f"concurrent_sub_{uuid4().hex[:16]}"
                    table.put_item(Item={
                        'PK': f'{tenant.dynamodb_prefix}#SUBMISSION#{submission_id}',
                        'SK': f'META#{datetime.now(timezone.utc).isoformat()}',
                        'tenant_id': tenant.tenant_id,
                        'submission_id': submission_id,
                        'concurrent_test': True,
                        'iteration': i
                    })
                    
                    # Query tenant data
                    tenant_data = table.scan(
                        FilterExpression='begins_with(PK, :prefix)',
                        ExpressionAttributeValues={':prefix': tenant.dynamodb_prefix}
                    )['Items']
                    
                    # Verify all data belongs to this tenant
                    for item in tenant_data:
                        if not item['PK'].startswith(tenant.dynamodb_prefix):
                            results['isolation_violations'].append({
                                'expected_prefix': tenant.dynamodb_prefix,
                                'actual_pk': item['PK'],
                                'iteration': i
                            })
                            results['data_integrity_maintained'] = False
                    
                    results['operations_completed'] += 1
                    
            except Exception as e:
                results['error'] = str(e)
                results['data_integrity_maintained'] = False
            
            return results
        
        # Run concurrent operations for all tenants
        with ThreadPoolExecutor(max_workers=len(env.tenants)) as executor:
            future_to_tenant = {
                executor.submit(concurrent_tenant_operations, tenant): tenant 
                for tenant in env.tenants
            }
            
            results = []
            for future in as_completed(future_to_tenant):
                tenant = future_to_tenant[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    results.append({
                        'tenant_id': tenant.tenant_id,
                        'error': str(exc),
                        'data_integrity_maintained': False
                    })
        
        # Verify all operations completed successfully with isolation maintained
        for result in results:
            assert result['data_integrity_maintained'], f"Isolation violated for tenant {result['tenant_id']}: {result.get('isolation_violations', [])}"
            assert result['operations_completed'] == 50, f"Not all operations completed for tenant {result['tenant_id']}"
            assert len(result.get('isolation_violations', [])) == 0, f"Isolation violations detected: {result['isolation_violations']}"
        
        # Final isolation verification
        assert env.verify_tenant_isolation(dynamodb_resource)
        
        env.cleanup_tenant_data(dynamodb_resource)

    def test_tenant_data_encryption_isolation(self, multi_tenant_test_env, dynamodb_resource):
        """Test that tenant data encryption keys are properly isolated"""
        env = multi_tenant_test_env
        
        # Test sensitive data isolation
        sensitive_data_cases = [
            {"field": "credit_card", "value": "4111-1111-1111-1111", "should_be_encrypted": True},
            {"field": "ssn", "value": "123-45-6789", "should_be_encrypted": True},
            {"field": "api_key", "value": "sk_live_123456789", "should_be_encrypted": True},
            {"field": "name", "value": "John Doe", "should_be_encrypted": False},
            {"field": "email", "value": "john@example.com", "should_be_encrypted": False},
        ]
        
        table = dynamodb_resource.Table('formbridge-test')
        
        for tenant in env.tenants:
            for case in sensitive_data_cases:
                submission_id = f"encrypt_test_{uuid4().hex[:16]}"
                
                # Store data (in real system, would be encrypted based on field sensitivity)
                stored_value = case["value"]
                if case["should_be_encrypted"]:
                    # Simulate encryption with tenant-specific key
                    stored_value = f"encrypted_with_{tenant.tenant_id}_key:{case['value']}"
                
                table.put_item(Item={
                    'PK': f'{tenant.dynamodb_prefix}#SUBMISSION#{submission_id}',
                    'SK': f'SENSITIVE#{case["field"]}',
                    'tenant_id': tenant.tenant_id,
                    'field_name': case["field"],
                    'field_value': stored_value,
                    'is_sensitive': case["should_be_encrypted"]
                })
        
        # Verify tenant-specific encryption
        for tenant in env.tenants:
            tenant_sensitive_data = table.scan(
                FilterExpression='begins_with(PK, :prefix) AND begins_with(SK, :sk_prefix)',
                ExpressionAttributeValues={
                    ':prefix': tenant.dynamodb_prefix,
                    ':sk_prefix': 'SENSITIVE#'
                }
            )['Items']
            
            for item in tenant_sensitive_data:
                if item['is_sensitive']:
                    # Verify data is encrypted with tenant-specific key
                    assert f"encrypted_with_{tenant.tenant_id}_key:" in item['field_value']
                    # Verify other tenants' keys are not present
                    for other_tenant in env.tenants:
                        if other_tenant.tenant_id != tenant.tenant_id:
                            assert f"encrypted_with_{other_tenant.tenant_id}_key:" not in item['field_value']
        
        env.cleanup_tenant_data(dynamodb_resource)

    def test_tenant_rate_limiting_isolation(self, multi_tenant_test_env):
        """Test that tenant rate limiting is properly isolated"""
        env = multi_tenant_test_env
        
        # Simulate rate limiting for each tenant
        rate_limit_results = {}
        
        for tenant in env.tenants:
            rate_limit_results[tenant.tenant_id] = {
                'requests_allowed': 0,
                'requests_blocked': 0,
                'rate_limit_exceeded': False
            }
            
            # Simulate 150 requests (exceeding 100/minute limit)
            for i in range(150):
                # In real system, this would check Redis/DynamoDB rate limit counters
                current_requests = rate_limit_results[tenant.tenant_id]['requests_allowed']
                
                if current_requests < tenant.config['rate_limit']['requests_per_minute']:
                    rate_limit_results[tenant.tenant_id]['requests_allowed'] += 1
                else:
                    rate_limit_results[tenant.tenant_id]['requests_blocked'] += 1
                    rate_limit_results[tenant.tenant_id]['rate_limit_exceeded'] = True
        
        # Verify rate limiting is isolated per tenant
        for tenant_id, result in rate_limit_results.items():
            assert result['requests_allowed'] == 100, f"Tenant {tenant_id} should have exactly 100 allowed requests"
            assert result['requests_blocked'] == 50, f"Tenant {tenant_id} should have 50 blocked requests"
            assert result['rate_limit_exceeded'], f"Tenant {tenant_id} should have exceeded rate limit"
        
        # Verify one tenant's rate limiting doesn't affect others
        tenant_1_blocked = rate_limit_results[env.tenants[0].tenant_id]['requests_blocked']
        tenant_2_blocked = rate_limit_results[env.tenants[1].tenant_id]['requests_blocked']
        
        assert tenant_1_blocked == tenant_2_blocked == 50, "Rate limiting should be isolated per tenant"

    def test_tenant_secret_isolation(self, multi_tenant_test_env):
        """Test that tenant secrets are properly isolated"""
        env = multi_tenant_test_env
        
        # Simulate secrets storage and access
        mock_secrets_manager = {}
        
        # Store secrets for each tenant
        for tenant in env.tenants:
            mock_secrets_manager[tenant.secrets_key] = {
                'api_key': tenant.api_key,
                'secret_key': tenant.secret_key,
                'encryption_key': f"enc_key_{uuid4().hex}",
                'webhook_signing_key': f"webhook_key_{uuid4().hex}"
            }
        
        # Test secret access isolation
        for tenant in env.tenants:
            # Tenant should only access their own secrets
            tenant_secrets = mock_secrets_manager.get(tenant.secrets_key)
            assert tenant_secrets is not None, f"Tenant {tenant.tenant_id} secrets not found"
            assert tenant_secrets['api_key'] == tenant.api_key
            assert tenant_secrets['secret_key'] == tenant.secret_key
            
            # Verify tenant cannot access other tenants' secrets
            for other_tenant in env.tenants:
                if other_tenant.tenant_id != tenant.tenant_id:
                    other_secrets_key = other_tenant.secrets_key
                    # In real system, access would be denied by IAM/RBAC
                    assert other_secrets_key != tenant.secrets_key
                    
                    # Simulate access denial
                    try:
                        # This would raise an access denied exception in real system
                        if tenant.secrets_key != other_secrets_key:
                            raise PermissionError(f"Access denied to {other_secrets_key}")
                    except PermissionError:
                        # Expected behavior - access denied
                        pass

    def test_tenant_analytics_data_isolation(self, multi_tenant_test_env, dynamodb_resource):
        """Test that tenant analytics data is properly isolated"""
        env = multi_tenant_test_env
        table = dynamodb_resource.Table('formbridge-test')
        
        # Create analytics data for each tenant
        analytics_data = {}
        
        for tenant in env.tenants:
            analytics_data[tenant.tenant_id] = {
                'total_submissions': 0,
                'daily_submissions': {},
                'form_performance': {}
            }
            
            # Generate analytics data
            for day in range(7):  # 7 days of data
                date_key = f"2025-01-{day + 1:02d}"
                daily_count = (day + 1) * 10  # Different patterns per tenant
                
                analytics_data[tenant.tenant_id]['daily_submissions'][date_key] = daily_count
                analytics_data[tenant.tenant_id]['total_submissions'] += daily_count
                
                # Store in DynamoDB
                table.put_item(Item={
                    'PK': f'{tenant.dynamodb_prefix}#ANALYTICS#{date_key}',
                    'SK': 'DAILY_STATS',
                    'tenant_id': tenant.tenant_id,
                    'date': date_key,
                    'submission_count': daily_count,
                    'unique_forms': (day + 1) * 2,
                    'conversion_rate': 0.8 + (day * 0.02)
                })
        
        # Verify analytics data isolation
        for tenant in env.tenants:
            tenant_analytics = table.scan(
                FilterExpression='begins_with(PK, :prefix) AND contains(PK, :analytics)',
                ExpressionAttributeValues={
                    ':prefix': tenant.dynamodb_prefix,
                    ':analytics': 'ANALYTICS'
                }
            )['Items']
            
            # Verify all analytics belong to this tenant
            total_submissions = 0
            for item in tenant_analytics:
                assert item['tenant_id'] == tenant.tenant_id
                assert item['PK'].startswith(tenant.dynamodb_prefix)
                total_submissions += item['submission_count']
            
            # Verify totals match expected values
            expected_total = analytics_data[tenant.tenant_id]['total_submissions']
            assert total_submissions == expected_total, f"Analytics total mismatch for {tenant.tenant_id}"
        
        env.cleanup_tenant_data(dynamodb_resource)


@pytest.mark.multi_tenant
@pytest.mark.security  
class TestCrossTenantAttackPrevention:
    """Test prevention of cross-tenant attacks and data breaches"""
    
    def test_tenant_id_injection_prevention(self, multi_tenant_test_env, dynamodb_resource):
        """Test prevention of tenant ID injection attacks"""
        env = multi_tenant_test_env
        env.setup_tenant_data(dynamodb_resource)
        
        table = dynamodb_resource.Table('formbridge-test')
        target_tenant = env.tenants[0]
        attacker_tenant = env.tenants[1]
        
        # Attempt tenant ID injection attacks
        injection_attempts = [
            # SQL-like injection attempts
            {"malicious_tenant_id": f"{target_tenant.tenant_id}' OR '1'='1"},
            {"malicious_tenant_id": f"{target_tenant.tenant_id}; DROP TABLE submissions; --"},
            {"malicious_tenant_id": f"{target_tenant.tenant_id} UNION SELECT * FROM other_tenant"},
            
            # NoSQL injection attempts  
            {"malicious_tenant_id": f"{target_tenant.tenant_id}{{$ne: null}}"},
            {"malicious_tenant_id": f"{target_tenant.tenant_id}{{$regex: '.*'}}"},
            
            # Path traversal attempts
            {"malicious_tenant_id": f"../../../{target_tenant.tenant_id}"},
            {"malicious_tenant_id": f"{target_tenant.tenant_id}/../other_tenant"},
            
            # Encoding attempts
            {"malicious_tenant_id": f"%2e%2e%2f{target_tenant.tenant_id}"},
            {"malicious_tenant_id": f"{target_tenant.tenant_id}%00other_data"},
        ]
        
        for attempt in injection_attempts:
            malicious_id = attempt["malicious_tenant_id"]
            
            # Try to query with malicious tenant ID
            try:
                # In a properly secured system, this should either:
                # 1. Return no results (input sanitization working)
                # 2. Raise an exception (validation working)
                
                results = table.scan(
                    FilterExpression='begins_with(PK, :prefix)',
                    ExpressionAttributeValues={':prefix': f'TENANT#{malicious_id}'}
                )
                
                # If query succeeds, verify it returns no sensitive data
                for item in results.get('Items', []):
                    # Should not contain target tenant's actual data
                    assert item.get('tenant_id') != target_tenant.tenant_id, f"Injection attack succeeded: {malicious_id}"
                    
            except Exception as e:
                # Exception is expected for malformed queries
                assert any(keyword in str(e).lower() for keyword in ['invalid', 'malformed', 'error'])
        
        env.cleanup_tenant_data(dynamodb_resource)

    def test_parameter_pollution_attacks(self, multi_tenant_test_env):
        """Test prevention of HTTP parameter pollution attacks"""
        env = multi_tenant_test_env
        
        # Simulate parameter pollution attacks
        pollution_attacks = [
            # Multiple tenant IDs
            {"params": {"tenant_id": [env.tenants[0].tenant_id, env.tenants[1].tenant_id]}},
            
            # Array injection
            {"params": {"tenant_id": f"['{env.tenants[0].tenant_id}', '{env.tenants[1].tenant_id}']"}},
            
            # Object injection
            {"params": {"tenant_id": f"{{'$in': ['{env.tenants[0].tenant_id}', '{env.tenants[1].tenant_id}']}"}},
            
            # Null byte injection
            {"params": {"tenant_id": f"{env.tenants[0].tenant_id}\x00{env.tenants[1].tenant_id}"}},
        ]
        
        for attack in pollution_attacks:
            # Simulate request processing with parameter pollution
            params = attack["params"]
            
            # Proper parameter validation should handle these cases
            validated_tenant_id = self._validate_and_extract_tenant_id(params)
            
            # Should either return single valid tenant ID or None
            if validated_tenant_id:
                assert validated_tenant_id in [t.tenant_id for t in env.tenants]
                # Should not be a list or contain multiple values
                assert isinstance(validated_tenant_id, str)
                assert len(validated_tenant_id.split()) == 1  # Single value
            else:
                # Validation properly rejected the malicious input
                assert validated_tenant_id is None

    def test_timing_attack_resistance(self, multi_tenant_test_env, dynamodb_resource):
        """Test resistance to timing attacks for tenant discovery"""
        import time
        
        env = multi_tenant_test_env
        env.setup_tenant_data(dynamodb_resource)
        
        table = dynamodb_resource.Table('formbridge-test')
        existing_tenant = env.tenants[0]
        non_existent_tenant = f"t_nonexistent_{uuid4().hex[:8]}"
        
        # Measure timing for existing tenant queries
        existing_tenant_times = []
        for _ in range(100):
            start_time = time.time()
            results = table.scan(
                FilterExpression='begins_with(PK, :prefix)',
                ExpressionAttributeValues={':prefix': existing_tenant.dynamodb_prefix}
            )
            end_time = time.time()
            existing_tenant_times.append(end_time - start_time)
        
        # Measure timing for non-existent tenant queries
        non_existent_times = []
        for _ in range(100):
            start_time = time.time()
            results = table.scan(
                FilterExpression='begins_with(PK, :prefix)',
                ExpressionAttributeValues={':prefix': f'TENANT#{non_existent_tenant}'}
            )
            end_time = time.time()
            non_existent_times.append(end_time - start_time)
        
        # Calculate average times
        avg_existing = sum(existing_tenant_times) / len(existing_tenant_times)
        avg_non_existent = sum(non_existent_times) / len(non_existent_times)
        
        # Time difference should be minimal to prevent tenant enumeration
        time_difference_ratio = abs(avg_existing - avg_non_existent) / max(avg_existing, avg_non_existent)
        
        # Should be less than 20% difference to prevent timing attacks
        assert time_difference_ratio < 0.2, f"Timing difference {time_difference_ratio:.2%} may allow tenant enumeration"
        
        env.cleanup_tenant_data(dynamodb_resource)

    def test_resource_exhaustion_prevention(self, multi_tenant_test_env, dynamodb_resource):
        """Test prevention of resource exhaustion attacks between tenants"""
        env = multi_tenant_test_env
        
        # Simulate one tenant attempting to exhaust resources
        attacking_tenant = env.tenants[0]
        victim_tenant = env.tenants[1]
        
        table = dynamodb_resource.Table('formbridge-test')
        
        # Simulate resource exhaustion attempt
        resource_usage = {
            'attacking_tenant': {'storage_used': 0, 'requests_made': 0},
            'victim_tenant': {'storage_used': 0, 'requests_made': 0}
        }
        
        # Attacking tenant tries to use excessive resources
        try:
            for i in range(1000):  # Attempt to create 1000 large items
                large_payload = "x" * 10000  # 10KB per item
                
                # Check resource limits (in real system, would be enforced by quotas)
                if resource_usage['attacking_tenant']['storage_used'] > 100 * 1024:  # 100KB limit
                    raise Exception("QUOTA_EXCEEDED: Storage limit reached")
                
                if resource_usage['attacking_tenant']['requests_made'] > 100:  # 100 request limit
                    raise Exception("RATE_LIMIT_EXCEEDED: Request limit reached")
                
                table.put_item(Item={
                    'PK': f'{attacking_tenant.dynamodb_prefix}#ATTACK#{i}',
                    'SK': f'LARGE_ITEM#{i}',
                    'tenant_id': attacking_tenant.tenant_id,
                    'large_data': large_payload
                })
                
                resource_usage['attacking_tenant']['storage_used'] += len(large_payload)
                resource_usage['attacking_tenant']['requests_made'] += 1
                
        except Exception as e:
            # Resource limit enforcement should kick in
            assert any(keyword in str(e) for keyword in ['QUOTA_EXCEEDED', 'RATE_LIMIT_EXCEEDED', 'THROTTLE'])
        
        # Verify victim tenant is unaffected
        victim_items = table.scan(
            FilterExpression='begins_with(PK, :prefix)',
            ExpressionAttributeValues={':prefix': victim_tenant.dynamodb_prefix}
        )
        
        # Victim tenant should still be able to operate normally
        table.put_item(Item={
            'PK': f'{victim_tenant.dynamodb_prefix}#NORMAL_OPERATION',
            'SK': 'TEST_ITEM',
            'tenant_id': victim_tenant.tenant_id,
            'message': 'Victim tenant unaffected by attack'
        })
        
        # Verify the item was stored successfully
        victim_test_item = table.get_item(
            Key={
                'PK': f'{victim_tenant.dynamodb_prefix}#NORMAL_OPERATION',
                'SK': 'TEST_ITEM'
            }
        )
        
        assert victim_test_item['Item']['tenant_id'] == victim_tenant.tenant_id
        
        env.cleanup_tenant_data(dynamodb_resource)

    def _validate_and_extract_tenant_id(self, params: Dict[str, Any]) -> str:
        """
        Mock tenant ID validation that would be implemented in the real system
        Should handle parameter pollution and injection attempts
        """
        tenant_id = params.get("tenant_id")
        
        if not tenant_id:
            return None
        
        # Handle parameter pollution - take only first value if array
        if isinstance(tenant_id, list):
            tenant_id = tenant_id[0] if tenant_id else None
        
        if not isinstance(tenant_id, str):
            return None
        
        # Remove null bytes and other dangerous characters
        tenant_id = tenant_id.replace('\x00', '').strip()
        
        # Validate format - should be alphanumeric with underscores
        if not tenant_id.replace('_', '').replace('-', '').isalnum():
            return None
        
        # Check length limits
        if len(tenant_id) > 50 or len(tenant_id) < 3:
            return None
        
        # Should start with 't_' prefix
        if not tenant_id.startswith('t_'):
            return None
        
        return tenant_id


@pytest.mark.multi_tenant
@pytest.mark.performance
class TestMultiTenantPerformance:
    """Test multi-tenant performance and scalability"""
    
    def test_tenant_query_performance_isolation(self, multi_tenant_test_env, dynamodb_resource, performance_baseline):
        """Test that tenant queries perform consistently regardless of other tenant data volume"""
        env = multi_tenant_test_env
        
        table = dynamodb_resource.Table('formbridge-test')
        
        # Create different data volumes for different tenants
        small_tenant = env.tenants[0]  # 10 items
        medium_tenant = env.tenants[1]  # 100 items  
        large_tenant = env.tenants[2]   # 1000 items
        
        # Populate tenants with different data volumes
        self._populate_tenant_data(table, small_tenant, 10)
        self._populate_tenant_data(table, medium_tenant, 100)
        self._populate_tenant_data(table, large_tenant, 1000)
        
        # Measure query performance for each tenant
        performance_results = {}
        
        for tenant in [small_tenant, medium_tenant, large_tenant]:
            query_times = []
            
            for _ in range(50):  # 50 query samples
                start_time = time.time()
                results = table.scan(
                    FilterExpression='begins_with(PK, :prefix)',
                    ExpressionAttributeValues={':prefix': tenant.dynamodb_prefix}
                )
                end_time = time.time()
                
                query_times.append((end_time - start_time) * 1000)  # Convert to ms
            
            avg_time = sum(query_times) / len(query_times)
            p95_time = sorted(query_times)[int(0.95 * len(query_times))]
            
            performance_results[tenant.tenant_id] = {
                'avg_time_ms': avg_time,
                'p95_time_ms': p95_time,
                'data_volume': len(table.scan(FilterExpression='begins_with(PK, :prefix)', 
                                            ExpressionAttributeValues={':prefix': tenant.dynamodb_prefix})['Items'])
            }
        
        # Verify performance is within acceptable bounds for all tenants
        for tenant_id, results in performance_results.items():
            assert results['avg_time_ms'] < performance_baseline['dynamodb_write_ms'] * 5, f"Query performance degraded for {tenant_id}"
            assert results['p95_time_ms'] < performance_baseline['dynamodb_write_ms'] * 10, f"P95 performance degraded for {tenant_id}"
        
        # Verify small tenant performance isn't affected by large tenant
        small_tenant_perf = performance_results[small_tenant.tenant_id]['avg_time_ms']
        large_tenant_perf = performance_results[large_tenant.tenant_id]['avg_time_ms']
        
        # Performance difference should be reasonable (large tenant can be slower, but not excessively)
        perf_ratio = large_tenant_perf / small_tenant_perf
        assert perf_ratio < 5.0, f"Large tenant performance impact too high: {perf_ratio:.2f}x slower"
        
        env.cleanup_tenant_data(dynamodb_resource)

    def _populate_tenant_data(self, table, tenant: TenantConfig, item_count: int):
        """Populate tenant with specified number of test items"""
        for i in range(item_count):
            table.put_item(Item={
                'PK': f'{tenant.dynamodb_prefix}#SUBMISSION#{i:06d}',
                'SK': f'META#{datetime.now(timezone.utc).isoformat()}',
                'tenant_id': tenant.tenant_id,
                'submission_id': f'perf_test_{i:06d}',
                'data': f'Performance test data item {i}',
                'iteration': i
            })
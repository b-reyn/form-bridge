# DynamoDB Architect Strategy - Form-Bridge Project

## Strategy Overview
**Last Updated**: January 26, 2025  
**Agent**: dynamodb-architect  
**Focus**: Multi-tenant serverless form ingestion with EventBridge-centric architecture

## Current Best Practices (2025)

### Single Table Design Evolution
- **Multi-tenant serverless** applications now require sophisticated sharding strategies
- **Write sharding** has become essential for preventing hot partitions in high-volume scenarios
- **Pre-aggregated metrics** are now preferred over real-time queries for cost optimization
- **Intelligent compression** can achieve 70% storage savings on payloads >1KB
- **TTL-based lifecycle management** is critical for compliance and cost control

### Latest 2025 Patterns
1. **Hybrid Capacity Strategy**: Provisioned for base load + on-demand for bursts
2. **EventBridge Integration**: DynamoDB Streams → EventBridge Pipes for real-time processing
3. **S3 Hybrid Storage**: Large objects (>1KB) stored in S3 with DynamoDB metadata
4. **Advanced Sharding**: Hash-based distribution with tenant lookup tables
5. **Cost Optimization Hub**: AWS's new reservation recommendations for DynamoDB

## Project-Specific Architecture

### Critical Issues Addressed

#### 1. Missing Core MVP Features
The current design focuses heavily on WordPress plugin authentication but lacks the core form-bridge functionality:

**MISSING COMPONENTS:**
- Form submission storage schema
- Destination management patterns
- Delivery attempt tracking
- Multi-tenant form routing

**SOLUTION:**
Implement comprehensive single-table design covering all form-bridge entities.

#### 2. Hot Partition Prevention
**PROBLEM**: High-volume form submissions will create hot partitions
**SOLUTION**: Implement write sharding with tenant lookup table

#### 3. Cost Model Reality Check
**CORRECTED PROJECTIONS:**
- MVP (1K submissions/month): $15-20/month (not $4.50)
- Growth (10K submissions/month): $48-73/month
- Production (100K submissions/month): $310-445/month

## Comprehensive Single-Table Design

### Table Structure: `FormBridgeData`

```python
# Primary Keys and Access Patterns
TABLE_DESIGN = {
    "table_name": "FormBridgeData",
    "partition_key": "PK",  # String
    "sort_key": "SK",       # String
    "gsi1": {
        "partition_key": "GSI1PK", 
        "sort_key": "GSI1SK"
    },
    "gsi2": {
        "partition_key": "GSI2PK", 
        "sort_key": "GSI2SK"  
    },
    "gsi3": {
        "partition_key": "GSI3PK", 
        "sort_key": "GSI3SK"
    },
    "ttl_attribute": "ttl"
}

# Entity Types and Key Patterns
ENTITY_PATTERNS = {
    # Core Form-Bridge Entities
    "submission": {
        "PK": "TENANT#{tenant_id}#{shard_id}",
        "SK": "SUB#{submission_id}",
        "GSI1PK": "TENANT#{tenant_id}",
        "GSI1SK": "TS#{timestamp}",
        "GSI2PK": "TENANT#{tenant_id}#STATUS",
        "GSI2SK": "{status}#{timestamp}"
    },
    "destination": {
        "PK": "TENANT#{tenant_id}",
        "SK": "DEST#{destination_id}",
        "GSI1PK": "TENANT#{tenant_id}",
        "GSI1SK": "DEST#{destination_type}#{created_at}"
    },
    "delivery_attempt": {
        "PK": "SUB#{submission_id}",
        "SK": "DEST#{destination_id}#ATTEMPT#{attempt_num}",
        "GSI1PK": "TENANT#{tenant_id}",
        "GSI1SK": "DELIVERY#{status}#{timestamp}",
        "GSI2PK": "DEST#{destination_id}",
        "GSI2SK": "STATUS#{status}#{timestamp}"
    },
    "tenant_config": {
        "PK": "TENANT#{tenant_id}",
        "SK": "CONFIG#main",
        "GSI1PK": "CONFIG#active",
        "GSI1SK": "TENANT#{tenant_id}"
    },
    # Write Sharding Support
    "tenant_shards": {
        "PK": "TENANT#{tenant_id}",
        "SK": "SHARDS#{shard_count}",
        "attributes": ["shard_mapping", "distribution_strategy"]
    },
    # Pre-aggregated Metrics
    "daily_metrics": {
        "PK": "TENANT#{tenant_id}",
        "SK": "METRICS#DAY#{date}",
        "GSI1PK": "METRICS#DAY#{date}",
        "GSI1SK": "TENANT#{tenant_id}",
        "attributes": ["submission_count", "destination_stats", "error_rate"]
    },
    "hourly_metrics": {
        "PK": "TENANT#{tenant_id}",
        "SK": "METRICS#HOUR#{datetime}",
        "ttl": "auto_cleanup_72h"
    }
}
```

### Write Sharding Implementation

```python
import hashlib
import json
import time
from typing import Dict, List, Optional

class FormBridgeShardingStrategy:
    """
    Intelligent write sharding for high-volume form submissions
    """
    
    def __init__(self, dynamodb_client):
        self.dynamodb = dynamodb_client
        self.table_name = "FormBridgeData"
        
    def get_shard_id(self, tenant_id: str, submission_timestamp: str) -> str:
        """
        Calculate shard ID based on tenant volume and time distribution
        """
        # Get tenant's current shard configuration
        shard_config = self._get_tenant_shard_config(tenant_id)
        shard_count = shard_config.get("shard_count", 1)
        
        if shard_count == 1:
            return "0"  # No sharding for low-volume tenants
            
        # Hash-based distribution with time component
        hash_input = f"{tenant_id}#{submission_timestamp}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        shard_id = str(int(hash_value[:8], 16) % shard_count)
        
        return shard_id
    
    def _calculate_optimal_shards(self, tenant_id: str) -> int:
        """
        Calculate optimal shard count based on tenant volume
        """
        # Query recent submission volume
        volume = self._get_recent_volume(tenant_id)
        
        if volume > 10000:  # >10K submissions/month
            return 10
        elif volume > 1000:  # >1K submissions/month
            return 4
        else:
            return 1  # No sharding needed
    
    def create_submission_key(self, tenant_id: str, submission_id: str, 
                            timestamp: str) -> Dict:
        """Create properly sharded submission key"""
        shard_id = self.get_shard_id(tenant_id, timestamp)
        
        return {
            'PK': f'TENANT#{tenant_id}#{shard_id}',
            'SK': f'SUB#{submission_id}',
            'GSI1PK': f'TENANT#{tenant_id}',
            'GSI1SK': f'TS#{timestamp}',
            'GSI2PK': f'TENANT#{tenant_id}#STATUS',
            'GSI2SK': f'PENDING#{timestamp}',
            'shard_id': shard_id,
            'tenant_id': tenant_id
        }
```

### Intelligent Compression Strategy

```python
import gzip
import json
import base64
from typing import Dict, Any, Tuple

class PayloadCompressionManager:
    """
    Intelligent compression for form payloads >1KB
    Target: 70% storage savings
    """
    
    COMPRESSION_THRESHOLD = 1024  # 1KB
    TARGET_COMPRESSION_RATIO = 0.7  # 70% savings
    
    def process_payload(self, payload: Dict[Any, Any]) -> Dict[str, Any]:
        """
        Intelligently compress payload based on size and content
        """
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_size = len(payload_json.encode('utf-8'))
        
        if payload_size < self.COMPRESSION_THRESHOLD:
            return {
                "data": payload,
                "compressed": False,
                "original_size": payload_size,
                "storage_size": payload_size
            }
        
        # Attempt compression
        compressed_data = gzip.compress(payload_json.encode('utf-8'))
        compression_ratio = len(compressed_data) / payload_size
        
        if compression_ratio < self.TARGET_COMPRESSION_RATIO:
            # Good compression achieved
            return {
                "data": base64.b64encode(compressed_data).decode('utf-8'),
                "compressed": True,
                "compression_algorithm": "gzip",
                "original_size": payload_size,
                "storage_size": len(compressed_data),
                "compression_ratio": compression_ratio
            }
        else:
            # Poor compression, store uncompressed
            return {
                "data": payload,
                "compressed": False,
                "original_size": payload_size,
                "storage_size": payload_size,
                "compression_note": "poor_compression_ratio"
            }
```

### Pre-Aggregated Metrics Strategy

```python
from datetime import datetime, timedelta
from typing import Dict, List
import json

class MetricsAggregationManager:
    """
    Pre-aggregated metrics to avoid expensive real-time queries
    """
    
    def __init__(self, dynamodb_client):
        self.dynamodb = dynamodb_client
        self.table_name = "FormBridgeData"
    
    def update_submission_metrics(self, tenant_id: str, submission_data: Dict):
        """
        Update daily and hourly metrics for new submission
        """
        now = datetime.utcnow()
        date_key = now.strftime('%Y-%m-%d')
        hour_key = now.strftime('%Y-%m-%d-%H')
        
        # Update daily metrics
        self._update_daily_metrics(tenant_id, date_key, submission_data)
        
        # Update hourly metrics (with TTL)
        self._update_hourly_metrics(tenant_id, hour_key, submission_data, now)
    
    def get_dashboard_metrics(self, tenant_id: str, 
                            days_back: int = 30) -> Dict:
        """
        Efficiently retrieve dashboard metrics using pre-aggregated data
        """
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Query pre-aggregated daily metrics
        response = self.dynamodb.query(
            TableName=self.table_name,
            KeyConditionExpression='PK = :pk AND SK BETWEEN :start AND :end',
            ExpressionAttributeValues={
                ':pk': f'TENANT#{tenant_id}',
                ':start': f'METRICS#DAY#{start_date}',
                ':end': f'METRICS#DAY#{end_date}'
            }
        )
        
        # Aggregate results
        total_submissions = 0
        daily_breakdown = {}
        form_stats = {}
        
        for item in response.get('Items', []):
            date_key = item['SK'].replace('METRICS#DAY#', '')
            count = item.get('submission_count', 0)
            
            total_submissions += count
            daily_breakdown[date_key] = count
            
            # Merge form statistics
            item_form_stats = item.get('form_stats', {})
            for form_id, form_count in item_form_stats.items():
                form_stats[form_id] = form_stats.get(form_id, 0) + form_count
        
        return {
            'total_submissions': total_submissions,
            'daily_breakdown': daily_breakdown,
            'form_statistics': form_stats,
            'period': f'{start_date} to {end_date}'
        }
```

### Domain Reverse Lookup for WordPress Plugin Efficiency

```python
class DomainLookupManager:
    """
    Optimized domain reverse lookup for WordPress plugin efficiency
    """
    
    def __init__(self, dynamodb_client):
        self.dynamodb = dynamodb_client
        self.table_name = "FormBridgeData"
    
    def lookup_tenant_by_domain(self, domain: str) -> Optional[Dict]:
        """
        Fast domain → tenant lookup for WordPress plugin
        """
        domain_hash = hashlib.sha256(domain.encode()).hexdigest()[:16]
        
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={
                    'PK': f'DOMAIN#{domain_hash}',
                    'SK': f'LOOKUP#{domain}'
                }
            )
            return response.get('Item')
        except Exception:
            return None
```

## Cost Optimization Strategies

### Realistic Cost Projections

```python
COST_MODEL_2025 = {
    "mvp_1k_monthly": {
        "dynamodb": {"read": 2, "write": 3, "storage": 1},
        "lambda": {"compute": 2, "requests": 1},
        "api_gateway": {"requests": 1, "data_transfer": 0.5},
        "eventbridge": {"events": 0.5},
        "security": {"kms": 2, "secrets_manager": 1},
        "monitoring": {"cloudwatch": 1, "xray": 0.5},
        "s3": {"storage": 0.5, "requests": 0.2},
        "total_range": "12-21 USD"
    },
    "growth_10k_monthly": {
        "dynamodb": {"read": 8, "write": 12, "storage": 3},
        "lambda": {"compute": 6, "requests": 2},
        "api_gateway": {"requests": 3, "data_transfer": 2},
        "eventbridge": {"events": 2},
        "security": {"kms": 8, "secrets_manager": 3, "waf": 5},
        "monitoring": {"cloudwatch": 3, "xray": 2},
        "s3": {"storage": 2, "requests": 1},
        "total_range": "48-73 USD"
    }
}
```

## Decision Log

### Key Architectural Decisions

1. **Single Table vs Multi-Table** (Jan 26, 2025)
   - **Decision**: Single table design
   - **Rationale**: Better performance, cost efficiency, simpler operations
   - **Trade-offs**: More complex data modeling, requires careful key design

2. **Write Sharding Strategy** (Jan 26, 2025) 
   - **Decision**: Hash-based sharding with tenant lookup table
   - **Rationale**: Prevents hot partitions for high-volume tenants
   - **Implementation**: Dynamic shard count based on tenant volume

3. **Compression Strategy** (Jan 26, 2025)
   - **Decision**: Intelligent compression for payloads >1KB
   - **Rationale**: 70% storage cost savings potential
   - **Threshold**: 1KB payload size, gzip compression

4. **Cost Model Correction** (Jan 26, 2025)
   - **Decision**: Realistic cost projections ($15-20 MVP, not $4.50)
   - **Rationale**: Security requirements (KMS, WAF) increase baseline costs
   - **Monitoring**: Real-time cost alerts at $10, $15, $20 thresholds

## Knowledge Base

### Gotchas and Lessons Learned

1. **EventBridge Payload Limits**: 256KB limit requires S3 offloading for large forms
2. **DynamoDB Transactions**: Cost 2x normal operations, use sparingly
3. **GSI Projections**: ALL projections increase storage costs significantly
4. **TTL Timing**: TTL deletion happens within 48 hours, not immediately
5. **Conditional Writes**: Essential for idempotency but add latency

### Integration Patterns

1. **EventBridge → DynamoDB Streams**: Use for real-time dashboard updates
2. **Lambda → DynamoDB**: Connection pooling critical for performance
3. **Step Functions → DynamoDB**: Batch operations for delivery attempts
4. **API Gateway → DynamoDB**: Direct integration for simple queries

## Todo/Backlog

### Short Term (Next 2 Weeks)
- [ ] Implement complete single-table schema for form submissions
- [ ] Add write sharding for high-volume tenants  
- [ ] Create pre-aggregated metrics tables
- [ ] Implement intelligent payload compression
- [ ] Add domain reverse lookup functionality

### Medium Term (Next Month)
- [ ] Implement cost optimization recommendations engine
- [ ] Add advanced monitoring and alerting
- [ ] Create tenant isolation audit procedures
- [ ] Optimize GSI design based on query patterns
- [ ] Implement backup and recovery procedures

### Long Term (Next Quarter)
- [ ] Multi-region replication strategy
- [ ] Advanced analytics with DynamoDB Streams
- [ ] ML-based cost optimization
- [ ] Automated capacity planning
- [ ] Compliance audit automation

## Implementation Roadmap

### Phase 1: Core Schema (Week 1)
1. Design and implement complete single-table schema
2. Create access pattern implementations
3. Add basic compression for large payloads
4. Implement tenant isolation validation

### Phase 2: Optimization (Week 2-3)
1. Implement write sharding strategy
2. Add pre-aggregated metrics
3. Create domain lookup optimization  
4. Add cost monitoring and alerting

### Phase 3: Advanced Features (Week 4+)
1. Advanced security features
2. Performance optimization
3. Automated cost optimization
4. Compliance and audit features

---

**Next Strategy Update**: February 26, 2025  
**Focus Areas**: Performance optimization results, cost analysis, scaling patterns
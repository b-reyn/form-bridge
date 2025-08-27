# Minimal DynamoDB Design - MVP Deployment First

## Overview
This is a deliberately simplified DynamoDB configuration designed to deploy without issues. All advanced features have been removed to prioritize deployment success over optimization.

## Table Structure

### Primary Table: `formbridge-data-{environment}`

**Core Keys:**
- `PK` (Partition Key): String - Primary partitioning key
- `SK` (Sort Key): String - Sorting and uniqueness key

**Global Secondary Index: TenantIndex**
- `GSI1PK` (Partition Key): String - Tenant-scoped queries  
- `GSI1SK` (Sort Key): String - Time-based sorting
- Projection: `KEYS_ONLY` (minimal storage cost)

## Entity Patterns (Simplified)

### 1. Form Submissions
```
PK: TENANT#abc123
SK: SUB#01J7R3S8...
GSI1PK: TENANT#abc123  
GSI1SK: TS#2025-08-26T10:00:00Z

Attributes:
- form_id: string
- payload: object
- status: string (pending, processing, delivered, failed)
- created_at: ISO timestamp
```

### 2. Tenant Configuration
```
PK: TENANT#abc123
SK: CONFIG#main
GSI1PK: CONFIG#active
GSI1SK: TENANT#abc123

Attributes:
- tenant_name: string
- api_key_hash: string  
- destinations: array of destination objects
- settings: configuration object
```

### 3. Delivery Destinations
```
PK: TENANT#abc123
SK: DEST#webhook1
GSI1PK: TENANT#abc123
GSI1SK: DEST#webhook1

Attributes:
- destination_type: webhook|email|zapier
- endpoint_url: string
- auth_config: object
- enabled: boolean
```

## Access Patterns

### Query 1: Get Submission by ID
```python
dynamodb.get_item(
    Key={
        'PK': 'TENANT#abc123',
        'SK': 'SUB#01J7R3S8...'
    }
)
```

### Query 2: List Recent Submissions for Tenant
```python
dynamodb.query(
    IndexName='TenantIndex',
    KeyConditionExpression='GSI1PK = :tenant AND GSI1SK BETWEEN :start AND :end',
    ExpressionAttributeValues={
        ':tenant': 'TENANT#abc123',
        ':start': 'TS#2025-08-25T00:00:00Z',
        ':end': 'TS#2025-08-26T23:59:59Z'
    }
)
```

### Query 3: Get Tenant Configuration
```python
dynamodb.get_item(
    Key={
        'PK': 'TENANT#abc123', 
        'SK': 'CONFIG#main'
    }
)
```

### Query 4: List Tenant Destinations
```python
dynamodb.query(
    KeyConditionExpression='PK = :tenant AND begins_with(SK, :dest)',
    ExpressionAttributeValues={
        ':tenant': 'TENANT#abc123',
        ':dest': 'DEST#'
    }
)
```

## Billing Configuration

**Mode:** Pay-per-request (on-demand)
- No capacity planning required
- Automatic scaling
- No minimum costs
- Perfect for unpredictable workloads

**Expected Costs (MVP):**
- 1,000 submissions/month: ~$2-3/month
- 10,000 submissions/month: ~$8-12/month  
- 100,000 submissions/month: ~$35-50/month

## Multi-Tenant Isolation

**Tenant Prefix Pattern:**
- All tenant data uses `TENANT#{tenant_id}` prefix
- Ensures natural partitioning in DynamoDB
- Enables IAM policies for tenant isolation
- Makes tenant deletion easy (delete by prefix)

**Security Model:**
```json
{
  "Version": "2012-10-17", 
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "dynamodb:GetItem",
      "dynamodb:Query", 
      "dynamodb:PutItem"
    ],
    "Resource": "arn:aws:dynamodb:*:*:table/formbridge-data-*",
    "Condition": {
      "ForAllValues:StringEquals": {
        "dynamodb:LeadingKeys": ["TENANT#${aws:PrincipalTag/TenantId}"]
      }
    }
  }]
}
```

## What's Missing (Day 2 Features)

This minimal design removes several important production features that should be added after deployment is working:

1. **Security Features (REMOVED):**
   - Encryption at rest (SSESpecification)
   - Point-in-time recovery (PointInTimeRecoverySpecification)
   - KMS key management

2. **Performance Features (REMOVED):**
   - Additional GSIs for complex queries
   - Write sharding for high-volume tenants
   - Connection pooling optimizations

3. **Operational Features (REMOVED):**
   - DynamoDB Streams for real-time processing
   - TTL for automatic cleanup
   - Backup configurations
   - CloudWatch alarms

4. **Advanced Patterns (REMOVED):**
   - Pre-aggregated metrics tables
   - Delivery attempt tracking
   - Batch processing optimizations
   - Intelligent compression

## Deployment Validation

After deployment, validate the table works:

```python
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('formbridge-data-dev')

# Test write
table.put_item(Item={
    'PK': 'TENANT#test123',
    'SK': 'CONFIG#main', 
    'tenant_name': 'Test Tenant',
    'created_at': '2025-08-26T10:00:00Z'
})

# Test read
response = table.get_item(Key={
    'PK': 'TENANT#test123',
    'SK': 'CONFIG#main'
})
print(response['Item'])

# Test GSI query
response = table.query(
    IndexName='TenantIndex',
    KeyConditionExpression='GSI1PK = :pk',
    ExpressionAttributeValues={':pk': 'TENANT#test123'}
)
print(f"Found {len(response['Items'])} items")
```

## Next Steps After Deployment

Once this minimal table deploys successfully:

1. Add TTL specification for automatic cleanup
2. Enable point-in-time recovery
3. Add encryption at rest with customer-managed keys
4. Implement additional GSIs based on query patterns
5. Add DynamoDB Streams for real-time processing
6. Create CloudWatch alarms for monitoring
7. Implement cost optimization strategies

The goal is: **Deploy first, enhance later.**
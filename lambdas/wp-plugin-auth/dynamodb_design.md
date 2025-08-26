# DynamoDB Single Table Design for WordPress Plugin Authentication

## Table Structure

**Table Name:** `form-bridge-plugin-auth`

**Primary Key:**
- Partition Key (PK): String
- Sort Key (SK): String

**Global Secondary Indexes:**
- GSI1: GSI1PK (String), GSI1SK (String)
- GSI2: GSI2PK (String), GSI2SK (String) [Optional for advanced queries]

**Attributes:**
- TTL: Number (Unix timestamp for automatic expiration)

## Access Patterns

### 1. Site Registration Management

#### Temporary Registration (Initial Registration)
```
PK: SITE#{domain}
SK: REG#{registration_id}
GSI1PK: TEMP#{temp_key}
GSI1SK: STATUS#pending

Attributes:
- registration_id: String
- domain: String
- temp_key: String (temporary key for key exchange)
- status: String (pending, active, expired)
- wp_version: String
- plugin_version: String
- admin_email: String (optional)
- agency_id: String (optional)
- client_ip: String
- created_at: String (ISO 8601)
- expires_at: String (ISO 8601)
- ttl: Number (automatic cleanup)
```

**Queries:**
- Get registration by domain: `PK = SITE#{domain}`
- Find registration by temp key: `GSI1PK = TEMP#{temp_key}`
- List pending registrations: `GSI1PK = STATUS#pending`

#### Site Credentials (After Key Exchange)
```
PK: SITE#{domain}
SK: CREDS#{site_id}
GSI1PK: SITE#{site_id}
GSI1SK: ACTIVE

Attributes:
- site_id: String (permanent site identifier)
- domain: String
- api_key_hash: String (SHA256 of API key)
- webhook_secret: String
- status: String (active, suspended, disabled)
- created_at: String (ISO 8601)
- activated_at: String (ISO 8601)
- last_seen: String (ISO 8601)
- request_count: Number
- rate_limit_remaining: Number
```

**Queries:**
- Get credentials by domain: `PK = SITE#{domain}, SK = CREDS#{site_id}`
- Find active site by site_id: `GSI1PK = SITE#{site_id}, GSI1SK = ACTIVE`
- List all active sites: `GSI1SK = ACTIVE`

### 2. API Key Management

#### API Key Lookup
```
PK: API#{api_key_hash}
SK: LOOKUP
GSI1PK: SITE#{site_id}
GSI1SK: API_KEY

Attributes:
- site_id: String
- domain: String
- created_at: String (ISO 8601)
- last_used: String (ISO 8601)
```

**Queries:**
- Validate API key: `PK = API#{api_key_hash}, SK = LOOKUP`
- Find API keys by site: `GSI1PK = SITE#{site_id}, GSI1SK = API_KEY`

### 3. Rate Limiting

#### Rate Limit Counters (Per-Site)
```
PK: RATE#{site_id}
SK: TIME#{timestamp}
GSI1PK: RATE#{site_id}
GSI1SK: TIME#{timestamp}

Attributes:
- timestamp: Number (Unix timestamp)
- request_type: String (api, webhook, update_check)
- ttl: Number (auto-cleanup after 24 hours)
```

**Queries:**
- Check rate limits for site: `PK = RATE#{site_id}, SK BETWEEN TIME#{start} AND TIME#{end}`
- Time-based rate limit analysis: `GSI1PK = RATE#{site_id}, GSI1SK BETWEEN TIME#{start} AND TIME#{end}`

#### Rate Limit Counters (Per-IP, for registration)
```
PK: RATE#{client_ip}
SK: TIME#{timestamp}
GSI1PK: RATE#{client_ip}
GSI1SK: TIME#{timestamp}

Attributes:
- timestamp: Number (Unix timestamp)
- action: String (registration, key_exchange, validation)
- ttl: Number (auto-cleanup after 5 minutes for registration)
```

### 4. Site Validation Results

#### Validation Cache
```
PK: VALIDATION#{domain}
SK: RESULT
GSI1PK: REG#{registration_id}
GSI1SK: VALIDATION

Attributes:
- domain: String
- registration_id: String
- validation_level: String (basic, standard, strict)
- passes_validation: Boolean
- validation_score: Number
- validation_results: Map (detailed check results)
- validated_at: String (ISO 8601)
- valid_until: String (ISO 8601)
- ttl: Number (auto-cleanup after 24 hours)
```

**Queries:**
- Get validation for domain: `PK = VALIDATION#{domain}, SK = RESULT`
- Find validation by registration: `GSI1PK = REG#{registration_id}, GSI1SK = VALIDATION`

### 5. Plugin Version Management

#### Version Information Cache
```
PK: PLUGIN_VERSION#latest
SK: INFO
GSI1PK: VERSION#{version}
GSI1SK: RELEASE

Attributes:
- version_info: Map (version details)
- cached_at: String (ISO 8601)
- ttl: Number (auto-cleanup after 2 hours)
```

#### Update Check Tracking
```
PK: UPDATE_CHECK#{site_id}
SK: TIME#{timestamp}
GSI1PK: UPDATES#{latest_version}
GSI1SK: SITE#{site_id}

Attributes:
- site_id: String
- domain: String
- current_version: String
- latest_version: String
- update_available: Boolean
- checked_at: String (ISO 8601)
- ttl: Number (auto-cleanup after 90 days)
```

**Queries:**
- Get update history for site: `PK = UPDATE_CHECK#{site_id}`
- Find sites checking specific version: `GSI1PK = UPDATES#{version}`
- Track update adoption: `GSI1SK = SITE#{site_id}`

### 6. Security Event Logging

#### Failed Authentication Attempts
```
PK: FAILED#{site_id}
SK: TIME#{timestamp}
GSI1PK: SECURITY#{event_type}
GSI1SK: TIME#{timestamp}

Attributes:
- site_id: String
- domain: String (optional)
- event_type: String (auth_failure, rate_limit, suspicious_activity)
- client_ip: String
- user_agent: String
- details: Map (event-specific details)
- timestamp: String (ISO 8601)
- ttl: Number (auto-cleanup after 30 days)
```

**Queries:**
- Get failed attempts for site: `PK = FAILED#{site_id}`
- Analyze security events by type: `GSI1PK = SECURITY#{event_type}`
- Time-based security analysis: `GSI1SK BETWEEN TIME#{start} AND TIME#{end}`

#### Abuse Pattern Detection
```
PK: ABUSE#{pattern_type}
SK: {identifier}#{timestamp}
GSI1PK: ABUSE_TRACKING#{identifier}
GSI1SK: TIME#{timestamp}

Attributes:
- pattern_type: String (registration_spam, api_abuse, invalid_domains)
- identifier: String (ip_address, domain, site_id)
- severity: String (low, medium, high, critical)
- details: Map (pattern-specific data)
- detected_at: String (ISO 8601)
- ttl: Number (varies by severity)
```

### 7. Agency/Multi-Site Management

#### Agency Groups (for bulk registration)
```
PK: AGENCY#{agency_id}
SK: INFO
GSI1PK: AGENCY_META#{agency_id}
GSI1SK: ACTIVE

Attributes:
- agency_id: String
- agency_name: String
- contact_email: String
- max_sites: Number
- current_sites: Number
- created_at: String (ISO 8601)
- status: String (active, suspended)
```

#### Agency Site Relationships
```
PK: AGENCY#{agency_id}
SK: SITE#{site_id}
GSI1PK: SITE#{site_id}
GSI1SK: AGENCY#{agency_id}

Attributes:
- agency_id: String
- site_id: String
- domain: String
- added_at: String (ISO 8601)
- role: String (owner, member, viewer)
```

**Queries:**
- Get all sites for agency: `PK = AGENCY#{agency_id}, SK BEGINS_WITH SITE#`
- Find agency for site: `GSI1PK = SITE#{site_id}, GSI1SK BEGINS_WITH AGENCY#`

## Data Lifecycle Management

### TTL Settings
- **Registration Records**: 1 hour (3600 seconds)
- **Rate Limit Records**: 24 hours (86400 seconds) for analysis, 5 minutes (300 seconds) for registration limits
- **Validation Cache**: 24 hours (86400 seconds)
- **Version Cache**: 2 hours (7200 seconds)
- **Security Events**: 30 days (2592000 seconds)
- **Update Check History**: 90 days (7776000 seconds)
- **Abuse Records**: Variable based on severity (1-90 days)

### Automatic Cleanup
All temporary data uses DynamoDB TTL for automatic cleanup, reducing storage costs and maintaining data hygiene.

## Security Considerations

### 1. Data Isolation
- Each entity type uses distinct PK prefixes
- No cross-contamination between different data types
- Agency boundaries enforced at application level

### 2. Sensitive Data Handling
- API keys are never stored in plain text (only SHA256 hashes)
- Webhook secrets are encrypted at rest
- Client IPs are stored but can be hashed for privacy

### 3. Access Control
- Lambda functions use least-privilege IAM roles
- Different functions access only required data patterns
- No direct table access from client applications

### 4. Audit Trail
- All security events are logged with timestamps
- Rate limiting events are tracked for analysis
- Failed authentication attempts are recorded

## Performance Optimization

### 1. Hot Partition Avoidance
- Time-based SKs distribute load across partitions
- Site IDs and domains provide natural distribution
- Rate limit records use site_id prefixes for isolation

### 2. Query Efficiency
- GSI1 enables efficient lookups by alternate keys
- Sparse indexes reduce storage costs
- TTL automatic cleanup prevents table growth

### 3. Cost Optimization
- On-demand billing for variable workloads
- TTL reduces long-term storage costs
- Efficient access patterns minimize RCU/WCU usage

This single table design supports all WordPress plugin authentication use cases while maintaining security, performance, and cost efficiency. The schema prevents one compromised site from affecting others while enabling easy deployment for legitimate users.
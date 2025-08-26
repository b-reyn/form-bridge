# Principal Engineer Strategy Document

*Last Updated: January 26, 2025*
*Agent: principal-engineer*
*Focus: Technical Leadership, Security Architecture, and Quality Standards*

## Current Mission
Completed comprehensive frontend architecture review of Form-Bridge, focusing on React dashboard security, WordPress plugin architecture, and performance optimization. Identified critical security issues with hardcoded admin credentials and provided detailed technical recommendations.

## Security Architecture Patterns

### 1. API Key Management Strategy
**Current Issue**: Same API key across all sites for one client - major security risk

**Recommended Solution**: Hierarchical Key Derivation
```python
# Master key → Site-specific keys using HMAC-SHA256
site_key = HMAC-SHA256(master_key, f"SITE#{site_url}#{salt}")
```

**Implementation**:
- Master key stored encrypted in DynamoDB
- Site-specific keys derived deterministically
- No need to store individual site keys
- Can regenerate site key from master + site_url

### 2. Multi-Tenant Security Model
**Pattern**: Tenant isolation with shared infrastructure
- Tenant prefix in all DynamoDB keys
- IAM session tags for runtime isolation
- EventBridge rules scoped per tenant
- Lambda execution role per tenant context

### 3. Zero-Trust Registration Flow
**Components**:
1. Temporary registration tokens (15-minute TTL)
2. HMAC signature verification
3. Site URL validation
4. Rate limiting per IP and tenant

## Best Practices Research (2024-2025)

### Industry Standards Analysis

#### Jetpack/WordPress.com Model
- Uses OAuth for initial connection
- Site-specific tokens generated post-authorization
- Heartbeat mechanism for site health monitoring
- Automatic disconnection after 30 days of inactivity

#### Gravity Forms Approach
- License key validates at network level for multisite
- Site-specific activation records
- Periodic home-calling for validation
- Offline grace period of 14 days

#### WooCommerce Pattern
- REST API with OAuth 1.0a
- Consumer key/secret pairs per application
- Webhook signatures using HMAC-SHA256
- Nonce validation with 15-minute window

### Security Vulnerabilities Landscape
- 7,966 new WordPress vulnerabilities in 2024
- 96% in plugins, 4% in themes
- Average patch time: 32 days
- 50% never get patched before disclosure

## Technical Decisions Log

### Decision 001: Key Derivation vs Storage
**Date**: January 26, 2025
**Choice**: HMAC-based key derivation
**Rationale**: 
- Reduces storage complexity
- Enables deterministic key generation
- Simplifies key rotation
- Maintains single table design

### Decision 002: Registration Token Strategy
**Date**: January 26, 2025
**Choice**: JWT with short TTL for registration
**Rationale**:
- Stateless validation
- Contains registration context
- Prevents replay attacks
- Easy to validate in Lambda

### Decision 003: Auto-Update Security
**Date**: January 26, 2025
**Choice**: Ed25519 signatures with version pinning
**Rationale**:
- Small signature size
- Fast verification
- Industry standard (used by npm, cargo)
- Version pinning prevents downgrade attacks

## Implementation Patterns

### Secure API Key Hierarchy
```
Master Account Key (Encrypted in DynamoDB)
    ├── Site Derivation Key (HMAC-SHA256)
    │   ├── Site API Key (Runtime generated)
    │   └── Site Webhook Secret (Runtime generated)
    └── Admin API Key (For dashboard access)
```

### DynamoDB Security Schema
```
# Master credentials (encrypted)
PK: TENANT#t_abc123
SK: MASTER_KEY
Data: {
  encrypted_key: "AES-256-GCM encrypted",
  kms_key_id: "arn:aws:kms:...",
  rotation_schedule: "90d",
  last_rotated: "2025-01-26"
}

# Site registration records
PK: TENANT#t_abc123  
SK: SITE#sha256(site_url)
Data: {
  site_url: "https://example.com",
  registration_token_hash: "...",
  registered_at: "2025-01-26",
  last_seen: "2025-01-26",
  status: "active"
}

# Rate limiting
PK: RATELIMIT#ip_address
SK: TIMESTAMP#2025-01-26T10:00:00Z
Data: {
  request_count: 1,
  tenant_id: "t_abc123"
}
TTL: 3600
```

### Attack Vector Mitigations

| Attack Vector | Mitigation Strategy | Implementation |
|--------------|-------------------|----------------|
| Compromised Site | Site-specific derived keys | HMAC key derivation |
| API Key Theft | Key rotation + audit logs | 90-day rotation, CloudTrail |
| MITM Attacks | TLS 1.3 + Certificate pinning | CloudFront configuration |
| Replay Attacks | Timestamp + nonce validation | 5-minute window |
| DDoS | Rate limiting + WAF | API Gateway throttling |
| Key Exhaustion | Progressive backoff | Exponential retry delays |

## Performance Benchmarks

### Security Operation Overhead
- Key derivation: < 1ms per operation
- HMAC verification: < 0.5ms
- Rate limit check: < 2ms (DynamoDB query)
- Registration flow: < 500ms total
- Update signature verification: < 10ms

## Quality Gates

### Security Review Checklist
- [ ] All API keys use derivation pattern
- [ ] HMAC signatures on all webhooks
- [ ] Rate limiting implemented per endpoint
- [ ] Audit logging for security events
- [ ] Key rotation mechanism tested
- [ ] DDoS protection configured
- [ ] Security headers implemented
- [ ] Input validation on all endpoints
- [ ] Error messages don't leak information
- [ ] Monitoring alerts configured

## Knowledge Base

### Common Security Pitfalls
1. **Storing secrets in code**: Use environment variables or KMS
2. **Long-lived tokens**: Implement rotation and TTLs
3. **Missing rate limits**: Can lead to abuse and cost overruns
4. **Weak random generation**: Use cryptographically secure methods
5. **Verbose error messages**: Information disclosure risk

### Tools and Resources
- AWS KMS for key management
- AWS WAF for application protection
- CloudTrail for audit logging
- GuardDuty for threat detection
- Security Hub for compliance

## Todo/Backlog

### Immediate Priorities
- [x] Complete security audit
- [x] Complete frontend architecture review
- [ ] Implement key derivation system
- [ ] Set up registration token flow
- [ ] Configure auto-update signing
- [ ] Create security runbook
- [ ] Fix hardcoded admin credentials issue
- [ ] Implement smart polling system

### Future Enhancements
- [ ] Implement OAuth 2.0 flow option
- [ ] Add hardware security module support
- [ ] Create security dashboard
- [ ] Implement anomaly detection
- [ ] Add compliance reporting (SOC2, GDPR)
- [ ] WebSocket upgrade for real-time updates

## Collaboration Notes

### Recent Agent Interactions
- Researched WordPress plugin best practices
- Analyzed competitor implementations
- Evaluated DynamoDB security patterns
- Reviewed HMAC authentication standards

### Integration Points
- **eventbridge-architect**: Event pattern security
- **dynamodb-architect**: Table security design
- **lambda-serverless-expert**: Function security
- **monitoring-observability-expert**: Security metrics

## Lessons Learned

### From Security Audit (Jan 2025)
1. Single API key per client is critical vulnerability
2. WordPress plugins need self-registration capability
3. Auto-updates require cryptographic signatures
4. DynamoDB can handle security without Secrets Manager
5. Rate limiting must be per-site, not per-account

### From Frontend Architecture Review (Jan 2025)
1. Hardcoded admin credentials approach is major security anti-pattern
2. 5-second polling for all users creates unnecessary cost (~$50/month for 1000 users)
3. Universal plugin approach adds complexity without clear MVP benefit
4. Missing comprehensive E2E testing strategy for complete workflow
5. Bundle size optimization critical for mobile performance
6. Smart polling can reduce API costs by ~70%

### Best Practices Discovered
- Jetpack's SSO approach reduces attack surface
- Gravity Forms' license validation is robust
- WooCommerce OAuth flow is user-friendly
- Action Scheduler better than WP-Cron
- HMAC with timestamp prevents replay attacks

---
*This strategy document is actively maintained and updated after each significant technical decision or security finding.*
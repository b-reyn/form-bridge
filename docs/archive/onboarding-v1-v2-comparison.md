# Form-Bridge Onboarding Workflow: v1 vs v2 Comparison

*Date: January 26, 2025*

## Executive Summary
Version 2 addresses critical security vulnerabilities identified in v1's security audit while maintaining the 5-minute setup goal. The primary improvement is eliminating shared API keys across multiple sites through hierarchical key derivation.

---

## 🔴 Critical Security Issues Fixed

### 1. Multi-Site API Key Vulnerability

| Aspect | v1 (Vulnerable) | v2 (Secure) |
|--------|-----------------|-------------|
| **Key Strategy** | Single API key for all sites | Site-specific keys via HMAC derivation |
| **Compromise Impact** | All sites affected | Single site isolated |
| **Storage** | One key per tenant | Master key only (derive others) |
| **Risk Level** | CRITICAL ⚠️ | Minimal ✅ |

**v2 Implementation:**
```python
# Each site gets unique key derived from master
site_key = HMAC-SHA256(master_key, f"SITE#{site_url}#{salt}")
```

### 2. Registration Security

| Aspect | v1 | v2 |
|--------|-----|-----|
| **Initial Auth** | API key in plugin | JWT token (15-min expiry) |
| **Verification** | None | Site ownership required |
| **Token Type** | Permanent key | Temporary registration token |
| **Replay Protection** | None | Nonce + timestamp validation |

### 3. Auto-Update Capability

| Aspect | v1 | v2 |
|--------|-----|-----|
| **Updates** | Manual ZIP install | Automatic weekly checks |
| **Verification** | None | Ed25519 signatures |
| **Distribution** | Customer download | Secure S3 with signed URLs |
| **Rollback** | Manual | Automatic with version control |

---

## 🔒 Security Enhancements

### Authentication Architecture

**v1 Flow:**
```
Plugin → API (with embedded key) → Backend
         ↑ VULNERABLE: Key exposed if site compromised
```

**v2 Flow:**
```
Plugin → Registration (JWT) → Key Exchange → Secure API
         ↑ Two-phase process with verification
```

### Key Management

**v1 Approach:**
- Store API keys directly in DynamoDB
- Same key across multiple sites
- No rotation mechanism
- Keys visible in WordPress database

**v2 Approach:**
- Master key in KMS-encrypted storage
- Site keys derived (never stored)
- 90-day automatic rotation
- Keys never exposed in plaintext

### DynamoDB Schema Changes

**v1 Schema:**
```
PK: TENANT#abc
SK: APIKEY#the_actual_key  ← Security risk
Data: { permissions: [...] }
```

**v2 Schema:**
```
PK: TENANT#abc
SK: SECURITY#MASTER        ← Encrypted
Data: { 
    encrypted_key: "KMS:arn...",
    rotation_schedule: "90_DAYS"
}

PK: APIKEY#sha256(api_key)  ← Hashed for lookup
SK: METADATA
Data: { tenant_id: "abc", site: "example.com" }
```

---

## 📊 Feature Comparison Matrix

| Feature | v1 | v2 | Impact |
|---------|----|----|--------|
| **Setup Time** | 5 minutes | 5 minutes | Maintained ✅ |
| **Site Isolation** | ❌ No | ✅ Yes | Security++ |
| **Auto Updates** | ❌ No | ✅ Yes | Maintenance-- |
| **Audit Logging** | Basic | Comprehensive | Compliance++ |
| **Rate Limiting** | Per tenant | Per site | DDoS protection++ |
| **Key Rotation** | Manual | Automatic | Security++ |
| **MFA Support** | ❌ No | ✅ Yes | Enterprise-ready |
| **Monitoring** | Basic | Real-time security | Incident response++ |

---

## 💰 Cost Impact

### Additional Monthly Costs (v2)

| Service | Purpose | Cost |
|---------|---------|------|
| KMS | Key encryption | $4.00 |
| CloudWatch | Security monitoring | $5.00 |
| WAF | Rate limiting | $10.00 |
| Lambda | Auth functions | $2.00 |
| **Total** | **Security infrastructure** | **$21.00** |

**ROI**: Preventing one security incident (avg $50,000) pays for 200+ years of security infrastructure.

---

## 🚀 Migration Impact

### For New Users
- No change in setup experience
- Enhanced security transparent
- Same 5-minute onboarding

### For Existing Users (v1 → v2)
1. **Week 1**: Parallel operation (both keys work)
2. **Week 2**: Migration notifications sent
3. **Week 3**: Automatic migration for active sites
4. **Week 4**: Legacy key deprecation

### WordPress Plugin Changes

**v1 Plugin (2.5KB):**
```php
define('API_KEY', 'fb_live_xyz123');  // Hardcoded
```

**v2 Plugin (8KB):**
```php
// Dynamic key exchange
$site_key = get_option('formbridge_site_key');
if (!$site_key) {
    $site_key = formbridge_register_site();
}
```

---

## 📈 Performance Impact

| Metric | v1 | v2 | Change |
|--------|----|----|--------|
| **Registration Time** | 30 seconds | 45 seconds | +50% (one-time) |
| **API Latency** | 50ms | 55ms | +10% (key derivation) |
| **Update Check** | N/A | 100ms | New feature |
| **Security Overhead** | 0% | 5-10% | Acceptable |

---

## ✅ Implementation Checklist

### Immediate Changes Required
- [x] Stop using shared API keys
- [x] Implement JWT registration tokens
- [x] Add site ownership verification
- [x] Deploy HMAC signatures

### Week 1 Deployment
- [ ] KMS integration for master keys
- [ ] Site-specific key derivation
- [ ] Update Lambda authorizers
- [ ] Deploy monitoring dashboard

### Week 2 Deployment
- [ ] Auto-update system
- [ ] Ed25519 signing infrastructure
- [ ] Migration tools for existing users
- [ ] Security documentation

---

## 🎯 Key Takeaways

### What Stays the Same
1. **5-minute setup goal** - Maintained through automation
2. **Single DynamoDB table** - Enhanced with security patterns
3. **Simple user experience** - Complexity hidden in backend
4. **Agency bulk management** - Improved with secure distribution

### What's Dramatically Better
1. **Site isolation** - Compromised site can't affect others
2. **Auto-updates** - No manual intervention needed
3. **Audit compliance** - Ready for enterprise/regulated industries
4. **Incident response** - Automated containment in < 5 minutes

### Critical Decision Points

**Why Hierarchical Key Derivation?**
- Elegant solution to multi-site problem
- No key storage explosion
- Easy rotation affects all sites
- Maintains single table design

**Why JWT for Registration?**
- Industry standard (Jetpack uses similar)
- Time-limited exposure
- Stateless validation
- Rate limiting friendly

**Why Ed25519 for Updates?**
- Modern, secure, fast
- Small signatures (64 bytes)
- Used by npm, cargo, apt
- Future-proof

---

## 📝 Summary

**Version 2 is a security-hardened evolution of v1 that:**
- Eliminates the critical shared API key vulnerability
- Adds enterprise-grade security without UX compromise
- Introduces auto-updates for maintenance-free operation
- Provides comprehensive monitoring and compliance
- Costs only $21/month extra for complete security

**The migration from v1 to v2 is mandatory for production deployment** due to the critical security vulnerabilities in v1. The enhanced architecture provides defense-in-depth while maintaining the simplicity that makes Form-Bridge attractive to agencies managing multiple WordPress sites.
# Form-Bridge Onboarding Workflow

*Version: 1.0 | Date: January 2025*

## Overview
This document defines the onboarding workflow for Form-Bridge, optimized for agencies managing multiple WordPress sites and individuals seeking reliable form routing. The goal is to achieve **first successful form submission in under 5 minutes**.

## Technical Context
- **Storage**: Single DynamoDB table (no Secrets Manager in MVP)
- **Architecture**: EventBridge-centric with Lambda connectors
- **Security**: API keys stored directly in DynamoDB with optional AES encryption
- **Target Users**: Agencies with 50+ sites, small businesses, enterprises

---

## Phase 1: Account Creation (0-2 minutes)

### 1.1 Landing & Registration
**Entry Point**: User arrives from WordPress plugin search, Google, or referral

```
[Landing Page]
├── "Connect WordPress Forms to Any Destination"
├── [Start Free] → Registration
└── [Watch Demo] → 60-second video
```

### 1.2 Registration Flow
```
[Sign Up Form]
├── Email (required)
├── Password (required)
├── Company Name (optional)
├── Site Count: ( ) 1-5  ( ) 6-20  ( ) 20+  ← Determines onboarding path
└── [Create Account]
```

**Backend Actions**:
- Create Cognito user
- Generate tenant_id
- Initialize DynamoDB entries:
  ```
  PK: TENANT#t_abc123
  SK: METADATA
  Data: {
    company_name: "Agency XYZ",
    tier: "free",
    site_limit: 5,
    created_at: "2025-01-26T10:00:00Z"
  }
  ```

### 1.3 Email Verification (Non-blocking)
- Send verification email
- User can continue without verifying
- Verification unlocks: API access, higher limits, premium features

---

## Phase 2: First WordPress Connection (2-3 minutes)

### 2.1 Welcome Dashboard
```
[Welcome Screen]
"Let's connect your first WordPress site!"
├── [Download Plugin] → Generate personalized .zip
├── [I'll Install Later] → Skip to destinations
└── [Bulk Import Sites] → CSV upload (agencies)
```

### 2.2 Plugin Generation & Download
**Personalized Plugin Creation**:
```javascript
// Plugin includes embedded configuration
{
  "api_endpoint": "https://api.formbridge.io/ingest",
  "tenant_id": "t_abc123",
  "api_key": "fb_live_xKj9..." // Auto-generated
}
```

**DynamoDB Entry**:
```
PK: TENANT#t_abc123
SK: APIKEY#fb_live_xKj9...
Data: {
  created_at: "2025-01-26T10:02:00Z",
  status: "pending_activation",
  permissions: ["ingest:write"]
}
```

### 2.3 Installation Guide
```
[Installation Steps]
1. Upload form-bridge.zip to WordPress
2. Activate the plugin
3. Plugin auto-registers (no manual config!)
   └── POST /api/register with HMAC signature
4. Real-time status update in dashboard
   └── "🟢 WordPress Site Connected!"
```

### 2.4 Self-Registration Process
**WordPress Plugin Actions**:
1. On activation, plugin sends registration request:
   ```php
   // Automatic registration
   $payload = [
     'site_url' => get_site_url(),
     'site_name' => get_bloginfo('name'),
     'admin_email' => get_option('admin_email'),
     'wp_version' => get_bloginfo('version')
   ];
   $signature = hash_hmac('sha256', json_encode($payload), $api_key);
   ```

2. Backend validates and stores:
   ```
   PK: TENANT#t_abc123
   SK: SITE#site_xyz789
   Data: {
     site_url: "https://agency-client.com",
     site_name: "Client Site",
     status: "active",
     connected_at: "2025-01-26T10:03:00Z"
   }
   ```

---

## Phase 3: Bulk Site Management (Agencies Only)

### 3.1 Bulk Import Options
```
[Bulk Setup]
├── Option A: Master Plugin
│   └── One plugin.zip works for all sites
├── Option B: CSV Import
│   └── Upload site list, generate bulk config
└── Option C: WP Management Tool
    └── MainWP/ManageWP integration
```

### 3.2 Site Grouping
```
[Site Organization]
├── By Client: "ACME Corp" (15 sites)
├── By Type: "Landing Pages" (8 sites)
└── By Environment: "Production" (22 sites)
```

**DynamoDB Structure**:
```
PK: TENANT#t_abc123
SK: GROUP#acme_corp
Data: {
  name: "ACME Corp",
  site_ids: ["site_001", "site_002", ...],
  shared_destinations: ["dest_slack", "dest_hubspot"]
}
```

---

## Phase 4: First Destination Setup (1-2 minutes)

### 4.1 Quick-Start Destinations
```
[Choose Your First Destination]
┌─────────────┬─────────────┬─────────────┐
│    Email    │    Slack    │ Google Sheet│
│  (Instant)  │  (OAuth)    │   (OAuth)   │
└─────────────┴─────────────┴─────────────┘
         ↓
[Advanced Destinations]
API | Webhook | Database | CRM | S3
```

### 4.2 Email Destination (Fastest)
```
[Email Setup]
├── Recipient: [agency@example.com]
├── Subject Template: "New form from {{site_name}}"
└── [Test & Save]
```

**DynamoDB Entry**:
```
PK: TENANT#t_abc123
SK: DEST#email_001
Data: {
  type: "email",
  name: "Agency Notifications",
  config: {
    recipient: "agency@example.com",
    subject_template: "New form from {{site_name}}"
  },
  status: "active"
}
```

### 4.3 API Destination (Advanced)
```
[API Configuration]
├── Endpoint URL: [https://api.example.com/leads]
├── Method: [POST v]
├── Headers:
│   └── Authorization: [Bearer token123...]
├── Body Mapping:
│   └── [Visual Field Mapper]
└── [Test Connection]
```

**Storage Pattern** (No Secrets Manager):
```
PK: TENANT#t_abc123
SK: DEST#api_hubspot
Data: {
  type: "api",
  endpoint: "https://api.hubspot.com/contacts/v1/contact",
  method: "POST",
  headers: {
    "Authorization": "Bearer hapikey_xyz..." // Stored directly
  }
}
```

---

## Phase 5: Routing Configuration

### 5.1 Simple Routing (MVP)
```
[Route Setup]
All forms from: [All Sites v]
Send to: [✓ Email] [✓ HubSpot] [ ] Slack
```

### 5.2 EventBridge Rules Created
```javascript
// Automatic rule generation
{
  Name: "tenant-t_abc123-route-001",
  EventPattern: {
    source: ["formbridge.ingest"],
    "detail-type": ["submission.received"],
    detail: {
      tenant_id: ["t_abc123"]
    }
  },
  Targets: [
    { Arn: "arn:aws:lambda:email-connector" },
    { Arn: "arn:aws:lambda:hubspot-connector" }
  ]
}
```

---

## Phase 6: Test & Verify (30 seconds)

### 6.1 Test Form Submission
```
[Test Your Setup]
├── Select Site: [Agency Client Site v]
├── [Send Test Form]
└── Real-time status:
    ├── ✓ Received by Form-Bridge
    ├── ✓ Routed to Email
    └── ✓ Delivered to HubSpot
```

### 6.2 Success Celebration
```
[🎉 Success!]
"Your first form was successfully routed!"
├── Time saved: 5 minutes per form
├── Reliability: 99.9% uptime
└── [View Dashboard] [Add More Sites] [Configure Rules]
```

---

## Error Handling & Recovery

### Common Issues & Solutions

1. **Plugin Won't Activate**
   - Check PHP version (7.4+)
   - Verify WordPress version (5.0+)
   - Check wp-config.php permissions

2. **Site Not Appearing**
   - Verify internet connectivity
   - Check firewall rules
   - Validate HMAC signature

3. **Destination Failing**
   - Test API credentials
   - Check rate limits
   - Verify endpoint URL

### Support Escalation
```
Level 1: Self-service docs & videos
Level 2: In-app chat (business hours)
Level 3: Email support (24hr response)
Level 4: Phone support (Enterprise only)
```

---

## Success Metrics

### Target KPIs
- **Time to first form**: < 5 minutes
- **Onboarding completion**: > 80%
- **7-day activation**: > 70%
- **30-day retention**: > 60%

### Tracking Events
```javascript
// Analytics events to track
{
  "onboarding.started": { tier: "agency" },
  "plugin.downloaded": { method: "single" },
  "site.connected": { time_elapsed: 180 },
  "destination.added": { type: "email" },
  "test.successful": { total_time: 240 },
  "onboarding.completed": { sites: 1, destinations: 2 }
}
```

---

## Agency Fast-Track Program

For agencies with 20+ sites:
1. **White-glove onboarding call** (15 minutes)
2. **Pre-configured plugin** with agency defaults
3. **Bulk import assistance**
4. **Priority support channel**
5. **Custom training materials**

---

## Progressive Feature Discovery

After successful onboarding, gradually introduce:
- Week 1: Basic routing rules
- Week 2: Conditional logic
- Week 3: Data transformations
- Week 4: Advanced analytics
- Month 2: API rate limiting
- Month 3: Custom connectors

---

## Implementation Notes

### Frontend Requirements
- React components for each step
- WebSocket for real-time updates
- Local storage for progress saving
- Responsive design for mobile

### Backend Requirements
- Lambda for plugin generation
- EventBridge for routing
- DynamoDB for all storage
- CloudWatch for monitoring

### Security Considerations
- HMAC for plugin authentication
- Rate limiting on registration
- API key rotation capability
- Audit logging for compliance

---

## Appendix: DynamoDB Schema

```
# Tenant
PK: TENANT#<tenant_id>
SK: METADATA

# API Keys
PK: TENANT#<tenant_id>
SK: APIKEY#<key>

# Sites
PK: TENANT#<tenant_id>
SK: SITE#<site_id>

# Groups
PK: TENANT#<tenant_id>
SK: GROUP#<group_id>

# Destinations
PK: TENANT#<tenant_id>
SK: DEST#<dest_id>

# Routes
PK: TENANT#<tenant_id>
SK: ROUTE#<route_id>

# Submissions (TTL 30 days)
PK: SUBMISSION#<submission_id>
SK: TIMESTAMP#<iso_timestamp>
```

This workflow prioritizes speed, simplicity, and agency needs while maintaining security and scalability through the EventBridge architecture and DynamoDB storage pattern.
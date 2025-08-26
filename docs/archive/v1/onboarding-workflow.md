# Form-Bridge Onboarding Workflow Design

## Executive Summary
A progressive, personalized onboarding flow that gets users from signup to their first successful form routing in under 10 minutes, with special optimization for agencies managing multiple WordPress sites.

## Core Principles
1. **Quick Win First**: Route one form successfully before asking for more setup
2. **Progressive Disclosure**: Reveal advanced features only when needed
3. **Self-Service**: Minimize manual intervention through automation
4. **Agency-Optimized**: Bulk operations and site grouping from day one

---

## Stage 1: Account Creation & First Login (2-3 minutes)

### 1.1 Registration Flow

**Entry Points:**
- Direct signup from landing page
- WordPress plugin "Get API Key" button
- Partner referral links

**Signup Form (Minimal Friction):**
```
Required Fields Only:
- Email address
- Password (with strength indicator)
- [Continue with Google/Microsoft] (OAuth options)

NOT Required Initially:
- Company name (ask later)
- Phone number (never required)
- Credit card (free tier first)
```

**Email Verification:**
- Send verification email but DON'T block access
- Allow immediate dashboard access
- Show gentle reminder banner: "Please verify your email to unlock all features"
- Auto-verify if user clicks link within 7 days

### 1.2 Initial Workspace Setup

**Welcome Screen:**
```
"Welcome to Form-Bridge! Let's get your first form routing in 3 minutes."

What describes you best?
[ ] I manage one WordPress site (Solo)
[ ] I manage 2-10 sites (Small Agency)  
[ ] I manage 10+ sites (Agency) [RECOMMENDED PATH]
[ ] I'm just exploring

[Continue →]
```

**Personalization Based on Selection:**
- **Solo**: Skip to single site setup
- **Small Agency**: Show site grouping options
- **Agency**: Enable bulk operations immediately
- **Exploring**: Provide sandbox environment

### 1.3 Tier Selection (Deferred)

**Progressive Pricing:**
- Start on free tier automatically (100 submissions/month)
- Show upgrade prompts only after:
  - 50% of free tier consumed
  - Attempting to add 4th destination
  - Requesting premium features

**Tier Structure:**
```
Free: 100 submissions, 1 site, 3 destinations
Starter ($29): 10K submissions, 10 sites, unlimited destinations  
Pro ($99): 100K submissions, unlimited sites, priority support
Enterprise: Custom pricing, SLA, dedicated support
```

---

## Stage 2: First WordPress Site Connection (3-4 minutes)

### 2.1 Plugin Download Mechanism

**Smart Plugin Delivery:**
```
"Let's connect your first WordPress site"

Option A: [Quick Install] - One-click install via WordPress.com API
Option B: [Download Plugin] - Manual installation (.zip file)
Option C: [Install via WP Admin] - Copy install command

For Agencies:
[Bulk Setup] - Download master plugin with pre-configured API key
```

### 2.2 Installation Guidance

**Interactive Installation Guide:**
```
Step-by-step with screenshots:
1. ✓ Plugin downloaded
2. ⏳ Upload to WordPress (Show: Plugins > Add New > Upload)
3. ⏳ Activate plugin
4. ⏳ Plugin will auto-register...

[Having trouble? Watch 60-second video]
[Chat with support]
```

### 2.3 Self-Registration Process

**Automatic Site Registration:**
```
Plugin Auto-Registration Flow:
1. Plugin activated on WordPress site
2. Generates site UUID and HMAC secret
3. Sends registration request to Form-Bridge API:
   {
     "site_url": "agency-site-001.com",
     "site_name": "Client ABC Site",
     "wordpress_version": "6.4",
     "plugin_version": "1.0.0",
     "admin_email": "admin@agency.com"
   }
4. API creates DynamoDB entry:
   PK: TENANT#agency_123
   SK: SITE#auto_generated_uuid
5. Returns confirmation to plugin
6. Plugin stores HMAC secret locally
```

### 2.4 Connection Verification

**Real-Time Verification:**
```
Dashboard shows live status:
[⏳] Waiting for plugin activation...
[✓] Site connected: agency-site-001.com
[!] Test form ready to submit

Quick Test:
"Click here to send a test form from your site"
[One-click test that submits form with dummy data]
```

---

## Stage 3: Bulk Site Management (Agencies)

### 3.1 Efficient Multi-Site Addition

**Bulk Operations Interface:**
```
"Add Multiple Sites"

Option 1: [Master Plugin]
Download one plugin with your API key embedded
Install on all sites (they auto-register)

Option 2: [CSV Import]
Upload CSV with site URLs and names
We'll generate individual setup links

Option 3: [WordPress Multisite]
Single plugin installation for entire network

Option 4: [API Integration]
POST /sites/bulk with array of sites
```

### 3.2 Site Grouping/Tagging

**Organization Structure:**
```
Sites Organization:
├── Client Groups
│   ├── ABC Corp (15 sites)
│   ├── XYZ Inc (8 sites)
│   └── Personal Sites (3 sites)
├── Site Types
│   ├── E-commerce (12 sites)
│   ├── Lead Generation (18 sites)
│   └── Contact Forms (10 sites)
└── Environments
    ├── Production (35 sites)
    └── Staging (5 sites)

[Bulk Actions]: Apply destinations to entire groups
```

### 3.3 Credential Management

**Shared vs Individual Credentials:**
```
Destination Credentials Strategy:

Shared (Recommended for Agencies):
- One HubSpot API key for all client sites
- Single Slack workspace for notifications
- Stored at agency level in DynamoDB

Individual (Per-Client):
- Separate Salesforce instances per client
- Different S3 buckets per site
- Override shared credentials when needed

DynamoDB Structure:
PK: CLIENT#agency_123, SK: CONNECTOR#hubspot (shared)
PK: CLIENT#agency_123, SK: SITE#001#CONNECTOR#salesforce (individual)
```

---

## Stage 4: First Destination Setup (2-3 minutes)

### 4.1 Destination Selection

**Smart Recommendation:**
```
"Where should we send your form submissions?"

Popular Quick Starts:
[Email] - Get instant notifications (30 seconds)
[Slack] - Team notifications (1 minute)
[Google Sheets] - Simple spreadsheet (2 minutes)

CRM Integration:
[HubSpot] [Salesforce] [Pipedrive]

Advanced:
[Webhook] [S3] [Database] [Custom API]

[Skip for now - just store in Form-Bridge]
```

### 4.2 Credential Configuration

**Progressive Credential Collection:**
```
Example: Slack Setup

1. "Connect to Slack" [OAuth button]
2. Select channel: [#general ▼]
3. Message format: 
   [Use template ▼]
   - Simple notification
   - Detailed with all fields
   - Custom format
4. Test connection: [Send test message]
```

**Secure Storage Pattern:**
```
DynamoDB Entry:
PK: CLIENT#agency_123
SK: CONNECTOR#slack#workspace_001
Attributes: {
  connector_type: "slack",
  webhook_url: "https://hooks.slack.com/...",
  channel: "#form-notifications",
  created_at: "2025-01-15T10:00:00Z",
  last_used: "2025-01-15T10:05:00Z",
  status: "active"
}
```

### 4.3 Test Submission Flow

**Interactive Testing:**
```
"Let's test your setup!"

[Send Test Form]
↓
Simulated form data:
{
  "name": "Test User",
  "email": "test@example.com",
  "message": "This is a test submission"
}
↓
[⏳] Sending to Slack...
[✓] Delivered successfully!

[View in Slack] [Send Another] [Continue]
```

### 4.4 Success Verification

**Clear Success Indicators:**
```
✓ Form received by Form-Bridge
✓ Stored in database  
✓ Delivered to Slack
✓ Confirmation webhook sent

"Congratulations! Your first form routing is working!"
[Add another destination] [View dashboard]
```

---

## Stage 5: Quick Win Moment

### 5.1 The "Aha" Moment

**Target: Under 5 minutes to success**
```
Key Success Moment:
User sees their test form submission appear in real destination
(Slack notification, email, spreadsheet row)

Celebration UI:
"🎉 First form routed successfully!"
"You've just automated your form handling. Every submission will now 
automatically route to your configured destinations."

[Share achievement] [Explore more features]
```

### 5.2 Value Demonstration

**Immediate Value Metrics:**
```
Dashboard Shows:
- "Setup time: 4 minutes 32 seconds"
- "Time saved per form: ~5 minutes"
- "Expected monthly time savings: 8 hours"

Quick Stats:
- Forms processed: 1
- Destinations active: 1
- Reliability: 100%
- Average delivery time: 1.2 seconds
```

### 5.3 Next Steps Guidance

**Progressive Feature Discovery:**
```
"What's next?"

Recommended:
□ Add another destination (2 min)
□ Set up form field mapping (3 min)
□ Configure failure notifications (1 min)

Advanced (Show after basics):
□ Add conditional routing rules
□ Set up data transformations
□ Configure webhook retries
□ Enable audit logging
```

---

## Error States & Recovery

### Connection Failures
```
"We couldn't connect to your WordPress site"
Possible solutions:
- Check plugin is activated
- Whitelist our IP: 52.x.x.x
- Verify site is publicly accessible
[Retry] [Manual setup] [Contact support]
```

### Destination Failures
```
"Slack connection failed"
Error: Invalid webhook URL
[Fix: Show webhook URL format example]
[Alternative: Try OAuth connection]
[Skip: Configure later]
```

### Form Submission Failures
```
"Test form didn't arrive"
Troubleshooting:
1. Check WordPress plugin status [Auto-check]
2. Verify HMAC secret [Regenerate]
3. Check form size (<256KB) [View limits]
[Retry test] [Debug mode] [Get help]
```

---

## Success Criteria

### Activation Metrics
- **Time to first form**: < 5 minutes (P50)
- **Time to first destination**: < 10 minutes (P50)
- **Completion rate**: > 80%
- **Drop-off points**: < 10% per step

### User Satisfaction
- **CSAT after onboarding**: > 4.5/5
- **Support tickets during onboarding**: < 5%
- **Feature adoption week 1**: > 3 features

### Business Metrics
- **Free to paid conversion**: > 20% in 30 days
- **7-day retention**: > 70%
- **30-day retention**: > 60%
- **Agency tier adoption**: > 40% of signups

---

## Technical Implementation Notes

### Frontend Requirements
- React/Vue components for each step
- WebSocket for real-time plugin connection status
- Local storage for progress saving
- Analytics events on each step

### Backend Requirements
- Lambda authorizer for API key generation
- DynamoDB for credential storage
- EventBridge for routing logic
- CloudWatch for monitoring onboarding metrics

### WordPress Plugin Requirements
- Auto-registration on activation
- HMAC secret generation
- Health check endpoint
- Automatic updates

---

## A/B Testing Opportunities

1. **Signup Flow**
   - Control: Email + password
   - Variant: OAuth only

2. **Plugin Installation**
   - Control: Manual download
   - Variant: WordPress.com API auto-install

3. **First Destination**
   - Control: User choice
   - Variant: Recommend based on persona

4. **Tier Presentation**
   - Control: Show pricing upfront
   - Variant: Progressive disclosure

---

## Continuous Improvement

### Analytics to Track
- Funnel conversion at each step
- Time spent per step
- Error rates by step
- Feature usage post-onboarding
- Support contact reasons

### Feedback Loops
- Post-onboarding survey (NPS)
- Session recordings review
- Support ticket analysis
- User interview program
- Behavioral cohort analysis

### Iteration Cycle
- Weekly: Review metrics
- Bi-weekly: A/B test results
- Monthly: Major flow optimizations
- Quarterly: Strategic workflow changes
# Multi-Tenant Serverless Form Ingestion & Fan-Out
## Option A: **EventBridge-Centric Architecture (AWS + Python MVP)**

> Goal: Ingest form submissions from WordPress (and other sources), persist them per-tenant, and **fan-out serverlessly** to many destinations (REST, CRM, DB). Ship fast, stay cheap, and scale safely.

---

## TL;DR (What you’ll ship first)
- **API Gateway (HTTP API)** → **Lambda Ingest** (HMAC auth, validate/normalize) → **EventBridge bus**.
- EventBridge **Rules** trigger:
  1) **Lambda Persist** → DynamoDB (`Submissions`), and
  2) **Step Functions Express** workflow **Deliver** (Map over tenant destinations → call tiny connector Lambdas, e.g., `rest-generic`).  
- **Cognito** protects a small React admin to query DynamoDB by tenant.
- **Secrets Manager** holds per-tenant shared secrets + destination credentials.
- **DLQs + retries + audit table** for reliability.

---

## High-Level Flow

```
[WordPress/Django/etc.]
        │  POST JSON + HMAC
        ▼
   API Gateway (HTTP API)
        │  Lambda Authorizer validates tenant + HMAC
        ▼
      Lambda Ingest (normalize, idempotency)
        │  PutEvents(detail=canonical_event)
        ▼
       EventBridge Bus ────────────────┐
          │ Rule: Persist             │ Rule: Deliver
          ▼                           ▼
  Lambda Persist → DynamoDB       Step Functions (Express)
         (Submissions)                 │  Map over destinations
                                       ├─► Lambda connector: rest-generic
                                       ├─► Lambda connector: dynamo-writer
                                       └─► (future) hubspot/salesforce/…
                                       │
                                       └──► On failure → SQS DLQ + DeliveryAttempts
```

---

## Canonical Event (schema v1.0)

```json
{
  "tenant_id": "t_abc123",
  "source": "wordpress",
  "form_id": "contact_us",
  "schema_version": "1.0",
  "submission_id": "01J7R3S8B2JD2VEXAMPLE",  // UUIDv7 preferred
  "submitted_at": "2025-08-25T18:00:00Z",
  "ip": "203.0.113.5",
  "payload": { "name": "Jane", "email": "jane@example.com", "message": "Hello!" },
  "destinations": ["rest:webhookA", "db:dynamo"]
}
```

- **Idempotency**: `submission_id` is required and **unique** per submission. Create client-side or in Ingest Lambda.  
- **Large blobs**: upload to **S3 pre-signed URL** → put S3 URI in `payload.attachments[]`.

---

## Data Model (DynamoDB)

### 1) `Submissions`
- **PK**: `TENANT#{tenant_id}`
- **SK**: `SUB#{submission_id}`
- Attrs: `source, form_id, submitted_at, payload, status`
- **GSI1** (by time): `GSI1PK=TENANT#{tenant_id}`, `GSI1SK=TS#{submitted_at}`
- **TTL** (optional) for raw payload retention policy.

### 2) `Destinations` (per-tenant connectors)
- **PK**: `TENANT#{tenant_id}`
- **SK**: `DEST#{destination_id}`
- Attrs: `type (rest/db/crm)`, `config` (endpoint, mapping, auth mode), `enabled`, `rate_limit`

### 3) `DeliveryAttempts` (audit + retries)
- **PK**: `SUB#{submission_id}`
- **SK**: `DEST#{destination_id}#ATTEMPT#{n}`
- Attrs: `status`, `response_code`, `error`, `duration_ms`, `next_retry_at`

> Keep **secrets out of DynamoDB**. Store them in **Secrets Manager** and reference by ARN in `Destinations.config.auth.secret_ref`.

---

## Public API Contracts

### POST `/ingest`
- **Headers**
  - `X-Tenant-Id`: e.g., `t_abc123`
  - `X-Timestamp`: ISO8601 UTC
  - `X-Signature`: `hex(hmac_sha256(shared_secret, timestamp + "\n" + raw_body))`
- **Body**: raw form payload (arbitrary JSON); Ingest Lambda converts to Canonical Event.
- **Auth**: Lambda Authorizer validates tenant + HMAC + replay window (±5 minutes).

### GET `/submissions?tenant_id=...&since=...&cursor=...`
- **Auth**: Cognito JWT (admin/operator role).  
- **Resp**: `{ items: [...], next_cursor: "..." }` (DynamoDB Query on GSI1).

---

## WordPress (MVP) – Minimal PHP Snippet

```php
<?php
function send_to_ingest($payload) {
  $api = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/ingest";
  $tenant = "t_abc123";
  $secret = "*** rotate me ***";
  $ts = gmdate("c");
  $body = json_encode($payload);
  $sig = hash_hmac('sha256', $ts . "\n" . $body, $secret);
  $resp = wp_remote_post($api, array(
    'headers' => array(
      'Content-Type' => 'application/json',
      'X-Tenant-Id' => $tenant,
      'X-Timestamp' => $ts,
      'X-Signature' => $sig
    ),
    'body' => $body,
    'timeout' => 5
  ));
  // handle $resp / fire-and-forget OK
}
```
Hook this into your form submit action (`wpforms`, `Contact Form 7`, etc.).

---

## Lambda Authorizer (HMAC) – Python Skeleton

```python
import base64, hmac, hashlib, json, os, time
from datetime import datetime, timezone
import boto3

secrets = boto3.client("secretsmanager")

def lambda_handler(event, ctx):
    headers = {k.lower(): v for k,v in event["headers"].items()}
    tenant = headers.get("x-tenant-id")
    ts = headers.get("x-timestamp")
    sig = headers.get("x-signature")
    body = event.get("rawBody") or event.get("body", "")

    if not (tenant and ts and sig):
        return deny("missing headers")

    # Replay window (±5m)
    req_time = datetime.fromisoformat(ts.replace("Z","+00:00"))
    now = datetime.now(timezone.utc)
    if abs((now - req_time).total_seconds()) > 300:
        return deny("stale timestamp")

    # Load shared secret
    sec_arn = os.environ["TENANT_SECRET_PREFIX"] + tenant
    secret = secrets.get_secret_value(SecretId=sec_arn)["SecretString"]

    expected = hmac.new(secret.encode(), f"{ts}\n{body}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return deny("bad signature")

    return allow(tenant)

def allow(tenant):
    return { "isAuthorized": True, "context": { "tenant_id": tenant } }

def deny(reason):
    return { "isAuthorized": False, "context": { "reason": reason } }
```

Attach to API Gateway HTTP API as a **JWT/Lambda authorizer** (HTTP APIs support Simple Responses).

---

## EventBridge: Bus + Rules

- **Bus**: `form-bus`
- **PutEvents** in Ingest Lambda with `detail-type="submission.received"`, `source="ingest"`, `detail=canonical_event`
- **Rules**
  - `PersistRule`: pattern `{ "detail-type": ["submission.received"] }` → **Lambda Persist**
  - `DeliverRule`: pattern `{ "detail-type": ["submission.received"] }` → **Step Functions Express: Deliver**
  - (optional) `ArchiveRule` → Kinesis Firehose → S3 raw archive

Configure **maximum event age** and **retry policy** on each target; set **SQS DLQ** per target for poison events.

---

## Step Functions (Express) – “Deliver” State Machine (ASL Sketch)

```json
{
  "Comment": "Fan-out to destinations",
  "StartAt": "LoadDestinations",
  "States": {
    "LoadDestinations": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "load-destinations",
        "Payload.$": "$"
      },
      "ResultPath": "$.destinations",
      "Next": "ForEachDestination"
    },
    "ForEachDestination": {
      "Type": "Map",
      "ItemsPath": "$.destinations.items",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "Deliver",
        "States": {
          "Deliver": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
              "FunctionName.$": "$.lambda_name",
              "Payload.$": "$"
            },
            "Retry": [
              { "ErrorEquals": ["States.ALL"], "IntervalSeconds": 1, "BackoffRate": 2.0, "MaxAttempts": 6 }
            ],
            "Catch": [
              { "ErrorEquals": ["States.ALL"], "ResultPath": "$.error", "Next": "RecordFailure" }
            ],
            "Next": "RecordSuccess"
          },
          "RecordSuccess": { "Type": "Task", "Resource": "arn:aws:states:::lambda:invoke", "Parameters": { "FunctionName": "record-attempt", "Payload.$": "$" }, "End": true },
          "RecordFailure": { "Type": "Task", "Resource": "arn:aws:states:::lambda:invoke", "Parameters": { "FunctionName": "record-attempt", "Payload.$": "$" }, "End": true }
        }
      },
      "End": true
    }
  }
}
```

Tune `MaxConcurrency` per provider; add **SQS buffer** if a destination is fragile.

---

## Connector: `rest-generic` (Python httpx)

```python
import httpx, os, json, boto3, time
from botocore.exceptions import ClientError

secrets = boto3.client("secretsmanager")

def lambda_handler(event, ctx):
    dest = event["destination"]
    cfg = dest["config"]
    endpoint = cfg["endpoint"]
    mapping = cfg.get("mapping", {})
    auth = cfg.get("auth", {})

    body = build_body(mapping, event)  # map canonical fields → provider shape
    headers = build_headers(auth)

    start = time.time()
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(endpoint, json=body, headers=headers)
            r.raise_for_status()
        return {"status": "ok", "code": r.status_code, "duration_ms": int((time.time()-start)*1000)}
    except httpx.HTTPError as e:
        return {"status": "error", "code": getattr(e.response, "status_code", 0), "message": str(e), "duration_ms": int((time.time()-start)*1000)}

def build_headers(auth):
    mode = auth.get("mode", "none")
    h = {"Content-Type": "application/json"}
    if mode == "api_key_header":
        key = secrets.get_secret_value(SecretId=auth["secret_ref"]) ["SecretString"]
        h[auth.get("header", "X-API-Key")] = key
    elif mode == "bearer_token":
        token = secrets.get_secret_value(SecretId=auth["secret_ref"]) ["SecretString"]
        h["Authorization"] = f"Bearer {token}"
    # oauth2_client_credentials/auth_code would fetch/refresh here
    return h

def build_body(mapping, ev):
    # Simple JSONPath-like mapping demo
    import jmespath
    out = {}
    for k, expr in mapping.items():
        out[k] = jmespath.search(expr, ev)
    return out
```

- Include `submission_id` in the outbound body or header for idempotency observability on the receiving side.

---

## React Admin (MVP)
- **Auth**: Cognito User Pool → JWT.  
- **API**: `/submissions` GET (Lambda querying Dynamo GSI1 with pagination).  
- **UI**: Paginated table w/ filters (tenant, form_id, date range).  
- **Later**: Switch to **AppSync** if you want live filters/aggregations.

```tsx
// SubmissionsTable.tsx (excerpt)
<td><code>{JSON.stringify(s.payload).slice(0, 120)}…</code></td>
```

---

## Observability & Ops
- **Structured logs** (JSON) with `tenant_id`, `submission_id`, `destination_id` across all Lambdas.
- **Metrics/Alarms**:
  - 5xx from Ingest
  - EventBridge target failures
  - Step Functions failed/retired executions
  - DLQ depth (SQS)
  - Connector error rate per destination
- **Tracing**: X-Ray (API GW → Lambda → Step Functions).

---

## Security & Compliance
- **Upstream auth**: HMAC + timestamp; rotate per-tenant secrets in Secrets Manager.
- **Downstream auth**: API keys/Bearer now; add OAuth2 support later (store tokens in Secrets Manager keyed by `tenant_id:destination_id`).
- **PII**: DynamoDB encryption at rest, TLS in transit; consider **TTL** on `Submissions` or move payloads to S3 + Glacier for retention policies.
- **Least privilege**: Separate IAM roles per Lambda; scope Secrets Manager `GetSecretValue` to specific ARNs.
- **Multi-tenant enforcement**: Validate tenant on **every** read/write; prefix keys with `TENANT#{tenant_id}`.

---

## Scaling & Quotas (Where it shines / Caveats)
**Scales well**
- API Gateway + Lambda (thousands RPS; provision per-tenant throttles if desired).
- EventBridge fan-out; Step Functions Express high parallelism.

**Caveats / Gotchas**
- **Payload limits**: API Gateway (10MB), EventBridge (~256KB detail). Put big data in S3 and reference.
- **Cold starts**: Keep Lambdas **out of VPC**; use Python 3.12; slim deps. Provisioned Concurrency only if needed.
- **At-least-once** delivery: design **idempotent** connectors; record `DeliveryAttempts`.
- **Provider rate limits**: backoff on 429/5xx; consider **SQS buffers** or lower `MaxConcurrency` per destination.
- **Ordering**: not guaranteed (fine for forms). If you need ordering per submission, process serially within the Map item.
- **Time-to-first-byte from WordPress**: fire-and-forget from plugin; don’t wait on downstream delivery to respond 200.

---

## Development Plan (MVP → Week 1)
**Day 0-1: Foundations**
- CDK/SAM stack: API GW + Authorizer + Ingest Lambda + EventBridge bus + rules + Persist Lambda + DynamoDB tables + Secrets Manager entries.
- Create tenant secret; install WP snippet and test HMAC POSTs (200 OK).

**Day 2-3: Delivery**
- Step Functions Express “Deliver” + `load-destinations` + `rest-generic` connector.
- `DeliveryAttempts` table + success/failure logging.
- DLQs on EB targets + alarm wiring.

**Day 4: Admin UI**
- Cognito User Pool + `/submissions` GET Lambda.
- React table: paginate + filter by `form_id` and date.

**Day 5: Hardening**
- Load test (k6/Artillery) small spike, confirm retries/backoff & DLQ.
- Rotate a tenant secret; verify authorizer.
- Add S3 upload path for ≥256KB payloads.

**Backlog (near-term)**
- OAuth2 auth-code flow for a CRM (UI dance + token store + refresh).
- EventBridge **Archive + Replay** (nice for reprocessing bugs).
- AppSync GraphQL for richer querying; fine-grained RBAC.

---

## Minimal CDK Structure (Python)

```
infra/
  app.py
  stacks/
    api_stack.py          # API GW, Authorizer, Ingest
    bus_stack.py          # EventBridge bus + rules
    data_stack.py         # DynamoDB, S3 (optional)
    workflow_stack.py     # Step Functions + Lambdas
    auth_stack.py         # Cognito User Pool
lambdas/
  authorizer/
  ingest/
  persist/
  connectors/rest_generic/
  util/record_attempt/
ui/
  src/
```

---

## IAM (principle of least privilege)
- Ingest role: `events:PutEvents` to only your bus ARN.
- Persist role: `dynamodb:PutItem/UpdateItem` on `Submissions`.
- Deliver workflow role: invoke only specific connector functions; write `DeliveryAttempts` only.
- Connector roles: read specific Secrets ARNs; outbound internet (no VPC).

---

## Cost Notes (typical MVP)
- **API GW + Lambda + Step Functions Express + EventBridge + DynamoDB**: low daily cost at modest volume (pennies to a few dollars/day).  
- DynamoDB costs dominated by R/W & storage; start with **on-demand**.  
- Keep logs at **INFO** with sampling; set retention to 14–30 days.

---

## Runbook (Ops)
- **Spike or failures**: Check CloudWatch dashboard → DLQ depth → recent `DeliveryAttempts`.  
- **Replay**: Move DLQ messages back to source queue or re-emit events from archive.  
- **Secret rotation**: Update Secrets Manager; invalidate old after overlap period; notify tenant.  
- **Schema bump**: Increment `schema_version`; maintain backward compatibility in connectors during transition.

---

## Appendix A: Mapping Config Example

```json
{
  "type": "rest",
  "endpoint": "https://example.com/lead",
  "auth": {
    "mode": "api_key_header",
    "header": "X-API-Key",
    "secret_ref": "arn:aws:secretsmanager:us-east-1:123456789012:secret:tenantA-dest1"
  },
  "mapping": {
    "email": "payload.email",
    "name": "payload.name",
    "message": "payload.message",
    "submission_id": "submission_id",
    "when": "submitted_at"
  },
  "retry": { "max": 6, "backoff": "exponential", "base_ms": 500 }
}
```

---

## Appendix B: Example EventBridge Put (Ingest Lambda)

```python
import boto3, json, os, uuid, datetime

events = boto3.client("events")

def handler(event, ctx):
    tenant = event["requestContext"]["authorizer"]["lambda"]["tenant_id"]
    body = json.loads(event["body"])
    submission_id = body.get("submission_id") or new_uuid_v7()
    detail = to_canonical(tenant, body, submission_id)
    events.put_events(Entries=[{
        "Source": "ingest",
        "DetailType": "submission.received",
        "Detail": json.dumps(detail),
        "EventBusName": os.environ["BUS_NAME"]
    }])
    return {"statusCode": 200, "body": json.dumps({"ok": True, "submission_id": submission_id})}
```

---

## Appendix C: React Query Endpoint (GET /submissions)

```python
# Lambda querySubmissions (pseudo)
import boto3, os, json
ddb = boto3.client("dynamodb")

def handler(event, ctx):
    q = event["queryStringParameters"] or {}
    tenant_id = q["tenant_id"]
    since = q.get("since", "1970-01-01T00:00:00Z")
    cursor = q.get("cursor")

    kwargs = {
      "TableName": os.environ["TABLE_SUBMISSIONS"],
      "IndexName": "GSI1",
      "KeyConditionExpression": "GSI1PK=:p AND GSI1SK BETWEEN :s AND :e",
      "ExpressionAttributeValues": {
        ":p": {"S": f"TENANT#{tenant_id}"},
        ":s": {"S": f"TS#{since}"},
        ":e": {"S": f"TS#9999-12-31T23:59:59Z"}
      },
      "Limit": 50
    }
    if cursor: kwargs["ExclusiveStartKey"] = json.loads(cursor)
    resp = ddb.query(**kwargs)
    items = [unmarshal(i) for i in resp["Items"]]
    next_cursor = json.dumps(resp["LastEvaluatedKey"]) if "LastEvaluatedKey" in resp else None
    return {"statusCode": 200, "body": json.dumps({"items": items, "next_cursor": next_cursor})}
```

---

### That’s the MVP.
It’s “boring on purpose,” serverless-cheap, and scales to your 50+ sites with clean multi-tenant isolation. Add OAuth2 connectors, S3 archival, and AppSync as you grow.


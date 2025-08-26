# Form-Bridge MVP: Comprehensive Test-Driven Development Plan

## Executive Summary

This TDD plan provides a structured approach to testing the Form-Bridge MVP, a multi-tenant serverless form ingestion and fan-out system. The plan emphasizes cost-effective testing using LocalStack, comprehensive coverage of critical paths, and a phased implementation approach that ensures quality while maintaining development velocity.

**Key Metrics:**
- Target test coverage: 80% overall (100% for critical paths)
- Test execution time: <5 minutes full suite
- Testing infrastructure cost: <$20/month
- Implementation timeline: 3 phases over 6 weeks

## Testing Pyramid Strategy

### 1. Unit Tests (70% - Target Coverage: 85%)

**Focus**: Individual function logic, business rules, data transformations

**Examples**:
```python
# Lambda handler unit test
def test_hmac_validation():
    """Test HMAC signature validation logic"""
    secret = "test_secret_key"
    timestamp = "2025-08-26T10:00:00Z"
    body = '{"email": "test@example.com"}'
    
    signature = generate_hmac_signature(secret, timestamp, body)
    assert validate_hmac_signature(secret, timestamp, body, signature) == True
    
    # Test with tampered body
    tampered_body = '{"email": "hacker@evil.com"}'
    assert validate_hmac_signature(secret, timestamp, tampered_body, signature) == False
```

```python
# DynamoDB query logic
def test_tenant_data_isolation():
    """Ensure tenant data is properly isolated"""
    submissions = query_submissions_by_tenant("tenant_123", since="2025-01-01")
    
    # Verify all results belong to the correct tenant
    for submission in submissions:
        assert submission['PK'].startswith('TENANT#tenant_123')
        assert 'tenant_456' not in str(submission)
```

```javascript
// React component unit test
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SubmissionForm from '../components/SubmissionForm';

test('validates email format before submission', async () => {
  const user = userEvent.setup();
  render(<SubmissionForm />);
  
  const emailInput = screen.getByLabelText(/email/i);
  await user.type(emailInput, 'invalid-email');
  await user.click(screen.getByRole('button', { name: /submit/i }));
  
  expect(screen.getByText(/valid email/i)).toBeInTheDocument();
});
```

### 2. Integration Tests (20% - Target Coverage: 90%)

**Focus**: Component interactions, AWS service integrations, workflow validation

**Examples**:
```python
# EventBridge to Lambda integration
@pytest.mark.integration
def test_eventbridge_lambda_routing(eventbridge_client, lambda_client):
    """Test event routing from EventBridge to Lambda processors"""
    
    # Create test event
    test_event = {
        "tenant_id": "test_tenant",
        "submission_id": "01J7R3S8B2JD2VEXAMPLE",
        "payload": {"email": "test@example.com"}
    }
    
    # Put event to EventBridge
    response = eventbridge_client.put_events(
        Entries=[{
            'Source': 'ingest',
            'DetailType': 'submission.received',
            'Detail': json.dumps(test_event),
            'EventBusName': 'form-bus'
        }]
    )
    
    # Verify event was processed by both persist and deliver lambdas
    time.sleep(2)  # Allow async processing
    
    # Check DynamoDB for persisted submission
    item = dynamodb_table.get_item(
        Key={'PK': f'TENANT#{test_event["tenant_id"]}', 
             'SK': f'SUB#{test_event["submission_id"]}'}
    )
    assert 'Item' in item
    
    # Check delivery attempts table
    attempts = query_delivery_attempts(test_event["submission_id"])
    assert len(attempts) > 0
```

```python
# API Gateway to Lambda integration
@pytest.mark.integration
def test_api_gateway_hmac_auth_flow():
    """Test complete API Gateway authentication flow"""
    
    # Valid HMAC request
    timestamp = datetime.utcnow().isoformat() + 'Z'
    body = '{"name": "John", "email": "john@example.com"}'
    signature = generate_hmac_signature(TEST_SECRET, timestamp, body)
    
    response = requests.post(f'{API_GATEWAY_URL}/ingest', 
        headers={
            'X-Tenant-Id': 'test_tenant',
            'X-Timestamp': timestamp,
            'X-Signature': signature,
            'Content-Type': 'application/json'
        },
        data=body
    )
    
    assert response.status_code == 200
    response_data = response.json()
    assert 'submission_id' in response_data
```

### 3. End-to-End Tests (10% - Target Coverage: 100% of Critical Paths)

**Focus**: Complete user workflows, cross-system integration

**Examples**:
```javascript
// Playwright E2E test
import { test, expect } from '@playwright/test';

test('complete WordPress to dashboard workflow', async ({ page, context }) => {
  // Simulate WordPress form submission
  const submissionResponse = await context.request.post('/api/ingest', {
    headers: {
      'X-Tenant-Id': 'e2e_tenant',
      'X-Timestamp': new Date().toISOString(),
      'X-Signature': await generateHmacSignature(testData)
    },
    data: {
      name: 'E2E Test User',
      email: 'e2e@example.com',
      message: 'End-to-end test submission'
    }
  });
  
  expect(submissionResponse.ok()).toBeTruthy();
  const submissionData = await submissionResponse.json();
  
  // Navigate to dashboard and verify submission appears
  await page.goto('/dashboard');
  await page.fill('[data-testid="tenant-filter"]', 'e2e_tenant');
  await page.click('[data-testid="search-button"]');
  
  await expect(page.getByText('e2e@example.com')).toBeVisible();
  await expect(page.getByText(submissionData.submission_id)).toBeVisible();
});
```

## Phase-Based Implementation

### Phase 1: Core Infrastructure Testing (Weeks 1-2)

**Priority**: Foundation components that everything depends on

#### 1.1 DynamoDB Operations Testing

**Coverage Goal**: 95%

```python
# conftest.py - Pytest fixtures
@pytest.fixture(scope="session")
def localstack_container():
    """Start LocalStack container for testing"""
    container = DockerContainer("localstack/localstack:latest")
    container.with_env("SERVICES", "dynamodb,s3,secretsmanager,events")
    container.with_env("DEBUG", "1")
    container.with_exposed_ports(4566)
    container.start()
    
    yield container
    container.stop()

@pytest.fixture
def dynamodb_resource(localstack_container):
    """Create DynamoDB resource pointing to LocalStack"""
    endpoint_url = f"http://localhost:{localstack_container.get_exposed_port(4566)}"
    return boto3.resource('dynamodb', 
                         endpoint_url=endpoint_url,
                         aws_access_key_id='test',
                         aws_secret_access_key='test',
                         region_name='us-east-1')

@pytest.fixture
def submissions_table(dynamodb_resource):
    """Create submissions table for testing"""
    table = dynamodb_resource.create_table(
        TableName='form-bridge-submissions-test',
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'},
            {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
            {'AttributeName': 'GSI1SK', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'GSI1',
            'KeySchema': [
                {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
            ],
            'Projection': {'ProjectionType': 'ALL'}
        }],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Wait for table to be ready
    table.wait_until_exists()
    yield table
    table.delete()
```

**Critical Test Cases**:
```python
def test_submission_storage_and_retrieval(submissions_table):
    """Test basic submission CRUD operations"""
    tenant_id = "test_tenant"
    submission_id = "01J7R3S8B2JD2VEXAMPLE"
    
    # Store submission
    item = {
        'PK': f'TENANT#{tenant_id}',
        'SK': f'SUB#{submission_id}',
        'GSI1PK': f'TENANT#{tenant_id}',
        'GSI1SK': f'TS#{datetime.utcnow().isoformat()}',
        'payload': {'email': 'test@example.com', 'name': 'Test User'},
        'status': 'received',
        'source': 'wordpress'
    }
    
    submissions_table.put_item(Item=item)
    
    # Retrieve by primary key
    response = submissions_table.get_item(
        Key={'PK': f'TENANT#{tenant_id}', 'SK': f'SUB#{submission_id}'}
    )
    
    assert 'Item' in response
    assert response['Item']['payload']['email'] == 'test@example.com'

def test_tenant_isolation(submissions_table):
    """Verify tenant data isolation"""
    # Add data for two different tenants
    submissions_table.put_item(Item={
        'PK': 'TENANT#tenant1',
        'SK': 'SUB#sub1',
        'GSI1PK': 'TENANT#tenant1',
        'GSI1SK': 'TS#2025-08-26T10:00:00Z',
        'payload': {'secret': 'tenant1_data'}
    })
    
    submissions_table.put_item(Item={
        'PK': 'TENANT#tenant2', 
        'SK': 'SUB#sub2',
        'GSI1PK': 'TENANT#tenant2',
        'GSI1SK': 'TS#2025-08-26T11:00:00Z',
        'payload': {'secret': 'tenant2_data'}
    })
    
    # Query tenant1 data
    response = submissions_table.query(
        IndexName='GSI1',
        KeyConditionExpression=Key('GSI1PK').eq('TENANT#tenant1')
    )
    
    assert len(response['Items']) == 1
    assert response['Items'][0]['payload']['secret'] == 'tenant1_data'
    
    # Ensure tenant2 data is not returned
    for item in response['Items']:
        assert 'tenant2_data' not in str(item)
```

#### 1.2 Lambda Handler Testing

**Coverage Goal**: 85%

```python
# test_lambda_handlers.py
import json
import pytest
from moto import mock_dynamodb, mock_secretsmanager
from lambdas.ingest.handler import lambda_handler as ingest_handler
from lambdas.persist.handler import lambda_handler as persist_handler

@mock_dynamodb
@mock_secretsmanager
def test_ingest_lambda_valid_request():
    """Test ingest lambda with valid HMAC authenticated request"""
    
    # Mock event from API Gateway
    event = {
        'httpMethod': 'POST',
        'headers': {
            'X-Tenant-Id': 'test_tenant',
            'X-Timestamp': '2025-08-26T10:00:00Z',
            'X-Signature': 'valid_signature_here',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'name': 'John Doe',
            'email': 'john@example.com',
            'message': 'Test submission'
        }),
        'requestContext': {
            'authorizer': {
                'lambda': {
                    'tenant_id': 'test_tenant'
                }
            }
        }
    }
    
    # Mock context
    class MockContext:
        aws_request_id = 'test-request-id'
        function_name = 'test-function'
    
    context = MockContext()
    
    # Call handler
    response = ingest_handler(event, context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'submission_id' in body
    assert body['ok'] == True

@mock_dynamodb
def test_persist_lambda_eventbridge_event():
    """Test persist lambda processing EventBridge event"""
    
    # Mock EventBridge event
    event = {
        'detail': {
            'tenant_id': 'test_tenant',
            'submission_id': '01J7R3S8B2JD2VEXAMPLE',
            'payload': {
                'name': 'Jane Doe',
                'email': 'jane@example.com'
            },
            'submitted_at': '2025-08-26T10:00:00Z',
            'source': 'wordpress'
        }
    }
    
    response = persist_handler(event, MockContext())
    
    assert response['statusCode'] == 200
```

#### 1.3 EventBridge Routing Testing

**Coverage Goal**: 100%

```python
# test_eventbridge_routing.py
@pytest.fixture
def eventbridge_client(localstack_container):
    endpoint_url = f"http://localhost:{localstack_container.get_exposed_port(4566)}"
    return boto3.client('events',
                       endpoint_url=endpoint_url,
                       aws_access_key_id='test',
                       aws_secret_access_key='test',
                       region_name='us-east-1')

def test_event_bus_rules_routing(eventbridge_client):
    """Test EventBridge rules route events correctly"""
    
    # Create custom event bus
    bus_name = 'form-bus-test'
    eventbridge_client.create_event_bus(Name=bus_name)
    
    # Create rules for testing
    persist_rule = {
        'Name': 'PersistRule',
        'EventPattern': json.dumps({
            'detail-type': ['submission.received'],
            'source': ['ingest']
        }),
        'State': 'ENABLED',
        'EventBusName': bus_name
    }
    
    eventbridge_client.put_rule(**persist_rule)
    
    # Test event matches rule pattern
    test_event = {
        'Source': 'ingest',
        'DetailType': 'submission.received',
        'Detail': json.dumps({
            'tenant_id': 'test_tenant',
            'submission_id': '01J7R3S8B2JD2VEXAMPLE'
        }),
        'EventBusName': bus_name
    }
    
    response = eventbridge_client.put_events(Entries=[test_event])
    
    assert response['FailedEntryCount'] == 0
    assert len(response['Entries']) == 1
```

#### 1.4 Authentication System Testing

**Coverage Goal**: 100%

```python
# test_authentication.py
import hmac
import hashlib
import time
from datetime import datetime, timezone

def test_hmac_signature_generation():
    """Test HMAC signature generation matches expected format"""
    secret = "test_secret_key"
    timestamp = "2025-08-26T10:00:00Z"
    body = '{"email": "test@example.com"}'
    
    expected_payload = f"{timestamp}\n{body}"
    expected_signature = hmac.new(
        secret.encode(),
        expected_payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    actual_signature = generate_hmac_signature(secret, timestamp, body)
    
    assert actual_signature == expected_signature

def test_timestamp_replay_protection():
    """Test timestamp validation prevents replay attacks"""
    secret = "test_secret_key"
    body = '{"email": "test@example.com"}'
    
    # Test valid timestamp (within 5 minute window)
    current_time = datetime.now(timezone.utc)
    valid_timestamp = current_time.isoformat().replace('+00:00', 'Z')
    valid_signature = generate_hmac_signature(secret, valid_timestamp, body)
    
    assert validate_hmac_signature(secret, valid_timestamp, body, valid_signature) == True
    
    # Test stale timestamp (older than 5 minutes)
    stale_time = current_time - timedelta(minutes=6)
    stale_timestamp = stale_time.isoformat().replace('+00:00', 'Z')
    stale_signature = generate_hmac_signature(secret, stale_timestamp, body)
    
    assert validate_hmac_signature(secret, stale_timestamp, body, stale_signature) == False

def test_tenant_secret_isolation():
    """Test different tenants have different secrets"""
    body = '{"email": "test@example.com"}'
    timestamp = "2025-08-26T10:00:00Z"
    
    tenant1_secret = "tenant1_secret"
    tenant2_secret = "tenant2_secret"
    
    tenant1_signature = generate_hmac_signature(tenant1_secret, timestamp, body)
    tenant2_signature = generate_hmac_signature(tenant2_secret, timestamp, body)
    
    # Signatures should be different
    assert tenant1_signature != tenant2_signature
    
    # Cross-tenant validation should fail
    assert validate_hmac_signature(tenant1_secret, timestamp, body, tenant2_signature) == False
```

### Phase 2: WordPress Integration Testing (Weeks 3-4)

**Priority**: Plugin functionality, HMAC implementation, auto-update mechanism

#### 2.1 WordPress Plugin Testing

**Coverage Goal**: 80%

```php
<?php
// tests/test-plugin-auth.php (PHPUnit)
class PluginAuthTest extends WP_UnitTestCase {
    
    public function test_hmac_signature_generation() {
        $secret = 'test_secret_key';
        $timestamp = '2025-08-26T10:00:00Z';
        $body = json_encode(['email' => 'test@example.com']);
        
        $signature = FormBridge_Auth::generate_hmac_signature($secret, $timestamp, $body);
        
        $expected_payload = $timestamp . "\n" . $body;
        $expected_signature = hash_hmac('sha256', $expected_payload, $secret);
        
        $this->assertEquals($expected_signature, $signature);
    }
    
    public function test_form_submission_integration() {
        // Mock WordPress form submission
        $_POST['form_data'] = json_encode([
            'name' => 'Test User',
            'email' => 'test@example.com',
            'message' => 'Test message'
        ]);
        
        // Mock successful API response
        add_filter('pre_http_request', function($preempt, $parsed_args, $url) {
            if (strpos($url, 'form-bridge') !== false) {
                return [
                    'response' => ['code' => 200],
                    'body' => json_encode(['ok' => true, 'submission_id' => 'test123'])
                ];
            }
            return $preempt;
        }, 10, 3);
        
        $result = FormBridge_Submission::send_to_api($_POST['form_data']);
        
        $this->assertTrue($result['success']);
        $this->assertArrayHasKey('submission_id', $result);
    }
    
    public function test_rate_limiting() {
        // Simulate multiple rapid submissions
        for ($i = 0; $i < 5; $i++) {
            $result = FormBridge_Submission::send_to_api([
                'email' => "test{$i}@example.com"
            ]);
        }
        
        // 6th submission should be rate limited
        $result = FormBridge_Submission::send_to_api([
            'email' => 'test6@example.com'
        ]);
        
        $this->assertFalse($result['success']);
        $this->assertStringContainsString('rate limit', $result['error']);
    }
}
```

#### 2.2 Auto-Update Mechanism Testing

**Coverage Goal**: 90%

```php
<?php
// tests/test-auto-update.php
class AutoUpdateTest extends WP_UnitTestCase {
    
    public function test_version_check() {
        // Mock API response with newer version
        add_filter('pre_http_request', function($preempt, $parsed_args, $url) {
            if (strpos($url, '/updates/check') !== false) {
                return [
                    'response' => ['code' => 200],
                    'body' => json_encode([
                        'version' => '1.2.0',
                        'download_url' => 'https://api.form-bridge.com/download/1.2.0',
                        'requires_php' => '7.4',
                        'requires_wp' => '5.0'
                    ])
                ];
            }
            return $preempt;
        }, 10, 3);
        
        $update_info = FormBridge_Updater::check_for_updates();
        
        $this->assertEquals('1.2.0', $update_info['version']);
        $this->assertNotEmpty($update_info['download_url']);
    }
    
    public function test_secure_download_verification() {
        $plugin_zip = '/tmp/test-plugin.zip';
        $signature = 'expected_signature_here';
        
        // Create mock plugin zip file
        file_put_contents($plugin_zip, 'mock zip content');
        
        $is_valid = FormBridge_Updater::verify_download_signature($plugin_zip, $signature);
        
        $this->assertTrue($is_valid);
        unlink($plugin_zip);
    }
}
```

### Phase 3: React Dashboard Testing (Weeks 5-6)

**Priority**: Component testing, API integration, user workflows

#### 3.1 React Component Testing

**Coverage Goal**: 70%

```javascript
// src/components/__tests__/SubmissionsList.test.js
import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import SubmissionsList from '../SubmissionsList';
import { QueryClient, QueryClientProvider } from 'react-query';

const server = setupServer(
  rest.get('/api/submissions', (req, res, ctx) => {
    const tenantId = req.url.searchParams.get('tenant_id');
    const since = req.url.searchParams.get('since');
    
    return res(ctx.json({
      items: [
        {
          submission_id: '01J7R3S8B2JD2VEXAMPLE',
          tenant_id: tenantId,
          submitted_at: '2025-08-26T10:00:00Z',
          payload: {
            name: 'John Doe',
            email: 'john@example.com',
            message: 'Test submission'
          },
          source: 'wordpress'
        }
      ],
      next_cursor: null
    }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

test('displays submissions for selected tenant', async () => {
  const user = userEvent.setup();
  render(<SubmissionsList />, { wrapper: createWrapper() });
  
  // Select tenant
  const tenantSelect = screen.getByLabelText(/tenant/i);
  await user.selectOptions(tenantSelect, 'test_tenant');
  
  // Click search
  await user.click(screen.getByRole('button', { name: /search/i }));
  
  // Wait for submissions to load
  await waitFor(() => {
    expect(screen.getByText('john@example.com')).toBeInTheDocument();
  });
  
  // Verify submission details
  const submissionRow = screen.getByTestId('submission-01J7R3S8B2JD2VEXAMPLE');
  expect(within(submissionRow).getByText('John Doe')).toBeInTheDocument();
  expect(within(submissionRow).getByText('wordpress')).toBeInTheDocument();
});

test('handles API errors gracefully', async () => {
  // Override server to return error
  server.use(
    rest.get('/api/submissions', (req, res, ctx) => {
      return res(ctx.status(500), ctx.json({ error: 'Internal server error' }));
    })
  );
  
  const user = userEvent.setup();
  render(<SubmissionsList />, { wrapper: createWrapper() });
  
  const tenantSelect = screen.getByLabelText(/tenant/i);
  await user.selectOptions(tenantSelect, 'test_tenant');
  await user.click(screen.getByRole('button', { name: /search/i }));
  
  await waitFor(() => {
    expect(screen.getByText(/error loading/i)).toBeInTheDocument();
  });
});

test('pagination works correctly', async () => {
  // Mock API with pagination
  server.use(
    rest.get('/api/submissions', (req, res, ctx) => {
      const cursor = req.url.searchParams.get('cursor');
      
      if (!cursor) {
        // First page
        return res(ctx.json({
          items: Array.from({length: 50}, (_, i) => ({
            submission_id: `sub${i}`,
            tenant_id: 'test_tenant',
            payload: { email: `user${i}@example.com` }
          })),
          next_cursor: 'cursor_page_2'
        }));
      } else {
        // Second page
        return res(ctx.json({
          items: Array.from({length: 25}, (_, i) => ({
            submission_id: `sub${i + 50}`,
            tenant_id: 'test_tenant',
            payload: { email: `user${i + 50}@example.com` }
          })),
          next_cursor: null
        }));
      }
    })
  );
  
  const user = userEvent.setup();
  render(<SubmissionsList />, { wrapper: createWrapper() });
  
  // Load first page
  await user.selectOptions(screen.getByLabelText(/tenant/i), 'test_tenant');
  await user.click(screen.getByRole('button', { name: /search/i }));
  
  await waitFor(() => {
    expect(screen.getByText('user0@example.com')).toBeInTheDocument();
  });
  
  // Click next page
  await user.click(screen.getByRole('button', { name: /next/i }));
  
  await waitFor(() => {
    expect(screen.getByText('user50@example.com')).toBeInTheDocument();
  });
});
```

#### 3.2 State Management Testing

**Coverage Goal**: 80%

```javascript
// src/store/__tests__/submissionsStore.test.js
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from 'react-query';
import { useSubmissionsStore } from '../submissionsStore';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

test('manages filter state correctly', () => {
  const { result } = renderHook(() => useSubmissionsStore(), {
    wrapper: createWrapper()
  });
  
  // Initial state
  expect(result.current.filters.tenant_id).toBe('');
  expect(result.current.filters.since).toBe('');
  
  // Update filters
  act(() => {
    result.current.setFilter('tenant_id', 'test_tenant');
    result.current.setFilter('since', '2025-01-01');
  });
  
  expect(result.current.filters.tenant_id).toBe('test_tenant');
  expect(result.current.filters.since).toBe('2025-01-01');
});

test('resets filters correctly', () => {
  const { result } = renderHook(() => useSubmissionsStore(), {
    wrapper: createWrapper()
  });
  
  // Set some filters
  act(() => {
    result.current.setFilter('tenant_id', 'test_tenant');
    result.current.setFilter('form_id', 'contact_form');
  });
  
  // Reset filters
  act(() => {
    result.current.resetFilters();
  });
  
  expect(result.current.filters.tenant_id).toBe('');
  expect(result.current.filters.form_id).toBe('');
});
```

## Test Infrastructure Setup

### Docker Compose Configuration

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=dynamodb,s3,secretsmanager,events,stepfunctions,lambda
      - DEBUG=1
      - DATA_DIR=/tmp/localstack/data
      - LAMBDA_EXECUTOR=docker
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - "/tmp/localstack:/tmp/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
    networks:
      - form-bridge-test

  test-runner:
    build:
      context: .
      dockerfile: Dockerfile.test
    depends_on:
      - localstack
    environment:
      - AWS_ENDPOINT_URL=http://localstack:4566
      - AWS_ACCESS_KEY_ID=test
      - AWS_SECRET_ACCESS_KEY=test
      - AWS_DEFAULT_REGION=us-east-1
    volumes:
      - .:/app
      - /app/node_modules
      - /app/.venv
    working_dir: /app
    networks:
      - form-bridge-test
    command: >
      sh -c "
        pip install -r requirements-test.txt &&
        npm install &&
        pytest tests/ --cov=lambdas --cov-report=html &&
        npm run test:coverage
      "

  wordpress-test:
    image: wordpress:php8.1-apache
    depends_on:
      - mysql-test
    environment:
      - WORDPRESS_DB_HOST=mysql-test
      - WORDPRESS_DB_NAME=wordpress_test
      - WORDPRESS_DB_USER=root
      - WORDPRESS_DB_PASSWORD=test123
    ports:
      - "8080:80"
    volumes:
      - ./wordpress-plugin:/var/www/html/wp-content/plugins/form-bridge
    networks:
      - form-bridge-test

  mysql-test:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=test123
      - MYSQL_DATABASE=wordpress_test
    networks:
      - form-bridge-test

networks:
  form-bridge-test:
    driver: bridge
```

### Test Dockerfile

```dockerfile
# Dockerfile.test
FROM python:3.12-slim

# Install Node.js for React testing
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Install Docker for LocalStack Lambda execution
RUN apt-get update && apt-get install -y \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-test.txt /tmp/
RUN pip install -r /tmp/requirements-test.txt

# Install AWS CLI for integration tests
RUN pip install awscli

WORKDIR /app

# Install npm dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Set up Python path
ENV PYTHONPATH=/app

CMD ["pytest", "tests/", "--cov=lambdas", "--cov-report=html"]
```

### CI/CD Pipeline Configuration

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.12]
        node-version: [20]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Set up Node.js ${{ matrix.node-version }}
      uses: actions/setup-node@v4
      with:
        node-version: ${{ matrix.node-version }}
        cache: 'npm'
    
    - name: Cache Python dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements-test.txt') }}
    
    - name: Install Python dependencies
      run: |
        pip install -r requirements-test.txt
    
    - name: Install Node.js dependencies
      run: npm ci
    
    - name: Run Python unit tests
      run: |
        pytest tests/unit/ --cov=lambdas --cov-report=xml --cov-fail-under=80
    
    - name: Run React unit tests
      run: |
        npm run test:coverage -- --watchAll=false
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml,./coverage/lcov.info
        fail_ci_if_error: true

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Build test environment
      run: |
        docker-compose -f docker-compose.test.yml build
    
    - name: Run integration tests
      run: |
        docker-compose -f docker-compose.test.yml up --abort-on-container-exit
    
    - name: Collect test results
      run: |
        docker-compose -f docker-compose.test.yml logs test-runner
    
    - name: Cleanup
      if: always()
      run: |
        docker-compose -f docker-compose.test.yml down -v

  security-tests:
    runs-on: ubuntu-latest
    needs: unit-tests

    steps:
    - uses: actions/checkout@v4
    
    - name: Run Snyk security scan
      uses: snyk/actions/python@master
      env:
        SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      with:
        args: --severity-threshold=high
    
    - name: Run npm audit
      run: npm audit --audit-level=moderate

  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: 'npm'
    
    - name: Install dependencies
      run: npm ci
    
    - name: Install Playwright
      run: npx playwright install --with-deps chromium
    
    - name: Start test environment
      run: |
        docker-compose -f docker-compose.test.yml up -d localstack wordpress-test
        sleep 30  # Wait for services to start
    
    - name: Run Playwright tests
      run: |
        npx playwright test --reporter=html
      env:
        BASE_URL: http://localhost:3000
        API_URL: http://localhost:4566
    
    - name: Upload Playwright report
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: playwright-report
        path: playwright-report/
        retention-days: 7
```

## Performance Benchmarking

### Load Testing with k6

```javascript
// tests/load/submission-load-test.js
import http from 'k6/http';
import crypto from 'k6/crypto';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const submissionDuration = new Trend('submission_duration');

export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'],
    errors: ['rate<0.1'],
    submission_duration: ['p(95)<500'],
  },
};

const API_ENDPOINT = __ENV.API_ENDPOINT || 'https://api.form-bridge.com';
const TENANT_SECRET = __ENV.TENANT_SECRET || 'test_secret';

function generateHMAC(secret, timestamp, body) {
  const payload = timestamp + '\n' + body;
  return crypto.hmac('sha256', secret, payload, 'hex');
}

export default function () {
  const timestamp = new Date().toISOString();
  const body = JSON.stringify({
    name: `Test User ${__VU}-${__ITER}`,
    email: `user${__VU}${__ITER}@example.com`,
    message: 'Load test submission',
    form_id: 'contact_us'
  });
  
  const signature = generateHMAC(TENANT_SECRET, timestamp, body);
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-Id': 'load_test_tenant',
      'X-Timestamp': timestamp,
      'X-Signature': signature,
    },
  };
  
  const start = Date.now();
  const response = http.post(`${API_ENDPOINT}/ingest`, body, params);
  const duration = Date.now() - start;
  
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'has submission_id': (r) => JSON.parse(r.body).submission_id !== undefined,
    'response time < 200ms': () => duration < 200,
  });
  
  errorRate.add(!success);
  submissionDuration.add(duration);
  
  sleep(1); // 1 second between requests
}
```

### Memory and Performance Profiling

```python
# tests/performance/lambda_profiling.py
import memory_profiler
import time
import json
from lambdas.ingest.handler import lambda_handler

@memory_profiler.profile
def profile_ingest_lambda():
    """Profile memory usage of ingest lambda"""
    
    # Simulate API Gateway event
    event = {
        'httpMethod': 'POST',
        'headers': {
            'X-Tenant-Id': 'perf_test_tenant',
            'X-Timestamp': '2025-08-26T10:00:00Z',
            'X-Signature': 'test_signature',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'name': 'Performance Test User',
            'email': 'perf@example.com',
            'message': 'Large message content ' * 100  # Simulate larger payload
        }),
        'requestContext': {
            'authorizer': {
                'lambda': {
                    'tenant_id': 'perf_test_tenant'
                }
            }
        }
    }
    
    class MockContext:
        aws_request_id = 'perf-test-request'
        function_name = 'perf-test-function'
    
    # Time the lambda execution
    start_time = time.time()
    response = lambda_handler(event, MockContext())
    execution_time = time.time() - start_time
    
    print(f"Lambda execution time: {execution_time:.3f} seconds")
    print(f"Response status: {response['statusCode']}")
    
    return execution_time

def test_cold_start_performance():
    """Test lambda cold start times"""
    import subprocess
    import tempfile
    
    # Create temporary lambda deployment package
    with tempfile.TemporaryDirectory() as temp_dir:
        # Package lambda
        package_cmd = f"cd lambdas/ingest && zip -r {temp_dir}/function.zip ."
        subprocess.run(package_cmd, shell=True, check=True)
        
        # Deploy to AWS (or LocalStack)
        # ... deployment code ...
        
        # Invoke lambda multiple times to test cold starts
        cold_start_times = []
        for i in range(5):
            start = time.time()
            # Invoke lambda
            # ... invocation code ...
            cold_start_times.append(time.time() - start)
            time.sleep(60)  # Wait for lambda to go cold
        
        avg_cold_start = sum(cold_start_times) / len(cold_start_times)
        assert avg_cold_start < 1.0, f"Average cold start {avg_cold_start:.3f}s exceeds 1s threshold"

if __name__ == '__main__':
    # Profile memory usage
    execution_time = profile_ingest_lambda()
    
    # Test cold start performance
    test_cold_start_performance()
```

## Security Testing

### OWASP ZAP Integration

```yaml
# .github/workflows/security-scan.yml
name: Security Scan

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  security-scan:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Start test environment
      run: |
        docker-compose -f docker-compose.test.yml up -d
        sleep 60
    
    - name: Run OWASP ZAP scan
      uses: zaproxy/action-baseline@v0.7.0
      with:
        target: 'http://localhost:3000'
        rules_file_name: '.zap/rules.tsv'
        cmd_options: '-a'
    
    - name: Upload ZAP report
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: zap-report
        path: report_html.html
```

### Penetration Testing Scenarios

```python
# tests/security/penetration_tests.py
import requests
import json
import hmac
import hashlib
from datetime import datetime, timedelta

class SecurityTests:
    def __init__(self, api_endpoint, tenant_secret):
        self.api_endpoint = api_endpoint
        self.tenant_secret = tenant_secret
    
    def test_sql_injection_attempts(self):
        """Test for SQL injection vulnerabilities"""
        sql_payloads = [
            "'; DROP TABLE submissions; --",
            "' OR '1'='1",
            "'; SELECT * FROM submissions WHERE tenant_id = 'other_tenant'; --"
        ]
        
        for payload in sql_payloads:
            timestamp = datetime.utcnow().isoformat() + 'Z'
            body = json.dumps({
                'name': payload,
                'email': 'test@example.com',
                'message': 'Test'
            })
            
            signature = self._generate_signature(timestamp, body)
            
            response = requests.post(f'{self.api_endpoint}/ingest', 
                headers={
                    'X-Tenant-Id': 'test_tenant',
                    'X-Timestamp': timestamp,
                    'X-Signature': signature,
                    'Content-Type': 'application/json'
                },
                data=body
            )
            
            # Should not expose SQL errors
            assert response.status_code in [200, 400]
            assert 'SQL' not in response.text.upper()
            assert 'ERROR' not in response.text.upper()
    
    def test_xss_attempts(self):
        """Test for XSS vulnerabilities"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src='x' onerror='alert(1)'>"
        ]
        
        for payload in xss_payloads:
            timestamp = datetime.utcnow().isoformat() + 'Z'
            body = json.dumps({
                'name': 'Test User',
                'email': 'test@example.com',
                'message': payload
            })
            
            signature = self._generate_signature(timestamp, body)
            
            response = requests.post(f'{self.api_endpoint}/ingest',
                headers={
                    'X-Tenant-Id': 'test_tenant',
                    'X-Timestamp': timestamp,
                    'X-Signature': signature,
                    'Content-Type': 'application/json'
                },
                data=body
            )
            
            assert response.status_code == 200
            
            # Check if data is properly sanitized in dashboard
            dashboard_response = requests.get(f'{self.api_endpoint}/submissions',
                params={'tenant_id': 'test_tenant'},
                headers={'Authorization': 'Bearer valid_jwt_token'}
            )
            
            # Should not contain unescaped script tags
            assert '<script>' not in dashboard_response.text
    
    def test_replay_attack_prevention(self):
        """Test HMAC replay attack prevention"""
        # Create valid request
        timestamp = datetime.utcnow().isoformat() + 'Z'
        body = json.dumps({
            'name': 'Test User',
            'email': 'test@example.com',
            'message': 'Test message'
        })
        signature = self._generate_signature(timestamp, body)
        
        # First request should succeed
        response1 = requests.post(f'{self.api_endpoint}/ingest',
            headers={
                'X-Tenant-Id': 'test_tenant',
                'X-Timestamp': timestamp,
                'X-Signature': signature,
                'Content-Type': 'application/json'
            },
            data=body
        )
        assert response1.status_code == 200
        
        # Same request should be rejected (replay attack)
        response2 = requests.post(f'{self.api_endpoint}/ingest',
            headers={
                'X-Tenant-Id': 'test_tenant',
                'X-Timestamp': timestamp,
                'X-Signature': signature,
                'Content-Type': 'application/json'
            },
            data=body
        )
        
        # Should implement nonce or other replay prevention
        # For now, test that stale timestamp is rejected
        old_timestamp = (datetime.utcnow() - timedelta(minutes=10)).isoformat() + 'Z'
        old_signature = self._generate_signature(old_timestamp, body)
        
        response3 = requests.post(f'{self.api_endpoint}/ingest',
            headers={
                'X-Tenant-Id': 'test_tenant',
                'X-Timestamp': old_timestamp,
                'X-Signature': old_signature,
                'Content-Type': 'application/json'
            },
            data=body
        )
        
        assert response3.status_code == 401  # Unauthorized due to stale timestamp
    
    def test_tenant_isolation(self):
        """Test multi-tenant data isolation"""
        # Submit data for tenant A
        timestamp = datetime.utcnow().isoformat() + 'Z'
        body = json.dumps({
            'name': 'Tenant A User',
            'email': 'tenantA@example.com',
            'secret_data': 'tenant_a_secret'
        })
        signature = self._generate_signature(timestamp, body)
        
        requests.post(f'{self.api_endpoint}/ingest',
            headers={
                'X-Tenant-Id': 'tenant_a',
                'X-Timestamp': timestamp,
                'X-Signature': signature,
                'Content-Type': 'application/json'
            },
            data=body
        )
        
        # Try to access data as tenant B
        dashboard_response = requests.get(f'{self.api_endpoint}/submissions',
            params={'tenant_id': 'tenant_b'},  # Different tenant
            headers={'Authorization': 'Bearer tenant_b_jwt_token'}
        )
        
        # Should not see tenant A's data
        assert 'tenant_a_secret' not in dashboard_response.text
        assert 'tenantA@example.com' not in dashboard_response.text
    
    def _generate_signature(self, timestamp, body):
        """Generate HMAC signature for testing"""
        payload = f"{timestamp}\n{body}"
        return hmac.new(
            self.tenant_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

# Run security tests
if __name__ == '__main__':
    security_tests = SecurityTests(
        api_endpoint='http://localhost:4566',
        tenant_secret='test_secret_key'
    )
    
    security_tests.test_sql_injection_attempts()
    security_tests.test_xss_attempts()
    security_tests.test_replay_attack_prevention()
    security_tests.test_tenant_isolation()
    
    print("All security tests passed!")
```

## Cost Analysis and Timeline

### Testing Infrastructure Costs

| Component | Monthly Cost | Annual Cost | Notes |
|-----------|--------------|-------------|-------|
| LocalStack Pro | $0 | $0 | Using community edition |
| GitHub Actions | $0 | $0 | 2,000 minutes/month free tier |
| Docker Hub | $0 | $0 | Public repositories |
| Codecov | $0 | $0 | Open source plan |
| Playwright | $0 | $0 | Self-hosted runners |
| **Total** | **$0** | **$0** | **Optimized for cost** |

**Production Testing Costs:**
- AWS resources for staging tests: ~$10/month
- Third-party security scanning (Snyk): ~$10/month  
- Performance monitoring (if external): ~$5/month
- **Total Production**: **$25/month** ($300/year)

### Implementation Timeline

| Phase | Duration | Deliverables | Resources Needed |
|-------|----------|--------------|------------------|
| **Phase 1: Core Infrastructure** | 2 weeks | <ul><li>LocalStack setup</li><li>DynamoDB test suite</li><li>Lambda test framework</li><li>EventBridge integration tests</li><li>HMAC authentication tests</li></ul> | 1 QA Engineer, 1 DevOps Support |
| **Phase 2: WordPress Integration** | 2 weeks | <ul><li>WordPress PHPUnit tests</li><li>Plugin integration tests</li><li>Auto-update testing</li><li>Rate limiting validation</li></ul> | 1 QA Engineer, 1 WordPress Developer |
| **Phase 3: React Dashboard** | 2 weeks | <ul><li>React component tests</li><li>API integration tests</li><li>E2E Playwright tests</li><li>Performance benchmarks</li></ul> | 1 QA Engineer, 1 Frontend Developer |

### Success Metrics and KPIs

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| **Test Coverage** | 0% | 80% | Code coverage reports |
| **Critical Path Coverage** | 0% | 100% | Manual audit |
| **Test Execution Time** | N/A | <5 min | CI/CD pipeline timing |
| **False Positive Rate** | N/A | <2% | Test reliability tracking |
| **Security Scan Score** | N/A | >8.5/10 | OWASP ZAP scoring |
| **Performance SLA** | N/A | <200ms p99 | Load testing results |
| **Bug Detection Time** | N/A | <1 hour | Monitoring alerts |

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Create comprehensive TDD plan document with testing pyramid, phase-based approach, and specific test examples", "activeForm": "Creating comprehensive TDD plan document", "status": "completed"}, {"content": "Design Docker-based test infrastructure with LocalStack integration", "activeForm": "Designing Docker test infrastructure", "status": "completed"}, {"content": "Create specific test examples for each component (Lambda, DynamoDB, EventBridge, WordPress, React)", "activeForm": "Creating component-specific test examples", "status": "completed"}, {"content": "Define CI/CD pipeline tests and performance benchmarks", "activeForm": "Defining CI/CD pipeline tests", "status": "completed"}, {"content": "Calculate cost considerations and provide implementation timeline", "activeForm": "Calculating costs and timeline", "status": "completed"}]
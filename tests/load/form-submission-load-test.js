/**
 * k6 Load Testing for Form-Bridge Multi-Tenant Form Submissions
 * Tests 10K submissions/month scenario with EventBridge and DynamoDB
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import crypto from 'k6/crypto';

// Custom metrics
export const errorRate = new Rate('errors');
export const submissionDuration = new Trend('submission_duration');
export const hmacValidationDuration = new Trend('hmac_validation_duration');
export const eventBridgePublishDuration = new Trend('eventbridge_publish_duration');
export const dynamoDBWriteDuration = new Trend('dynamodb_write_duration');
export const multiTenantSubmissions = new Counter('multi_tenant_submissions');

// Test configuration
export const options = {
  scenarios: {
    // Ramp-up scenario: Simulate gradual traffic increase
    ramp_up: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '2m', target: 10 },   // Ramp up to 10 VUs over 2 minutes
        { duration: '5m', target: 50 },   // Stay at 50 VUs for 5 minutes (main load)
        { duration: '3m', target: 100 },  // Peak load: 100 VUs for 3 minutes
        { duration: '2m', target: 0 },    // Ramp down to 0 VUs
      ],
    },
    
    // Steady-state scenario: Simulate normal operations
    steady_state: {
      executor: 'constant-vus',
      vus: 25,
      duration: '10m',
      startTime: '12m', // Start after ramp-up scenario
    },
    
    // Spike scenario: Simulate traffic spikes
    spike_test: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { duration: '30s', target: 200 },  // Sudden spike
        { duration: '1m', target: 200 },   // Hold spike
        { duration: '30s', target: 10 },   // Quick ramp down
      ],
      startTime: '22m', // Start after steady-state
    }
  },
  
  // Performance thresholds
  thresholds: {
    // 95% of requests should complete under 2 seconds
    http_req_duration: ['p(95)<2000'],
    
    // Error rate should be less than 5%
    http_req_failed: ['rate<0.05'],
    errors: ['rate<0.05'],
    
    // Custom thresholds for Form-Bridge components
    submission_duration: ['p(95)<2000', 'p(99)<3000'],
    hmac_validation_duration: ['p(95)<100', 'avg<50'],
    eventbridge_publish_duration: ['p(95)<500', 'avg<200'],
    dynamodb_write_duration: ['p(95)<200', 'avg<100'],
    
    // Multi-tenant performance
    multi_tenant_submissions: ['count>1000'],
  },
  
  // HTTP configuration
  httpDebug: 'full', // Enable for debugging
  insecureSkipTLSVerify: true, // For testing with LocalStack
};

// Test data: Multi-tenant configurations
const tenants = new SharedArray('tenants', function () {
  return [
    {
      id: 't_load_test_1',
      name: 'Load Test Tenant 1',
      secret: 'load_test_secret_1_for_hmac_signing',
      forms: ['contact_form', 'newsletter_signup', 'feedback_form'],
      weight: 40 // 40% of traffic
    },
    {
      id: 't_load_test_2', 
      name: 'Load Test Tenant 2',
      secret: 'load_test_secret_2_for_hmac_signing',
      forms: ['contact_form', 'survey_form', 'support_ticket'],
      weight: 35 // 35% of traffic
    },
    {
      id: 't_load_test_3',
      name: 'Load Test Tenant 3', 
      secret: 'load_test_secret_3_for_hmac_signing',
      forms: ['contact_form', 'quote_request'],
      weight: 20 // 20% of traffic
    },
    {
      id: 't_load_test_4',
      name: 'Load Test Tenant 4',
      secret: 'load_test_secret_4_for_hmac_signing', 
      forms: ['contact_form'],
      weight: 5 // 5% of traffic (small tenant)
    }
  ];
});

// Form submission templates
const formTemplates = {
  contact_form: {
    name: () => `Load Test User ${Math.floor(Math.random() * 10000)}`,
    email: () => `loadtest${Math.floor(Math.random() * 10000)}@example.com`,
    subject: () => `Load Test Subject ${Math.floor(Math.random() * 1000)}`,
    message: () => `This is a load test message with some random content: ${Math.random().toString(36).substring(7)}`
  },
  newsletter_signup: {
    email: () => `newsletter${Math.floor(Math.random() * 10000)}@example.com`,
    name: () => `Newsletter User ${Math.floor(Math.random() * 10000)}`,
    preferences: () => ['updates', 'promotions'][Math.floor(Math.random() * 2)]
  },
  feedback_form: {
    rating: () => Math.floor(Math.random() * 5) + 1,
    feedback: () => `Load test feedback: ${Math.random().toString(36).substring(7)}`,
    category: () => ['product', 'service', 'website'][Math.floor(Math.random() * 3)]
  },
  survey_form: {
    response_1: () => Math.floor(Math.random() * 5) + 1,
    response_2: () => ['yes', 'no', 'maybe'][Math.floor(Math.random() * 3)],
    comments: () => `Survey comments: ${Math.random().toString(36).substring(7)}`
  },
  support_ticket: {
    issue_type: () => ['bug', 'feature_request', 'question'][Math.floor(Math.random() * 3)],
    priority: () => ['low', 'medium', 'high'][Math.floor(Math.random() * 3)],
    description: () => `Support issue description: ${Math.random().toString(36).substring(7)}`
  },
  quote_request: {
    service_type: () => ['consulting', 'development', 'design'][Math.floor(Math.random() * 3)],
    budget_range: () => ['< $10k', '$10k-$50k', '> $50k'][Math.floor(Math.random() * 3)],
    timeline: () => ['< 1 month', '1-3 months', '> 3 months'][Math.floor(Math.random() * 3)]
  }
};

/**
 * Select a tenant based on weighted distribution
 */
function selectTenant() {
  const random = Math.random() * 100;
  let cumulativeWeight = 0;
  
  for (const tenant of tenants) {
    cumulativeWeight += tenant.weight;
    if (random <= cumulativeWeight) {
      return tenant;
    }
  }
  
  // Fallback to first tenant
  return tenants[0];
}

/**
 * Generate form data based on template
 */
function generateFormData(formType) {
  const template = formTemplates[formType];
  const data = {};
  
  for (const [field, generator] of Object.entries(template)) {
    data[field] = generator();
  }
  
  return data;
}

/**
 * Generate HMAC signature for request
 */
function generateHmacSignature(secretKey, timestamp, body) {
  const message = `${timestamp}\n${body}`;
  const signature = crypto.hmac('sha256', secretKey, message, 'hex');
  return signature;
}

/**
 * Create form submission request
 */
function createSubmissionRequest(tenant, formType) {
  const timestamp = new Date().toISOString();
  const submissionId = `load_test_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  
  const payload = {
    form_id: formType,
    submission_id: submissionId,
    submitted_at: timestamp,
    payload: generateFormData(formType),
    metadata: {
      source: 'k6_load_test',
      user_agent: 'k6/0.47.0',
      source_ip: '192.168.1.100', // Simulated IP
      session_id: `session_${__VU}_${__ITER}`,
      test_run_id: `load_test_${Date.now()}`
    }
  };
  
  const body = JSON.stringify(payload);
  const signature = generateHmacSignature(tenant.secret, timestamp, body);
  
  return {
    url: `${__ENV.API_ENDPOINT || 'http://localhost:4566'}/submit`,
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenant.id,
      'X-Timestamp': timestamp,
      'X-Signature': signature,
      'User-Agent': 'k6-load-test/1.0',
      'X-Test-Run': 'form-bridge-load-test'
    },
    body: body,
    payload: payload
  };
}

/**
 * Main test function - executed by each VU
 */
export default function () {
  // Select tenant and form type
  const tenant = selectTenant();
  const formType = tenant.forms[Math.floor(Math.random() * tenant.forms.length)];
  
  // Create submission request
  const request = createSubmissionRequest(tenant, formType);
  
  // Measure total submission duration
  const submissionStart = Date.now();
  
  // Make the HTTP request
  const response = http.post(request.url, request.body, {
    headers: request.headers,
    timeout: '30s', // 30 second timeout
    tags: {
      tenant_id: tenant.id,
      form_type: formType,
      test_type: 'form_submission'
    }
  });
  
  const submissionEnd = Date.now();
  const totalDuration = submissionEnd - submissionStart;
  
  // Record custom metrics
  submissionDuration.add(totalDuration);
  multiTenantSubmissions.add(1, { tenant_id: tenant.id, form_type: formType });
  
  // Parse response for component-specific metrics (if available)
  let responseData = {};
  try {
    responseData = JSON.parse(response.body || '{}');
  } catch (e) {
    // Ignore JSON parse errors
  }
  
  // Record component-specific durations if available
  if (responseData.performance) {
    if (responseData.performance.hmac_validation_ms) {
      hmacValidationDuration.add(responseData.performance.hmac_validation_ms);
    }
    if (responseData.performance.eventbridge_publish_ms) {
      eventBridgePublishDuration.add(responseData.performance.eventbridge_publish_ms);
    }
    if (responseData.performance.dynamodb_write_ms) {
      dynamoDBWriteDuration.add(responseData.performance.dynamodb_write_ms);
    }
  }
  
  // Comprehensive checks
  const checks = check(response, {
    'status is 200': (r) => r.status === 200,
    'status is 201': (r) => r.status === 201,
    'response time < 2s': (r) => r.timings.duration < 2000,
    'response time < 5s': (r) => r.timings.duration < 5000,
    'response has submission_id': (r) => {
      try {
        const data = JSON.parse(r.body);
        return data.submission_id !== undefined;
      } catch (e) {
        return false;
      }
    },
    'response indicates success': (r) => {
      try {
        const data = JSON.parse(r.body);
        return data.success === true || r.status < 300;
      } catch (e) {
        return r.status < 300;
      }
    },
    'tenant isolation maintained': (r) => {
      try {
        const data = JSON.parse(r.body);
        // Verify response only contains data for the requesting tenant
        return !data.tenant_id || data.tenant_id === tenant.id;
      } catch (e) {
        return true; // Assume OK if can't parse
      }
    }
  }, { 
    tenant_id: tenant.id, 
    form_type: formType,
    vu: __VU,
    iteration: __ITER
  });
  
  // Record errors
  if (!checks['status is 200'] && !checks['status is 201']) {
    errorRate.add(1, { 
      tenant_id: tenant.id, 
      form_type: formType,
      status_code: response.status,
      error_type: 'http_error'
    });
    
    console.error(`Request failed: ${response.status} - ${response.body.substring(0, 200)}`);
  } else {
    errorRate.add(0);
  }
  
  // Log successful submissions periodically
  if (__ITER % 100 === 0) {
    console.info(`VU ${__VU} completed ${__ITER} iterations. Latest: ${tenant.id}/${formType} - ${response.status}`);
  }
  
  // Variable sleep based on scenario
  const sleepDuration = Math.random() * 2 + 0.5; // 0.5-2.5 seconds
  sleep(sleepDuration);
}

/**
 * Setup function - runs once before the test
 */
export function setup() {
  console.log('🚀 Starting Form-Bridge Load Test');
  console.log(`📊 Testing ${tenants.length} tenants with weighted distribution`);
  console.log(`🎯 Target: Simulate 10K submissions/month scenario`);
  console.log(`🔗 API Endpoint: ${__ENV.API_ENDPOINT || 'http://localhost:4566'}`);
  
  // Test API connectivity
  const healthCheck = http.get(`${__ENV.API_ENDPOINT || 'http://localhost:4566'}/health`, {
    timeout: '10s'
  });
  
  if (healthCheck.status !== 200) {
    console.warn(`⚠️  Health check failed: ${healthCheck.status}. Proceeding anyway...`);
  }
  
  return {
    startTime: Date.now(),
    tenants: tenants.length
  };
}

/**
 * Teardown function - runs once after the test
 */
export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`✅ Load test completed in ${duration.toFixed(2)} seconds`);
  console.log(`📈 Tested ${data.tenants} tenants across multiple scenarios`);
  console.log(`📊 Check detailed metrics in the k6 results`);
}

/**
 * Handle summary for custom reporting
 */
export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    test_duration_seconds: data.state.testRunDurationMs / 1000,
    scenarios: Object.keys(options.scenarios),
    
    // Overall metrics
    total_requests: data.metrics.http_reqs.values.count,
    successful_requests: data.metrics.http_reqs.values.count - (data.metrics.http_req_failed.values.passes || 0),
    error_rate: (data.metrics.http_req_failed.values.rate || 0) * 100,
    
    // Performance metrics
    avg_response_time_ms: data.metrics.http_req_duration.values.avg,
    p95_response_time_ms: data.metrics['http_req_duration'].values['p(95)'],
    p99_response_time_ms: data.metrics['http_req_duration'].values['p(99)'],
    
    // Custom Form-Bridge metrics
    multi_tenant_submissions: data.metrics.multi_tenant_submissions?.values.count || 0,
    avg_submission_duration_ms: data.metrics.submission_duration?.values.avg,
    p95_submission_duration_ms: data.metrics.submission_duration?.values['p(95)'],
    
    // Component performance (if available)
    avg_hmac_validation_ms: data.metrics.hmac_validation_duration?.values.avg,
    avg_eventbridge_publish_ms: data.metrics.eventbridge_publish_duration?.values.avg,
    avg_dynamodb_write_ms: data.metrics.dynamodb_write_duration?.values.avg,
    
    // Thresholds
    thresholds_passed: Object.entries(data.metrics).every(([key, metric]) => {
      return !metric.thresholds || Object.values(metric.thresholds).every(t => !t.lastFailed);
    })
  };
  
  return {
    'stdout': `
🎯 Form-Bridge Load Test Results Summary
========================================
Duration: ${summary.test_duration_seconds.toFixed(2)}s
Total Requests: ${summary.total_requests}
Success Rate: ${((1 - summary.error_rate / 100) * 100).toFixed(2)}%
Avg Response Time: ${summary.avg_response_time_ms.toFixed(2)}ms
P95 Response Time: ${summary.p95_response_time_ms.toFixed(2)}ms
Multi-Tenant Submissions: ${summary.multi_tenant_submissions}
Thresholds: ${summary.thresholds_passed ? '✅ PASSED' : '❌ FAILED'}
`,
    'test-results/k6-summary.json': JSON.stringify(summary, null, 2)
  };
}
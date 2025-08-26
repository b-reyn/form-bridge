# Recommended Slash Commands for FormBridge

## Overview

This document outlines recommended custom slash commands for the FormBridge multi-tenant serverless form processing system. These commands are designed to accelerate development, testing, and operations for the EventBridge-centric architecture.

## Implementation Guide

### Setting Up Commands

1. **Project-specific commands** (shared with team):
   ```bash
   mkdir -p .claude/commands
   ```

2. **Personal commands** (across all projects):
   ```bash
   mkdir -p ~/.claude/commands
   ```

3. **Create a command**:
   ```bash
   echo "Your prompt here with \$ARGUMENTS support" > .claude/commands/command-name.md
   ```

## Command Categories

### 🚀 Development Workflow Commands

#### `/deploy-stack`
**Purpose**: Deploy specific CloudFormation/SAM stack  
**Location**: `.claude/commands/deploy/deploy-stack.md`
```markdown
Deploy the CloudFormation/SAM stack: $ARGUMENTS

1. Validate CloudFormation/SAM template syntax
2. Check for required parameters and environment variables
3. Run `sam build` and `sam deploy --guided`
4. Verify all resources were created successfully
5. Output stack endpoints and resource ARNs
6. Run smoke tests on deployed resources
```

#### `/test-ingestion`
**Purpose**: Test form submission with HMAC authentication  
**Location**: `.claude/commands/test/test-ingestion.md`
```markdown
Test form ingestion API with sample payload for tenant: $ARGUMENTS

1. Generate valid HMAC signature for the tenant
2. Create test form submission payload
3. Submit to /ingest endpoint with proper headers
4. Verify 200 response with submission_id
5. Check EventBridge received the event
6. Confirm DynamoDB persistence
7. Track delivery to configured destinations
```

#### `/validate-event`
**Purpose**: Validate EventBridge event patterns  
**Location**: `.claude/commands/aws/validate-event.md`
```markdown
Validate the EventBridge event pattern for: $ARGUMENTS

1. Parse the provided event pattern
2. Check for required fields (tenant_id, submission_id)
3. Validate against canonical event schema v1.0
4. Test pattern matching with sample events
5. Verify routing rules will trigger correctly
6. Suggest optimizations for pattern efficiency
```

### 🔧 AWS Service-Specific Commands

#### `/lambda-cold-start`
**Purpose**: Analyze and optimize Lambda cold starts  
**Location**: `.claude/commands/aws/lambda-cold-start.md`
```markdown
Analyze cold start performance for Lambda function: $ARGUMENTS

1. Check deployment package size (target < 50MB)
2. Review initialization code outside handler
3. Analyze dependencies and suggest tree-shaking
4. Check for unnecessary SDK imports
5. Suggest provisioned concurrency if needed
6. Recommend memory/CPU optimization
7. Provide cold start benchmark results
```

#### `/dynamo-access-pattern`
**Purpose**: Design DynamoDB access patterns  
**Location**: `.claude/commands/aws/dynamo-access-pattern.md`
```markdown
Design DynamoDB access pattern for: $ARGUMENTS

1. Identify entities and relationships
2. Define primary key structure (PK/SK)
3. Design GSI for secondary access patterns
4. Calculate RCU/WCU requirements
5. Estimate monthly costs
6. Create example queries
7. Suggest TTL and archival strategies
```

#### `/eventbridge-rule`
**Purpose**: Create EventBridge rules  
**Location**: `.claude/commands/aws/eventbridge-rule.md`
```markdown
Create EventBridge rule for: $ARGUMENTS

1. Define event pattern for matching
2. Configure rule targets (Lambda/Step Functions)
3. Set retry policy and max event age
4. Configure DLQ for failed events
5. Add appropriate IAM permissions
6. Generate CloudFormation/CDK code
7. Provide testing instructions
```

#### `/step-functions-workflow`
**Purpose**: Design Step Functions workflows  
**Location**: `.claude/commands/aws/step-functions-workflow.md`
```markdown
Design Step Functions workflow for: $ARGUMENTS

1. Choose Express vs Standard workflow type
2. Create ASL (Amazon States Language) definition
3. Implement Map state for parallel processing
4. Add error handling and retry logic
5. Configure timeouts and heartbeats
6. Calculate state transition costs
7. Generate CloudFormation template
```

### 🏗️ Infrastructure Commands

#### `/estimate-cost`
**Purpose**: Estimate AWS monthly costs  
**Location**: `.claude/commands/infra/estimate-cost.md`
```markdown
Estimate AWS costs for: $ARGUMENTS

Calculate monthly costs based on:
1. Lambda: invocations, duration, memory
2. DynamoDB: storage, RCU, WCU
3. EventBridge: custom events published
4. API Gateway: API calls
5. Step Functions: state transitions
6. CloudWatch: logs, metrics, dashboards
7. Secrets Manager: secrets stored

Provide breakdown by service and total monthly estimate
```

#### `/security-audit`
**Purpose**: Multi-tenant security review  
**Location**: `.claude/commands/infra/security-audit.md`
```markdown
Security audit for: $ARGUMENTS

1. Review IAM roles for least privilege
2. Verify tenant isolation in DynamoDB
3. Check Secrets Manager access policies
4. Validate HMAC implementation
5. Audit API Gateway authorization
6. Review encryption at rest and in transit
7. Check for exposed sensitive data in logs
8. Verify CORS and security headers
9. Generate security compliance report
```

#### `/create-tenant`
**Purpose**: Onboard new tenant  
**Location**: `.claude/commands/deploy/create-tenant.md`
```markdown
Create new tenant configuration: $ARGUMENTS

1. Generate unique tenant_id (t_xxxxxx format)
2. Create HMAC shared secret in Secrets Manager
3. Initialize tenant record in DynamoDB
4. Configure default destinations
5. Set rate limits and quotas
6. Create tenant-specific CloudWatch dashboard
7. Generate API integration documentation
8. Provide WordPress/client setup instructions
```

### 📊 Monitoring & Operations Commands

#### `/trace-submission`
**Purpose**: Debug form submission flow  
**Location**: `.claude/commands/monitor/trace-submission.md`
```markdown
Trace submission ID through the system: $ARGUMENTS

1. Query API Gateway access logs
2. Find Lambda authorizer execution
3. Trace Ingest Lambda invocation
4. Check EventBridge event publication
5. Verify Persist Lambda execution
6. Query DynamoDB for submission record
7. Trace Step Functions execution
8. Check delivery attempts to destinations
9. Identify any failures or bottlenecks
10. Generate timeline visualization
```

#### `/check-dlq`
**Purpose**: Monitor dead letter queues  
**Location**: `.claude/commands/monitor/check-dlq.md`
```markdown
Check DLQ status for: $ARGUMENTS

1. List all DLQs in the system
2. Check message counts per queue
3. Sample oldest messages
4. Identify failure patterns
5. Group errors by type
6. Suggest remediation steps
7. Option to redrive messages
8. Generate alert if threshold exceeded
```

#### `/performance-report`
**Purpose**: System performance metrics  
**Location**: `.claude/commands/monitor/performance-report.md`
```markdown
Generate performance report for: $ARGUMENTS

Analyze metrics for specified time period:
1. API Gateway: request count, latency (p50, p90, p99)
2. Lambda: invocations, errors, duration, cold starts
3. DynamoDB: consumed capacity, throttles, latency
4. EventBridge: matched rules, failed invocations
5. Step Functions: execution time, success rate
6. End-to-end: submission to delivery latency
7. Cost analysis: actual vs budgeted
8. Generate graphs and executive summary
```

### 🔄 Development Session Commands

#### `/sprint-plan`
**Purpose**: Coordinate sprint planning  
**Location**: `.claude/commands/agent/sprint-plan.md`
```markdown
Plan sprint for: $ARGUMENTS

1. Consult product-owner agent for priorities
2. Review backlog and story points
3. Assess team capacity with project-manager
4. Assign tasks to specialist agents:
   - EventBridge tasks → eventbridge-architect
   - Lambda functions → lambda-serverless-expert
   - Database design → dynamodb-architect
   - CI/CD setup → cicd-cloudformation-engineer
5. Create sprint board
6. Set sprint goals and success criteria
7. Schedule ceremonies
```

#### `/agent-coordinate`
**Purpose**: Multi-agent task coordination  
**Location**: `.claude/commands/agent/agent-coordinate.md`
```markdown
Coordinate agents for task: $ARGUMENTS

1. Analyze task requirements
2. Identify required specialist agents
3. Create task breakdown
4. Delegate to appropriate agents in parallel
5. Monitor progress
6. Integrate results
7. Ensure consistency across implementations
8. Update strategy documents
```

### 📝 Documentation Commands

#### `/api-docs`
**Purpose**: Generate API documentation  
**Location**: `.claude/commands/docs/api-docs.md`
```markdown
Generate OpenAPI documentation for: $ARGUMENTS

1. Document all endpoints (paths, methods)
2. Define request/response schemas
3. Include authentication requirements
4. Add example requests and responses
5. Document error codes and meanings
6. Include rate limiting information
7. Generate Postman collection
8. Create integration guide
```

#### `/runbook`
**Purpose**: Create operational runbooks  
**Location**: `.claude/commands/docs/runbook.md`
```markdown
Create runbook for: $ARGUMENTS

1. Define alert trigger conditions
2. Document investigation steps
3. Provide diagnostic commands
4. Include remediation procedures
5. List escalation contacts
6. Add rollback procedures if applicable
7. Include post-incident checklist
8. Link to relevant dashboards
```

### 🧪 Testing Commands

#### `/load-test`
**Purpose**: Performance testing  
**Location**: `.claude/commands/test/load-test.md`
```markdown
Run load test for: $ARGUMENTS

1. Configure Artillery or K6 scenarios
2. Simulate multi-tenant traffic patterns
3. Ramp up to target load gradually
4. Monitor system metrics during test
5. Identify bottlenecks
6. Check for throttling or errors
7. Analyze results and generate report
8. Recommend scaling adjustments
```

#### `/integration-test`
**Purpose**: End-to-end testing  
**Location**: `.claude/commands/test/integration-test.md`
```markdown
Run integration test for: $ARGUMENTS

1. Submit test form with known data
2. Verify API response and status code
3. Check EventBridge event publication
4. Confirm DynamoDB persistence
5. Validate Step Functions execution
6. Verify delivery to destinations
7. Check data transformation accuracy
8. Validate error handling
9. Generate test report
```

#### `/chaos-test`
**Purpose**: Resilience testing  
**Location**: `.claude/commands/test/chaos-test.md`
```markdown
Run chaos test for: $ARGUMENTS

Simulate failures:
1. Lambda function timeouts
2. DynamoDB throttling
3. EventBridge rule disabling
4. Network latency injection
5. Secrets Manager access denied
6. Step Functions quota exceeded
7. API Gateway rate limiting

Verify:
- System degrades gracefully
- Retries work correctly
- DLQs capture failures
- Monitoring alerts fire
- Recovery is automatic
```

## Directory Structure

```bash
.claude/commands/
├── deploy/
│   ├── deploy-stack.md
│   └── create-tenant.md
├── test/
│   ├── test-ingestion.md
│   ├── load-test.md
│   ├── integration-test.md
│   └── chaos-test.md
├── aws/
│   ├── lambda-cold-start.md
│   ├── dynamo-access-pattern.md
│   ├── eventbridge-rule.md
│   ├── step-functions-workflow.md
│   └── validate-event.md
├── infra/
│   ├── estimate-cost.md
│   └── security-audit.md
├── monitor/
│   ├── trace-submission.md
│   ├── check-dlq.md
│   └── performance-report.md
├── agent/
│   ├── agent-coordinate.md
│   └── sprint-plan.md
├── docs/
│   ├── api-docs.md
│   └── runbook.md
└── README.md
```

## Best Practices

1. **Use `$ARGUMENTS`** - Include in prompts where dynamic input is needed
2. **Keep commands focused** - Each command should do one thing well
3. **Version control** - Commit commands to git for team sharing
4. **Document usage** - Include examples in command descriptions
5. **Test commands** - Verify they work before committing
6. **Organize by category** - Use subdirectories for related commands
7. **Update regularly** - Evolve commands based on usage patterns

## Getting Started

1. Create the commands directory:
   ```bash
   mkdir -p .claude/commands
   ```

2. Add your first command:
   ```bash
   cat > .claude/commands/test/test-ingestion.md << 'EOF'
   Test form ingestion for tenant: $ARGUMENTS
   Generate HMAC, submit test form, verify flow
   EOF
   ```

3. Use in Claude Code:
   ```
   /test-ingestion t_abc123
   ```

## Contributing

To add new commands:
1. Identify repetitive tasks
2. Create clear, actionable prompts
3. Test thoroughly
4. Document in this file
5. Share with team via git

## Resources

- [Claude Code Slash Commands Documentation](https://docs.anthropic.com/en/docs/claude-code/slash-commands)
- [Awesome Claude Code Commands](https://github.com/hesreallyhim/awesome-claude-code)
- [Claude Command Suite](https://github.com/qdhenry/Claude-Command-Suite)

---

*Last Updated: 2025-08-26*
*Project: FormBridge - Multi-Tenant Serverless Form Processing*
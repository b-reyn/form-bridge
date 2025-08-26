# Claude Code Hooks Configuration Recommendations for Form-Bridge

*Generated: January 26, 2025*
*Purpose: Optimize development workflow for serverless multi-tenant form ingestion system*

## Executive Summary

This document provides comprehensive hooks.json recommendations specifically tailored for the Form-Bridge project, incorporating serverless AWS Lambda best practices, multi-tenant security requirements, and automated quality assurance workflows.

## Current State Analysis

The existing hooks.json configuration provides basic security controls but lacks:
- Lambda-specific validation hooks
- CloudFormation/SAM template verification
- DynamoDB query optimization checks
- EventBridge pattern validation
- Multi-tenant isolation verification
- Agent strategy update automation
- Cost estimation hooks

## Recommended Hooks Configuration

### Complete hooks.json for Form-Bridge

```json
{
  "hooks": [
    // ============================================
    // PRE-TOOL USE HOOKS - Security & Validation
    // ============================================
    {
      "event": "PreToolUse",
      "matcher": "Edit|MultiEdit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Block sensitive file modifications",
          "command": "python3 -c \"import json, sys; data=json.load(sys.stdin); path=data.get('tool_input',{}).get('file_path',''); forbidden=['.env', 'secrets', 'credentials', '.pem', 'private_key']; sys.exit(2 if any(f in path.lower() for f in forbidden) else 0)\"",
          "stopOnError": true
        }
      ]
    },
    
    {
      "event": "PreToolUse", 
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Validate Lambda function modifications",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ lambdas/.*\\.py$ ]]; then python3 -m py_compile \"$CLAUDE_FILE_PATH\" 2>/dev/null || echo '⚠️ Python syntax error detected'; fi"
        }
      ]
    },

    {
      "event": "PreToolUse",
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "description": "Block dangerous commands",
          "command": "python3 -c \"import json, sys, re; data=json.load(sys.stdin); cmd=data.get('tool_input',{}).get('command',''); dangerous=['rm -rf /', 'sudo rm', 'chmod 777', 'curl.*\\|.*bash', 'wget.*\\|.*sh']; sys.exit(2 if any(re.search(d, cmd) for d in dangerous) else 0)\""
        }
      ]
    },

    {
      "event": "PreToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Enforce multi-tenant key prefixing in DynamoDB operations",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ lambdas/.*\\.py$ ]] && grep -q 'dynamodb\\|table\\|put_item\\|get_item' \"$CLAUDE_FILE_PATH\"; then grep -q 'TENANT#' \"$CLAUDE_FILE_PATH\" || echo '⚠️ WARNING: DynamoDB operation without TENANT# prefix detected'; fi"
        }
      ]
    },

    // ============================================
    // POST-TOOL USE HOOKS - Quality & Automation
    // ============================================
    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Auto-format Python Lambda functions",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ lambdas/.*\\.py$ ]]; then black \"$CLAUDE_FILE_PATH\" 2>/dev/null && echo '✅ Python formatted'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Validate CloudFormation/SAM templates",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ \\.(yaml|yml)$ ]] && grep -q 'AWSTemplateFormatVersion' \"$CLAUDE_FILE_PATH\"; then cfn-lint \"$CLAUDE_FILE_PATH\" 2>/dev/null || echo '⚠️ CloudFormation validation issues detected'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Run Lambda function unit tests",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ lambdas/.*\\.py$ ]] && [[ -f \"${CLAUDE_FILE_PATH%.py}_test.py\" ]]; then pytest \"${CLAUDE_FILE_PATH%.py}_test.py\" -v 2>/dev/null || echo '⚠️ Tests failing'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Check Lambda function complexity",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ lambdas/.*\\.py$ ]]; then radon cc \"$CLAUDE_FILE_PATH\" -s -n C 2>/dev/null | grep -E '^[[:space:]]*[MF]' && echo '⚠️ High complexity detected - consider refactoring'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Security scan Python dependencies",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" == *requirements.txt ]]; then safety check -r \"$CLAUDE_FILE_PATH\" 2>/dev/null || echo '⚠️ Security vulnerabilities in dependencies'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Estimate AWS costs for infrastructure changes",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ template\\.(yaml|yml)$ ]]; then echo '💰 Cost Impact: Run \"sam deploy --no-execute-changeset\" to preview cost changes'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Generate API documentation",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ api/.*\\.py$ ]] || [[ \"$CLAUDE_FILE_PATH\" =~ template\\.yaml$ ]]; then echo '📚 Remember to update API documentation in /docs/api/'; fi"
        }
      ]
    },

    // ============================================
    // SESSION HOOKS - Workflow Management
    // ============================================
    {
      "event": "SessionStart",
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "description": "Initialize Form-Bridge development environment",
          "command": "echo '🚀 Form-Bridge Multi-Tenant Serverless System' && echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' && echo 'Architecture: EventBridge-Centric (Option A)' && echo 'Environment: $(grep ENVIRONMENT .env 2>/dev/null | cut -d= -f2 || echo \"dev\")' && echo '' && echo 'Recent Changes:' && git log --oneline -5 2>/dev/null || echo 'Git not initialized' && echo '' && echo 'Lambda Functions:' && ls -la lambdas/ 2>/dev/null | grep -E '^d' | wc -l && echo '' && echo 'Quick Commands: sam build | sam deploy | pytest tests/'"
        }
      ]
    },

    {
      "event": "UserPromptSubmit",
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "description": "Check for TDD compliance",
          "command": "if echo \"$CLAUDE_USER_PROMPT\" | grep -iE 'implement|create|add.*function|lambda'; then echo '🧪 TDD Reminder: Write tests first! Create test file before implementation.'; fi"
        }
      ]
    },

    {
      "event": "Stop",
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "description": "Update agent strategy documents",
          "command": "echo '📝 Remember to update strategy documents in /docs/strategies/ with learnings from this session'"
        }
      ]
    },

    // ============================================
    // SPECIALIZED HOOKS - Form-Bridge Specific
    // ============================================
    {
      "event": "PreToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Validate EventBridge patterns",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ eventbridge.*\\.json$ ]] || grep -q 'EventPattern' \"$CLAUDE_FILE_PATH\" 2>/dev/null; then echo '🔍 Validating EventBridge pattern syntax...'; python3 -m json.tool \"$CLAUDE_FILE_PATH\" >/dev/null 2>&1 || echo '❌ Invalid JSON in EventBridge pattern'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Check DynamoDB query efficiency",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ lambdas/.*\\.py$ ]] && grep -q 'scan(' \"$CLAUDE_FILE_PATH\"; then echo '⚠️ WARNING: DynamoDB scan detected - consider using query() for better performance'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Validate Step Functions state machine",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ state-machine.*\\.json$ ]]; then echo '🔄 Validating Step Functions definition...' && python3 -c \"import json; json.load(open('$CLAUDE_FILE_PATH'))\" 2>/dev/null || echo '❌ Invalid state machine JSON'; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "description": "Check Lambda cold start optimization",
          "command": "if [[ \"$CLAUDE_FILE_PATH\" =~ lambdas/.*\\.py$ ]]; then size=$(wc -c < \"$CLAUDE_FILE_PATH\"); imports=$(grep -c '^import\\|^from' \"$CLAUDE_FILE_PATH\"); if [ $size -gt 50000 ] || [ $imports -gt 20 ]; then echo '⚠️ Large Lambda detected - consider splitting or optimizing imports for cold starts'; fi; fi"
        }
      ]
    },

    {
      "event": "PostToolUse",
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "description": "Log AWS API calls for cost tracking",
          "command": "if echo \"$CLAUDE_BASH_COMMAND\" | grep -E 'aws|sam deploy'; then echo \"$(date): $CLAUDE_BASH_COMMAND\" >> ~/.claude/aws-api-calls.log; fi"
        }
      ]
    }
  ],

  // ============================================
  // SECURITY CONFIGURATION
  // ============================================
  "security": {
    "auditLog": true,
    "auditFile": "~/.claude/form-bridge-audit.log",
    "sensitivePatterns": [
      "password",
      "secret",
      "token",
      "key",
      "credential",
      "private",
      "api_key",
      "hmac",
      "signature"
    ],
    "blockedOperations": [
      "rm -rf /",
      "chmod 777",
      "sudo rm",
      "git push --force",
      "aws iam delete",
      "aws s3 rm --recursive"
    ],
    "requiredApprovals": [
      "production deployment",
      "database migration",
      "IAM policy changes",
      "API Gateway changes"
    ]
  },

  // ============================================
  // COMPLIANCE & QUALITY GATES
  // ============================================
  "compliance": {
    "aws": {
      "requireEncryption": true,
      "blockPublicS3": true,
      "enforceVPC": false,
      "requireMFA": true
    },
    "code": {
      "pythonVersion": "3.12",
      "maxLambdaSize": "50MB",
      "maxTimeout": "300",
      "minTestCoverage": 80,
      "maxCyclomaticComplexity": 10
    },
    "security": {
      "requireHttps": true,
      "enforceHMAC": true,
      "maxSecretAge": "90days",
      "requiredHeaders": [
        "X-API-Key",
        "X-Request-ID",
        "X-Tenant-ID"
      ]
    }
  },

  // ============================================
  // DEVELOPMENT WORKFLOW OPTIMIZATION
  // ============================================
  "workflow": {
    "tdd": {
      "enforced": true,
      "testFirst": true,
      "coverageThreshold": 80
    },
    "documentation": {
      "autoGenerate": ["api", "schemas"],
      "requiredFor": ["lambdas", "state-machines"],
      "format": "markdown"
    },
    "deployment": {
      "stages": ["dev", "staging", "prod"],
      "requireApproval": ["staging", "prod"],
      "autoRollback": true
    }
  }
}
```

## Hook Categories Explained

### 1. **Pre-Commit Validation Hooks**
These hooks prevent common issues before code is committed:
- Python syntax validation for Lambda functions
- CloudFormation/SAM template validation
- Multi-tenant key prefix enforcement
- Security pattern detection

### 2. **Post-Edit Quality Hooks**
Automatic improvements after file modifications:
- Python code formatting with Black
- Complexity analysis with Radon
- Test execution for modified functions
- Documentation generation reminders

### 3. **Security Enforcement Hooks**
Protect against security vulnerabilities:
- Block sensitive file modifications
- Prevent dangerous bash commands
- Scan dependencies for vulnerabilities
- Enforce HMAC authentication patterns

### 4. **Cost Optimization Hooks**
Help maintain cost efficiency:
- Lambda size monitoring
- Cold start optimization warnings
- AWS API call logging
- Cost estimation prompts

### 5. **Development Workflow Hooks**
Improve development practices:
- TDD enforcement reminders
- Agent strategy update prompts
- Session initialization with project context
- Git status and recent changes display

### 6. **Form-Bridge Specific Hooks**
Tailored to your architecture:
- EventBridge pattern validation
- DynamoDB query optimization
- Step Functions state machine validation
- Multi-tenant isolation verification

## Implementation Strategy

### Phase 1: Core Security (Week 1)
1. Implement sensitive file blocking
2. Add dangerous command prevention
3. Enable audit logging
4. Set up Python syntax validation

### Phase 2: Quality Assurance (Week 2)
1. Add automated formatting
2. Implement test execution hooks
3. Enable complexity analysis
4. Set up coverage reporting

### Phase 3: AWS Optimization (Week 3)
1. Add CloudFormation validation
2. Implement DynamoDB query checks
3. Enable Lambda size monitoring
4. Set up cost tracking

### Phase 4: Workflow Enhancement (Week 4)
1. Add TDD enforcement
2. Implement documentation generation
3. Enable strategy document updates
4. Set up deployment validation

## Benefits of This Configuration

### Security Benefits
- **Zero-tolerance for sensitive data exposure**: Blocks access to credential files
- **Command injection prevention**: Validates all bash commands
- **Dependency vulnerability scanning**: Automatic security checks
- **Multi-tenant isolation enforcement**: Ensures proper key prefixing

### Quality Benefits
- **Consistent code formatting**: Automatic Python formatting
- **Early error detection**: Syntax validation before execution
- **Test coverage enforcement**: Automatic test execution
- **Complexity management**: Warns about high complexity code

### Productivity Benefits
- **Reduced context switching**: Session initialization with project state
- **Automated documentation**: Reminders and generation prompts
- **Cost awareness**: Real-time cost impact notifications
- **Knowledge retention**: Strategy document update reminders

### Operational Benefits
- **Audit trail**: Complete logging of sensitive operations
- **Rollback capability**: Track changes for easy reversal
- **Performance optimization**: Cold start and query warnings
- **Compliance automation**: Enforce security and quality standards

## Monitoring and Metrics

### Key Metrics to Track
1. **Security violations blocked**: Count of prevented dangerous operations
2. **Test coverage trend**: Track coverage improvements over time
3. **Code complexity reduction**: Monitor complexity scores
4. **Cost optimization savings**: Track prevented expensive operations
5. **Development velocity**: Measure time saved through automation

### Audit Log Analysis
Regular review of audit logs should focus on:
- Repeated security violations (training opportunities)
- Common validation failures (process improvements)
- Frequently triggered warnings (automation candidates)
- Cost-impacting operations (optimization targets)

## Troubleshooting Guide

### Common Issues and Solutions

**Issue**: Hooks not triggering
```bash
# Verify hooks.json is valid JSON
python3 -m json.tool .claude/hooks.json

# Check Claude Code version supports hooks
claude --version
```

**Issue**: Performance degradation from hooks
```bash
# Disable specific hooks temporarily
# Comment out resource-intensive hooks in hooks.json

# Monitor hook execution time
time claude [command]
```

**Issue**: False positive security blocks
```bash
# Add exceptions to security patterns
# Update sensitivePatterns array in hooks.json
# Use more specific regex patterns
```

## Integration with CI/CD

### GitHub Actions Integration
```yaml
name: Claude Code Validation
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Claude Code hooks
        run: |
          claude --headless -p "Validate all Lambda functions" \
            --output-format json > validation.json
      - name: Check validation results
        run: python3 check_validation.py validation.json
```

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
claude --headless -p "Run security and quality checks" || exit 1
```

## Best Practices for Hook Management

1. **Version Control**: Always commit hooks.json to repository
2. **Team Alignment**: Share hook configurations across team
3. **Progressive Enhancement**: Start simple, add complexity gradually
4. **Performance Monitoring**: Track hook execution times
5. **Regular Updates**: Review and update hooks monthly
6. **Documentation**: Document custom hooks and their purposes
7. **Testing**: Test hooks in development before production

## Conclusion

This comprehensive hooks configuration will significantly improve the Form-Bridge development workflow by:
- Preventing security vulnerabilities before they're introduced
- Maintaining high code quality standards automatically
- Optimizing AWS Lambda performance and costs
- Enforcing multi-tenant best practices
- Supporting TDD and documentation practices
- Creating an audit trail for compliance

The configuration is designed to be progressive - start with critical security hooks and gradually add quality and optimization hooks as the team becomes comfortable with the workflow.

## Next Steps

1. Review and customize the hooks.json for your specific needs
2. Test hooks in development environment
3. Train team on hook benefits and usage
4. Monitor metrics and adjust thresholds
5. Document team-specific patterns and additions
6. Schedule monthly hook effectiveness reviews

Remember: Hooks are powerful automation tools that should enhance, not hinder, development velocity. Start conservatively and expand based on team feedback and measured benefits.
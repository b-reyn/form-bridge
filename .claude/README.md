# Claude Code Configuration

This directory contains Claude Code configuration for the Multi-Provider Static Site Template.

## 📁 Configuration Files

### `settings.json` (Committed)
Safe default settings that work for all users:
- Basic permissions for reading and Docker operations
- Provider-aware configuration
- Security enforcement rules
- Quality gates and compliance requirements

### `settings.local.json` (Your Custom Settings)
**Not committed to git** - Create this file for your personal settings:
```bash
cp .claude.example/settings.local.json .claude/settings.local.json
```

### `hooks.json` (Production Security)
Automated safety and quality enforcement:
- **Blocks** sensitive file edits (.env, secrets, credentials)
- **Auto-formats** TypeScript files after editing
- **Validates** CloudFormation templates
- **Runs** security audits after package changes

## 🎯 Slash Commands

### `/setup`
Interactive template initialization - configures provider, validates environment, runs initial build.

### `/deploy` 
Production deployment with comprehensive security checks - audits dependencies, runs tests, validates HTTPS.

### `/review`
Comprehensive code review using specialized agents - delegates to appropriate experts for thorough analysis.

### `/switch-provider`
Safe provider switching - preserves all configurations while switching between AWS/Netlify/future providers.

## 🤖 Specialized Agents

The template includes 8 specialized agents in `/agents/`:

- **frontend-react** - React components, TypeScript, UI/UX
- **aws-infrastructure** - CloudFormation, S3, CloudFront deployment
- **test-qa-engineer** - Testing strategies and implementation
- **principal-engineer** - Architecture decisions and reviews
- **repo-strategy-owner** - Repository organization and structure
- **docs-rag-curator** - Documentation organization and optimization
- **debug-champion** - Error analysis and troubleshooting
- **cicd-cloudformation-engineer** - CI/CD pipelines and automation

## 🔒 Security Features

### Built-in Protection
- **Credential Protection**: Blocks editing of .env, secrets, private keys
- **Command Safety**: Prevents dangerous operations (rm -rf, sudo, etc.)
- **Audit Logging**: Tracks all sensitive operations
- **HTTPS Enforcement**: Ensures all deployments use HTTPS

### Quality Gates
- **Pre-deployment**: Type checking, tests, lint, security audit
- **Post-deployment**: HTTPS validation, security headers, functional tests
- **Compliance**: 70% test coverage, zero vulnerabilities, secure headers

## 🚀 Quick Start

1. **Copy example settings**:
   ```bash
   cp .claude.example/settings.local.json .claude/settings.local.json
   ```

2. **Initialize template**:
   ```
   /setup
   ```

3. **Deploy to your chosen provider**:
   ```
   /deploy aws
   # or
   /deploy netlify
   ```

4. **Review changes before committing**:
   ```
   /review
   ```

## 🛠️ Customization

### Adding Provider Permissions
Edit `.claude/settings.local.json` to add provider-specific permissions:

```json
{
  "permissions": {
    "allow": [
      "Bash:vercel deploy*",
      "Bash:vercel env*"
    ]
  }
}
```

### Custom Slash Commands
Add new commands in `.claude/commands/`:

```markdown
# .claude/commands/my-command.md
My custom workflow that does X, Y, Z.

1. Step one
2. Step two
3. Step three
```

### Provider Configuration
Update provider settings in `settings.json`:

```json
{
  "providers": {
    "myProvider": {
      "name": "My Provider",
      "enabled": true,
      "domains": ["docs.myprovider.com"]
    }
  }
}
```

## 🔧 Troubleshooting

### Common Issues

**"Permission denied" errors**:
- Check your `settings.local.json` includes required permissions
- Ensure Docker is running for Docker commands

**Slash commands not working**:
- Verify command files exist in `.claude/commands/`
- Check command syntax and formatting

**Security blocks preventing work**:
- Review hooks.json for overly restrictive rules
- Use secure alternatives (environment scripts vs direct .env edits)

### Debug Mode
Enable verbose logging in `settings.local.json`:

```json
{
  "monitoring": {
    "logCommands": true,
    "trackFileChanges": true,
    "performanceTracking": true
  }
}
```

## 📚 Documentation

- **Main Instructions**: `/CLAUDE.md` - Primary Claude instructions
- **Frontend Context**: `/src/CLAUDE.md` - React/TypeScript guidelines  
- **Infrastructure Context**: `/infrastructure/CLAUDE.md` - AWS deployment rules
- **Best Practices**: `/CLAUDE_CODE_RECOMMENDATIONS_FINAL.md` - Implementation guide

## 🎯 Production Ready

This configuration is designed for **production deployments**:
- Zero tolerance for security vulnerabilities
- HTTPS enforcement on all deployments
- Comprehensive testing and validation
- Audit trails for compliance
- Automated quality gates

The template demonstrates enterprise-grade practices while remaining accessible to developers of all skill levels.

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review the main CLAUDE.md file
3. Consult the specialized agent documentation
4. Check GitHub Issues for common problems

Remember: This is a template - customize it for your specific needs while maintaining security standards.
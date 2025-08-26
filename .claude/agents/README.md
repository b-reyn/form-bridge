# Claude Code Agents Directory

## Structure

The agents are organized into three logical categories:

### 📐 Engineering (`/engineering`)
Technical implementation specialists focused on building and maintaining the system.

**Core Platform Engineers:**
- `eventbridge-architect` - Event bus design and routing
- `lambda-serverless-expert` - Serverless functions and authorization
- `dynamodb-architect` - NoSQL data modeling and multi-tenancy
- `step-functions-orchestrator` - Workflow orchestration
- `api-gateway-specialist` - API design and security

**Infrastructure & DevOps:**
- `aws-infrastructure` - General AWS services and architecture
- `cicd-cloudformation-engineer` - CI/CD pipelines and IaC
- `monitoring-observability-expert` - CloudWatch, X-Ray, metrics
- `secrets-manager-specialist` - Secret management and rotation
- `cognito-auth-expert` - Authentication and authorization

**Development Support:**
- `principal-engineer` - Technical leadership and coordination
- `test-qa-engineer` - Testing strategies and quality assurance
- `debug-champion` - Troubleshooting and debugging
- `frontend-react` - React UI development (minimal use for admin UI)

### 📊 Product (`/product`)
Product management, design, and strategy focused on user needs and business value.

**Product Leadership:**
- `product-owner` - Requirements, backlog, and priorities
- `product-strategy` - Long-term vision and market positioning
- `project-manager` - Sprint planning and cross-team coordination

**User Experience:**
- `ux-researcher` - User research and insights
- `ui-designer` - Interface design and design systems
- `product-analytics` - Metrics, KPIs, and data analysis

### 🔧 Operations (`/operations`)
Supporting agents for documentation, organization, and non-core functions.

- `docs-rag-curator` - Documentation optimization for AI/RAG systems
- `repo-strategy-owner` - Repository organization and standards
- `seo-strategy-expert` - SEO optimization (not applicable to current project)

## Usage

Each agent has:
1. A definition file with their expertise and protocols
2. A strategy document at `/docs/strategies/{agent-name}-strategy.md`
3. Persistent knowledge management requirements

## Knowledge Management Protocol

Every agent MUST:
1. **START**: Read their strategy document
2. **START**: Research latest best practices
3. **WORK**: Document decisions and patterns
4. **END**: Update strategy with learnings

## Project Context

These agents support the **FormBridge** project - a multi-tenant serverless form processing platform built on AWS with:
- EventBridge for event routing
- Lambda for compute
- DynamoDB for storage
- Step Functions for orchestration
- API Gateway for ingestion

## Agent Collaboration

Agents work together based on expertise:
- **Engineering** agents implement technical solutions
- **Product** agents define requirements and validate with users
- **Operations** agents maintain documentation and standards

The `principal-engineer` acts as technical coordinator, while the `product-owner` drives business priorities and the `project-manager` ensures smooth execution.
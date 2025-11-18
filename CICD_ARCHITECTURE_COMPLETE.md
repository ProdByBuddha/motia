# Complete CI/CD Architecture: Parlant + Motia + Pydantic AI + sns-core

## Stack Overview

The complete AI-driven CI/CD system uses four complementary technologies:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Parlant (Conversational Interface)                │
│  - Natural language CI/CD commands                          │
│  - Context-aware multi-turn dialogues                       │
│  - Session management & query routing                       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  Layer 2: Motia (Infrastructure Orchestration)              │
│  - API endpoints, event bus, cron jobs                      │
│  - Docker, Vault, Ollama integration                        │
│  - Service discovery & coordination                         │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  Layer 3: Pydantic AI (Structured Intelligence)             │
│  - BuildAgent, TestAgent, DeployAgent, MonitorAgent         │
│  - Intelligent decision making with type safety             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  Layer 4: sns-core (Communication Efficiency)               │
│  - 60-85% token reduction between agents                    │
│  - Compressed workflow state transfer                       │
└─────────────────────────────────────────────────────────────┘
```

## Component Roles

### 1. Parlant: Conversational AI Framework

**Primary Role**: Natural language interface to CI/CD operations

**Capabilities**:
- Multi-turn deployment conversations
- Context persistence across sessions
- Intent classification and query routing
- Commercial-grade dialogue management

**Example Parlant Configuration**:
```typescript
// /opt/motia/parlant/cicd_agent.ts
import { ParlantAgent, Context, IntentRouter } from 'parlant'

export const cicdAgent = new ParlantAgent({
  name: 'CI/CD Operations Assistant',
  description: 'Intelligent CI/CD agent for deployment and build management',

  intents: [
    {
      name: 'deploy',
      patterns: [
        'deploy {service} to {environment}',
        'push {service} to production',
        'release {service}'
      ],
      handler: async (context: Context) => {
        const { service, environment } = context.slots
        return await motia.cicd.deploy(service, environment)
      }
    },
    {
      name: 'build_status',
      patterns: [
        'is {service} ready',
        'check build status for {service}',
        'can I deploy {service}'
      ],
      handler: async (context: Context) => {
        const { service } = context.slots
        return await motia.cicd.getBuildStatus(service)
      }
    },
    {
      name: 'rollback',
      patterns: [
        'rollback {service}',
        'revert {service} deployment',
        'undo last deployment'
      ],
      handler: async (context: Context) => {
        const { service } = context.slots
        return await motia.cicd.rollback(service)
      }
    }
  ],

  contextManager: {
    sessionTTL: 3600, // 1 hour
    storeHistory: true,
    maxHistory: 20
  }
})
```

### 2. Motia: Infrastructure Orchestration

**Primary Role**: Connects Parlant to execution layer

**Integration Points**:
```typescript
// /opt/motia/steps/cicd/parlant-bridge.step.ts
export const config: ApiRouteConfig = {
  type: 'api',
  method: 'POST',
  path: '/api/parlant/cicd',
  bodySchema: z.object({
    intent: z.string(),
    slots: z.record(z.any()),
    sessionId: z.string(),
    context: z.object({})
  })
}

export const handler: Handlers['ParlantCICDBridge'] = async (req, { emitter, logger }) => {
  const { intent, slots, sessionId, context } = req.body

  logger.info('Parlant intent received', { intent, slots })

  // Route to appropriate CI/CD workflow
  switch (intent) {
    case 'deploy':
      await emitter.emit('cicd.deploy.requested', {
        service: slots.service,
        environment: slots.environment,
        sessionId
      })
      break

    case 'build_status':
      await emitter.emit('cicd.status.requested', {
        service: slots.service,
        sessionId
      })
      break

    case 'rollback':
      await emitter.emit('cicd.rollback.requested', {
        service: slots.service,
        sessionId
      })
      break
  }

  return {
    status: 202,
    body: { message: 'CI/CD operation queued' }
  }
}
```

### 3. Pydantic AI: Structured Intelligence

**Primary Role**: Make intelligent CI/CD decisions

**Agent Architecture**:
```python
# /opt/motia/agents/cicd/build_agent.py
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from sns_core import SNSEncoder

class BuildDecision(BaseModel):
    """Structured build decision from AI"""
    should_build: bool
    reason: str
    strategy: str  # 'cache', 'no-cache', 'multi-stage'
    estimated_time: int  # seconds

class BuildAgent:
    def __init__(self):
        self.agent = Agent(
            'anthropic:claude-3-5-sonnet-20241022',
            result_type=BuildDecision,
            system_prompt='''You are a Docker build expert analyzing commits.
            Determine if rebuild is needed and select optimal build strategy.
            Use sns-core notation for efficient communication.'''
        )
        self.sns = SNSEncoder()

    async def analyze_commit(self, commit_data: dict) -> BuildDecision:
        """
        Analyze commit and decide build strategy

        Input (sns-core notation):
          repo:billionmail|commit:abc123|files:api.py,models.py|lines:+45,-12

        Output (structured Pydantic model):
          BuildDecision(
            should_build=True,
            reason="API changes require rebuild",
            strategy="cache",
            estimated_time=120
          )
        """
        # Encode commit data with sns-core
        encoded = self.sns.encode_commit(commit_data)

        # AI analyzes and returns structured decision
        result = await self.agent.run(
            f"Analyze commit: {encoded}"
        )

        return result.data

    @agent.tool
    async def check_dockerfile_changes(self, files_changed: list[str]) -> bool:
        """Check if Dockerfile was modified"""
        return 'Dockerfile' in files_changed or any(
            'docker-compose' in f for f in files_changed
        )
```

### 4. sns-core: Communication Efficiency

**Primary Role**: Compress inter-agent communication

**CI/CD Notation System**:
```python
# /opt/motia/agents/sns_cicd.py
from sns_core import SNSNotation

class CICDNotation(SNSNotation):
    """Extended sns-core for CI/CD workflows"""

    # Commit notation
    def encode_commit(self, data: dict) -> str:
        """
        Traditional: {"repo": "billionmail", "commit": "abc123", "branch": "main"}
        sns-core: repo:billionmail|commit:abc123|branch:main
        """
        return '|'.join(f"{k}:{v}" for k, v in data.items())

    # Workflow notation
    def encode_workflow(self, steps: list) -> str:
        """
        Traditional: ["build", "test", "deploy"]
        sns-core: build → test → deploy
        """
        return ' → '.join(steps)

    # Result notation
    def encode_result(self, success: bool, details: dict = None) -> str:
        """
        Traditional: {"success": True, "image": "billionmail:abc123", "time": 120}
        sns-core: ✓|img:billionmail:abc123|time:120s
        """
        status = '✓' if success else '✗'
        if details:
            detail_str = '|'.join(f"{k}:{v}" for k, v in details.items())
            return f"{status}|{detail_str}"
        return status

    # Build strategy notation
    def encode_build_strategy(self, strategy: str, options: dict = None) -> str:
        """
        Traditional: {"strategy": "cache", "target": "production", "platform": "linux/amd64"}
        sns-core: build[cache,prod,linux/amd64]
        """
        opts = ','.join([strategy] + (list(options.values()) if options else []))
        return f"build[{opts}]"
```

## Complete Workflow Example

### Scenario: Deploy Billionmail with Conversational Interface

#### Step 1: User Initiates via Parlant

```
User (via Slack/Web): "Deploy billionmail to staging"
```

#### Step 2: Parlant Processing

```typescript
// Parlant classifies intent
Intent: "deploy"
Slots: { service: "billionmail", environment: "staging" }
Context: { user: "buddha", timestamp: "2025-10-14T23:30:00Z" }

// Parlant sends to Motia
POST /api/parlant/cicd
{
  "intent": "deploy",
  "slots": { "service": "billionmail", "environment": "staging" },
  "sessionId": "session_abc123",
  "context": {}
}
```

#### Step 3: Motia Event Emission

```typescript
// Motia emits event
Event: "cicd.deploy.requested"
Payload: {
  service: "billionmail",
  environment: "staging",
  sessionId: "session_abc123"
}
```

#### Step 4: BuildAgent Analysis (Pydantic AI + sns-core)

```python
# BuildAgent receives event
commit_data = {
    "repo": "billionmail",
    "commit": "abc123def456",
    "branch": "main",
    "files_changed": ["api/routes.py", "models/user.py"],
    "lines_changed": "+45,-12"
}

# Encode with sns-core (60-85% token reduction)
encoded = sns.encode_commit(commit_data)
# Result: "repo:billionmail|commit:abc123|branch:main|files:api/routes.py,models/user.py|lines:+45,-12"

# AI analyzes (Pydantic AI returns structured result)
decision = await build_agent.analyze_commit(commit_data)
# Result: BuildDecision(
#   should_build=True,
#   reason="API changes detected",
#   strategy="cache",
#   estimated_time=120
# )

# Execute build if needed
if decision.should_build:
    build_result = await docker_api.build(
        image="billionmail",
        tag=commit_data["commit"],
        strategy=decision.strategy
    )
    # Result (sns-core): "✓|img:billionmail:abc123|time:118s"
```

#### Step 5: TestAgent Smart Selection (Pydantic AI + sns-core)

```python
# TestAgent analyzes which tests to run
test_input = "img:billionmail:abc123|changes:api/routes.py,models/user.py"

test_decision = await test_agent.select_tests(test_input)
# Result: TestDecision(
#   tests_to_run=["unit:api", "unit:models", "integration:auth"],
#   tests_to_skip=["e2e:ui", "performance"],
#   estimated_time=45
# )

# Execute selected tests
test_result = await test_runner.run(test_decision.tests_to_run)
# Result (sns-core): "✓|unit:45/45|int:12/12|time:43s"
```

#### Step 6: DeployAgent Decision (Pydantic AI + sns-core)

```python
# DeployAgent decides deployment strategy
deploy_input = "img:billionmail:abc123|tests:✓|env:staging|metrics:cpu:45%,mem:60%"

deploy_decision = await deploy_agent.decide_strategy(deploy_input)
# Result: DeployDecision(
#   strategy="blue-green",
#   rollback_enabled=True,
#   health_check_duration=300,
#   traffic_shift="gradual"
# )

# Execute deployment
deploy_result = await deployer.deploy(deploy_decision)
# Result (sns-core): "✓|strategy:blue-green|health:✓|time:5m"
```

#### Step 7: Parlant Response to User

```
Parlant → User: "✓ Deployment complete

Build: billionmail:abc123 (2m)
Tests: 57/57 passed (43s)
Deploy: Blue-green strategy (5m)
Health: All checks passing

Staging URL: https://staging.billionmail.com"
```

## Installation & Setup

### Phase 1: Install Dependencies

```bash
cd /opt/motia

# Python dependencies
cat > requirements.txt <<EOF
pydantic-ai>=0.0.14
sns-core @ git+https://github.com/esotericshadow/sns-core.git
docker>=7.0.0
aiohttp>=3.9.0
parlant-sdk>=1.0.0
EOF

pip install -r requirements.txt

# Node.js dependencies (Parlant integration)
npm install parlant-js
```

### Phase 2: Directory Structure

```bash
mkdir -p /opt/motia/{agents/{build,test,deploy,monitor},steps/cicd,parlant}
```

### Phase 3: Configuration

```yaml
# /opt/motia/config/cicd.yml
cicd:
  parlant:
    enabled: true
    session_ttl: 3600
    intents:
      - deploy
      - rollback
      - build_status
      - test_status

  agents:
    build:
      model: anthropic:claude-3-5-sonnet-20241022
      sns_notation: true
    test:
      model: anthropic:claude-3-5-sonnet-20241022
      sns_notation: true
    deploy:
      model: anthropic:claude-3-5-sonnet-20241022
      sns_notation: true

  repositories:
    - name: billionmail
      path: /path/to/billionmail
      branch: main
      auto_build: true
      auto_test: true
      auto_deploy: false  # require approval

  environments:
    staging:
      strategy: blue-green
      auto_rollback: true
    production:
      strategy: canary
      approval_required: true
```

## Benefits of Complete Stack

| Feature | Without Parlant | With Parlant |
|---------|----------------|--------------|
| **Interface** | API calls only | Natural language + API |
| **Context** | Stateless | Session-aware |
| **Approval** | Manual triggers | Conversational approval |
| **Feedback** | Polling/webhooks | Real-time dialogue |
| **Learning** | Static workflows | Context-aware adaptation |

## Conversational CI/CD Examples

### Example 1: Progressive Deployment

```
You: "Deploy billionmail"
Parlant: "To which environment?"
You: "Production"
Parlant: "Production requires approval. Current staging version is healthy. Proceed?"
You: "Yes, use canary with 5%"
Parlant: "Starting canary deployment:
         - 5% traffic to new version
         - Monitoring for 10 minutes
         - Auto-rollback if errors > 1%"
```

### Example 2: Build Troubleshooting

```
You: "Why isn't billionmail building?"
Parlant: "Checking recent builds...
         Last build failed 5 minutes ago.
         Issue: Docker cache miss on layer 12
         Would you like me to:
         1. Rebuild without cache
         2. Analyze Dockerfile
         3. Check CI/CD logs"
You: "1"
Parlant: "Rebuilding without cache... Done in 3m 24s ✓"
```

### Example 3: Multi-Service Orchestration

```
You: "Update all services"
Parlant: "Checking for updates:
         - billionmail: abc123 → def456 (API changes)
         - wix-backend: no changes
         - redis: minor version available

         Update billionmail and redis?"
You: "Yes but redis first"
Parlant: "Deploying in order:
         1. Redis ✓ (30s)
         2. Billionmail 🔄 (building...)"
```

## Next Steps

1. ✅ Review architecture
2. ⏳ Install all dependencies
3. ⏳ Create Parlant CI/CD agent
4. ⏳ Build Pydantic AI agents
5. ⏳ Integrate sns-core
6. ⏳ Configure Motia bridges
7. ⏳ Test complete workflow

---

**Architecture**: Parlant + Motia + Pydantic AI + sns-core
**Created**: October 14, 2025
**Status**: Ready for implementation

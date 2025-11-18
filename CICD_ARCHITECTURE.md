# CI/CD Architecture: Motia + Pydantic AI + sns-core

## Overview

Building an intelligent CI/CD system using:
- **Motia**: Orchestration framework (API, events, cron)
- **Pydantic AI**: Structured AI agents for decision-making
- **sns-core**: Efficient inter-agent communication protocol

## Architecture Layers

### Layer 1: Motia Orchestration (Infrastructure)

Provides the foundation:
- **API Endpoints**: Git webhooks, manual triggers, status queries
- **Event Bus**: Workflow state transitions, agent coordination
- **Cron Jobs**: Scheduled builds, health checks, cleanup
- **Service Integration**: Docker API, Ollama AI, Vault secrets

### Layer 2: Pydantic AI Agents (Intelligence)

Structured AI agents using Pydantic models:

```python
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

class BuildContext(BaseModel):
    repo: str
    commit: str
    branch: str
    dockerfile: str

class BuildResult(BaseModel):
    success: bool
    image_tag: str
    build_time: float
    logs: str

build_agent = Agent(
    'anthropic:claude-3-5-sonnet-20241022',
    result_type=BuildResult,
    system_prompt='''You are a Docker build expert.
    Analyze Dockerfiles and optimize build strategies.'''
)

@build_agent.tool
async def docker_build(ctx: RunContext[BuildContext], strategy: str):
    """Execute docker build with specified strategy"""
    # Build implementation
    pass
```

### Layer 3: sns-core Communication (Efficiency)

Compressed notation between agents:

```
Traditional (without sns-core):
{
  "action": "build",
  "repository": "billionmail",
  "commit_hash": "abc123def456",
  "branch": "main",
  "dockerfile_path": "./Dockerfile",
  "target_registry": "local",
  "build_args": {"NODE_ENV": "production"}
}

With sns-core notation:
repo:billionmail|commit:abc123|branch:main|dockerfile:./Dockerfile → build[prod] → img:billionmail:abc123

# 60-85% token reduction
```

## Component Architecture

### 1. Motia Steps (TypeScript)

```typescript
// /opt/motia/steps/cicd/webhook.step.ts
export const config = {
  type: 'api',
  method: 'POST',
  path: '/api/cicd/webhook/github',
  bodySchema: z.object({
    repository: z.string(),
    ref: z.string(),
    commit: z.string(),
  })
}

export const handler = async (req, { emitter }) => {
  // Emit event for Pydantic AI agent processing
  await emitter.emit('cicd.commit.received', req.body)
  return { status: 202, body: { message: 'Build queued' }}
}
```

### 2. Pydantic AI Agents (Python)

```python
# /opt/motia/agents/build_agent.py
from pydantic_ai import Agent, RunContext
from sns_core import SNSEncoder

class BuildAgent:
    def __init__(self):
        self.agent = Agent(
            'anthropic:claude-3-5-sonnet-20241022',
            result_type=BuildResult,
            system_prompt=self.build_prompt()
        )
        self.sns = SNSEncoder()

    async def process_commit(self, commit_data: dict):
        # Encode with sns-core for efficient processing
        encoded = self.sns.encode(commit_data)

        # AI decision: what build strategy to use?
        result = await self.agent.run(
            f"Analyze commit and determine build strategy: {encoded}"
        )

        # Execute build
        if result.data.should_build:
            return await self.execute_build(result.data.strategy)
```

### 3. sns-core Integration (Notation System)

```python
# /opt/motia/agents/sns_integration.py
from sns_core import SNSNotation

class CICDNotation(SNSNotation):
    """Extended sns-core for CI/CD workflows"""

    def encode_commit(self, data: dict) -> str:
        """
        Convert: {repo: 'billionmail', commit: 'abc123', branch: 'main'}
        To: repo:billionmail|commit:abc123|branch:main
        """
        return '|'.join(f"{k}:{v}" for k, v in data.items())

    def encode_workflow(self, steps: list) -> str:
        """
        Convert: ['build', 'test', 'deploy']
        To: build → test → deploy
        """
        return ' → '.join(steps)

    def decode_result(self, notation: str) -> dict:
        """Parse sns-core notation back to structured data"""
        parts = notation.split('|')
        return {p.split(':')[0]: p.split(':')[1] for p in parts}
```

## Workflow Examples

### Example 1: Automatic Build on Commit

```
1. Git webhook → Motia API (/api/cicd/webhook/github)
   ↓
2. Motia emits event (cicd.commit.received)
   ↓
3. BuildAgent receives event (via Pydantic AI)
   ↓ (sns-core notation)
   repo:billionmail|commit:abc123|branch:main
   ↓
4. AI analyzes commit:
   - Check Dockerfile changes
   - Determine if rebuild needed
   - Select build strategy (cache/no-cache/multi-stage)
   ↓
5. AI decision → build[cache] → img:billionmail:abc123
   ↓
6. Execute Docker build
   ↓
7. TestAgent receives (sns-core)
   img:billionmail:abc123 → test[unit,int] → ✓|✗
   ↓
8. If ✓ → DeployAgent (sns-core)
   img:billionmail:abc123 → deploy[staging] → health → ✓
```

### Example 2: Intelligent Test Selection

```python
# TestAgent uses AI to determine which tests to run

test_agent = Agent(
    'anthropic:claude-3-5-sonnet-20241022',
    system_prompt='''Analyze git diff and intelligently select tests.
    Use sns-core notation for efficient communication.'''
)

# Input (sns-core notation)
changes = "files:auth.py,api.py|lines:+45,-12"

# AI Decision
result = await test_agent.run(
    f"Which tests needed for: {changes}"
)

# Output (sns-core notation)
# test[auth.unit,auth.int,api.unit] → skip[ui.e2e,db.perf]
```

### Example 3: Deployment Decision Making

```python
deploy_agent = Agent(
    'anthropic:claude-3-5-sonnet-20241022',
    system_prompt='''You are a deployment expert.
    Analyze test results, system metrics, and decide deployment strategy.
    Use sns-core for efficient state communication.'''
)

# Input (sns-core notation)
state = "img:billionmail:abc123|tests:✓|metrics:cpu:45%,mem:60%|uptime:99.9%"

# AI analyzes and decides
result = await deploy_agent.run(
    f"Should we deploy? Current state: {state}"
)

# Output (sns-core)
# deploy[blue-green]|rollback[auto]|monitor[5m]
```

## Implementation Steps

### Step 1: Install Dependencies

```bash
cd /opt/motia

# Add Python dependencies
cat >> requirements.txt <<EOF
pydantic-ai>=0.0.1
sns-core>=1.0.0
docker>=7.0.0
aiohttp>=3.9.0
EOF

# Install
pip install -r requirements.txt
```

### Step 2: Create Agent Directory Structure

```bash
mkdir -p /opt/motia/agents/{build,test,deploy,monitor}
mkdir -p /opt/motia/steps/cicd
```

### Step 3: Create Motia CI/CD Steps

```typescript
// /opt/motia/steps/cicd/webhook.step.ts
// /opt/motia/steps/cicd/build-status.step.ts
// /opt/motia/steps/cicd/deploy-trigger.step.ts
```

### Step 4: Create Pydantic AI Agents

```python
# /opt/motia/agents/build/agent.py
# /opt/motia/agents/test/agent.py
# /opt/motia/agents/deploy/agent.py
# /opt/motia/agents/monitor/agent.py
```

### Step 5: Integrate sns-core

```python
# /opt/motia/agents/sns_integration.py
# Notation definitions for CI/CD workflows
```

### Step 6: Update docker-compose.yml

```yaml
services:
  motia:
    # ... existing config ...
    volumes:
      - ./:/app
      - /var/run/docker.sock:/var/run/docker.sock  # Docker API access
    environment:
      # ... existing env ...
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}  # For Pydantic AI
```

## Benefits

### 1. Intelligence
- AI analyzes commits to determine build necessity
- Smart test selection based on code changes
- Deployment decisions based on metrics and context
- Auto-rollback on failures

### 2. Efficiency
- sns-core reduces token usage by 60-85%
- Only run necessary tests
- Parallel execution where possible
- Resource-aware scheduling

### 3. Adaptability
- Learns from build patterns
- Adjusts strategies based on outcomes
- Self-healing deployments
- Context-aware decision making

### 4. Integration
- Uses existing Motia infrastructure
- Connects to Ollama for local AI
- Integrates with Vault for secrets
- Docker API for execution

## Configuration Files

### cicd.config.yaml

```yaml
repositories:
  - name: billionmail
    url: https://github.com/user/billionmail
    branch: main
    build_strategy: docker
    test_commands:
      - npm test
      - npm run test:integration
    deploy_targets:
      staging: billionmail-staging
      production: billionmail-production

agents:
  build:
    model: anthropic:claude-3-5-sonnet-20241022
    sns_notation: true
    max_retries: 3

  test:
    model: anthropic:claude-3-5-sonnet-20241022
    sns_notation: true
    intelligent_selection: true

  deploy:
    model: anthropic:claude-3-5-sonnet-20241022
    sns_notation: true
    strategy: blue-green
    auto_rollback: true

sns_core:
  enabled: true
  compression_level: high
  token_reduction_target: 70

monitoring:
  post_deploy_check: 5m
  rollback_threshold: 5xx_rate > 5%
  alert_channels:
    - prometheus
    - loki
```

## Security

- VPN-only access to Motia endpoints
- Vault integration for secret injection
- Docker socket permission restrictions
- Rate limiting on webhook endpoints
- Audit logging of all deployments

## Observability

- Prometheus metrics for build times, success rates
- Loki logs for agent decisions and reasoning
- Grafana dashboards for CI/CD pipeline visibility
- AlertManager notifications for failures

## Future Enhancements

- Multi-repository orchestration
- Cross-service dependency management
- Cost optimization (AI decides cheapest build strategy)
- Performance profiling integration
- Canary deployment strategies
- Chaos engineering integration

---

**Created**: October 14, 2025
**Architecture**: Motia + Pydantic AI + sns-core
**Maintainer**: buddha@iameternalzion.com

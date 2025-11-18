# Intelligent CI/CD System

AI-powered CI/CD pipeline using Motia + Pydantic AI + sns-core

## Architecture

### 4-Layer Stack with Hybrid AI Backend

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Parlant (Conversational Interface)       │
│  - Natural language CI/CD commands                 │
│  - Context-aware multi-turn dialogues              │
│  - Session management & query routing              │
│  ☁️ AI: Ollama Cloud + sns-core                    │
│  ⏱️ Latency: <1s | 💰 Cost: Minimal                │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  Layer 2: Motia (Infrastructure Orchestration)     │
│  - API endpoints, event bus, cron jobs             │
│  - Docker, Vault, Ollama integration               │
│  - Service discovery & coordination                │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  Layer 3: Pydantic AI (Structured Intelligence)    │
│  - BuildAgent, TestAgent, DeployAgent, MonitorAgent│
│  - Intelligent decision making with type safety    │
│  🖥️ AI: Ollama Local + sns-core                    │
│  ⏱️ Latency: 5-10s | 💰 Cost: $0                   │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  Layer 4: sns-core (Communication Efficiency)      │
│  - 60-85% token reduction between agents           │
│  - Compressed workflow state transfer              │
│  - Used by both Ollama Cloud and Ollama Local      │
└─────────────────────────────────────────────────────┘
```

### Hybrid AI Strategy

**Background Agent Tasks** (Layer 3 - CI/CD Automation)
- **Model**: Ollama Local (`qwen2.5:7b-instruct`)
- **Latency**: 5-10 seconds per decision (acceptable for async operations)
- **Cost**: $0 (local inference)
- **Use Cases**: Build decisions, test selection, deployment strategy, health monitoring
- **Compression**: sns-core reduces prompts by 60-85%

**User-Facing Conversational** (Layer 1 - Parlant Interface)
- **Model**: Ollama Cloud (`qwen2.5:7b-instruct` or similar)
- **Latency**: <1 second response time (critical for UX)
- **Cost**: Minimal with sns-core compression
- **Use Cases**: Natural language commands, status queries, interactive help
- **Compression**: sns-core reduces API costs by 50-70%

This hybrid approach optimizes for:
- ✅ Zero cost for background automation
- ✅ Fast user experience with cloud inference
- ✅ Maximum efficiency with sns-core across both
- ✅ No latency penalty for async CI/CD tasks

## Components

### AI Agents (Python + Pydantic AI)

#### BuildAgent (`agents/cicd/build/agent.py`)
- **Purpose**: Analyze commits and determine build necessity
- **Intelligence**:
  - Detects Dockerfile changes
  - Analyzes file scope and impact
  - Selects optimal build strategy (cache, no-cache, multi-stage)
  - Estimates build time
- **Output**: `BuildDecision` with structured build plan

#### TestAgent (`agents/cicd/test/agent.py`)
- **Purpose**: Intelligent test selection based on code changes
- **Intelligence**:
  - Maps changed files to relevant tests
  - Categorizes tests by type (unit, integration, e2e)
  - Optimizes execution order and parallelization
  - Estimates test duration
- **Output**: `TestDecision` with selected tests

#### DeployAgent (`agents/cicd/deploy/agent.py`)
- **Purpose**: Determine deployment strategy and safety
- **Intelligence**:
  - Assesses test results and system health
  - Determines deployment risk level
  - Selects strategy (immediate, blue-green, canary, rolling)
  - Configures rollback and health checks
- **Output**: `DeployDecision` with deployment plan

#### MonitorAgent (`agents/cicd/monitor/agent.py`)
- **Purpose**: Post-deployment health validation
- **Intelligence**:
  - Monitors error rates, response times, resource usage
  - Detects degradation patterns
  - Triggers automatic rollback when needed
  - Provides actionable recommendations
- **Output**: `MonitorResult` with health assessment

### Motia Steps (TypeScript)

#### github-webhook.step.ts
- **Trigger**: POST `/api/cicd/webhook/github`
- **Action**: Receives GitHub webhooks, emits `cicd.commit.received` event

#### build-trigger.step.ts
- **Trigger**: Event `cicd.commit.received`
- **Action**: Calls BuildAgent, executes Docker build, emits `cicd.build.completed`

#### test-trigger.step.ts
- **Trigger**: Event `cicd.build.completed`
- **Action**: Calls TestAgent, executes tests, emits `cicd.tests.completed`

#### deploy-trigger.step.ts
- **Trigger**: Event `cicd.deploy.requested`
- **Action**: Calls DeployAgent, executes deployment, emits `cicd.deploy.completed`

#### monitor-trigger.step.ts
- **Trigger**: Event `cicd.monitor.start`
- **Action**: Calls MonitorAgent repeatedly, validates health, triggers rollback if needed

## Installation

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker with API access
- Anthropic API key

### Dependencies Installed

```bash
# Python dependencies (already installed in /opt/motia/venv)
- pydantic-ai>=0.0.14
- docker>=7.0.0
- aiohttp>=3.9.0
- anthropic>=0.40.0
- pydantic>=2.0.0
```

### Directory Structure

```
/opt/motia/
├── agents/
│   ├── shared/
│   │   ├── sns_core.py           # SNS notation system
│   │   └── test_sns_core.py      # SNS tests
│   └── cicd/
│       ├── build/
│       │   └── agent.py          # BuildAgent
│       ├── test/
│       │   └── agent.py          # TestAgent
│       ├── deploy/
│       │   └── agent.py          # DeployAgent
│       └── monitor/
│           └── agent.py          # MonitorAgent
├── steps/cicd/
│   ├── github-webhook.step.ts
│   ├── build-trigger.step.ts
│   ├── test-trigger.step.ts
│   ├── deploy-trigger.step.ts
│   └── monitor-trigger.step.ts
└── config/
    └── cicd.yml                  # Configuration
```

## Configuration

Edit `/opt/motia/config/cicd.yml` to configure:

```yaml
repositories:
  - name: billionmail
    path: /opt/billionmail
    build:
      auto_build: true
    test:
      auto_test: true
    deploy:
      staging:
        auto_deploy: true
        strategy: immediate
      production:
        auto_deploy: false  # Manual approval
        strategy: blue-green
```

## Usage

### Setting up GitHub Webhook

1. Go to your repository Settings → Webhooks
2. Add webhook URL: `https://motia.iameternalzion.com/api/cicd/webhook/github`
3. Content type: `application/json`
4. Events: `push` events
5. Save

### Manual Deployment Trigger

```bash
# Trigger deployment via Motia event
curl -X POST https://motia.iameternalzion.com/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "event": "cicd.deploy.requested",
    "data": {
      "repo": "billionmail",
      "commit": "abc123",
      "imageTag": "billionmail:abc123",
      "environment": "production"
    }
  }'
```

### Monitoring Dashboard

Access Motia dashboard at `https://motia.iameternalzion.com` to view:
- Active CI/CD pipelines
- Build status and logs
- Test results
- Deployment progress
- Health monitoring

## Workflow Example

### Automatic Pipeline (Staging)

1. **Commit pushed** to GitHub → Webhook fires
2. **BuildAgent analyzes** commit → Decides to rebuild
3. **Docker build** executes → Image tagged `billionmail:abc123`
4. **TestAgent selects** relevant tests → Runs unit + integration tests
5. **All tests pass** → Triggers deployment to staging
6. **DeployAgent decides** strategy → Immediate deployment (staging)
7. **Deployment completes** → Triggers monitoring
8. **MonitorAgent validates** health → 5 consecutive healthy checks
9. **Deployment validated** → Pipeline complete ✅

### Manual Pipeline (Production)

1. **Staging validated** → Operator approves production
2. **Operator triggers** production deployment
3. **DeployAgent analyzes** → Blue-green strategy, high risk
4. **Blue-green deployment**:
   - Deploy new version alongside old
   - Run health checks (10 minutes)
   - Switch traffic
   - Keep old version for rollback
5. **MonitorAgent validates** → 5 consecutive healthy checks
6. **Deployment validated** → Old version removed

### Automatic Rollback Example

1. **Deployment completes** → MonitorAgent starts checking
2. **Health check 1**: Error rate 0.05% ✅
3. **Health check 2**: Error rate 0.1% ✅
4. **Health check 3**: Error rate 2.5% ⚠️ (Warning)
5. **MonitorAgent decides** → Rollback threshold exceeded
6. **Automatic rollback** triggered
7. **Previous version restored** → Service healthy again
8. **Alert sent** to operations team

## sns-core Notation Examples

### Commit Encoding
```
Traditional JSON: {
  "repo": "billionmail",
  "commit": "abc123def456",
  "branch": "main",
  "files": ["api.py", "models.py"],
  "lines": "+45,-12"
}

SNS-core: repo:billionmail|commit:abc123|branch:main|files:api.py,models.py|lines:+45,-12
Token reduction: 63%
```

### Build Result
```
Traditional: {"success": true, "image": "billionmail:abc123", "time": "120s"}
SNS-core: ✓|img:billionmail:abc123|time:120s
```

### Test Selection
```
SNS-core: test[unit:api,unit:models,int:auth] → skip[e2e:ui,perf]
```

### Deployment Strategy
```
SNS-core: deploy[blue-green]|rollback[auto]|monitor[5m]|health[✓]
```

## Testing Agents

### Test BuildAgent
```bash
cd /opt/motia/agents/cicd/build
../../venv/bin/python agent.py
```

### Test TestAgent
```bash
cd /opt/motia/agents/cicd/test
../../venv/bin/python agent.py
```

### Test DeployAgent
```bash
cd /opt/motia/agents/cicd/deploy
../../venv/bin/python agent.py
```

### Test MonitorAgent
```bash
cd /opt/motia/agents/cicd/monitor
../../venv/bin/python agent.py
```

### Test sns-core
```bash
cd /opt/motia/agents/shared
../../venv/bin/python test_sns_core.py
```

## Monitoring & Observability

### Metrics Tracked
- Build duration and success rate
- Test duration and pass rate
- Deployment duration and success rate
- Error rate (target: <0.1%)
- Response time p95/p99
- CPU and memory usage

### Alerts
- Build failures (after 2 consecutive failures)
- Test failures (after 2 consecutive failures)
- Deployment failures (immediate)
- High error rate (>1%)
- Slow response times (p95 >500ms)
- High resource usage (CPU >85%, Memory >90%)

### Dashboards
- Grafana: https://grafana.iameternalzion.com
- Prometheus: http://prometheus:9090
- Loki: http://loki:3100

## Troubleshooting

### Build not triggering
1. Check GitHub webhook delivery (Settings → Webhooks → Recent Deliveries)
2. Check Motia logs: `docker logs motia`
3. Verify webhook URL is accessible: `curl https://motia.iameternalzion.com/api/cicd/webhook/github`

### Agent errors
1. Check Python environment: `./venv/bin/python --version`
2. Test agent directly: `cd agents/cicd/build && ../../venv/bin/python agent.py`
3. Check Anthropic API key: `echo $ANTHROPIC_API_KEY`

### Deployment fails
1. Check Docker access: `docker ps`
2. Check image exists: `docker images | grep billionmail`
3. Check deployment logs in Motia dashboard

### Health checks failing
1. Check service is running: `curl https://staging.billionmail.com/health`
2. Check Prometheus metrics: `curl http://prometheus:9090/api/v1/query?query=up{job="billionmail"}`
3. Review MonitorAgent output for specific issues

## Next Steps

- [ ] Add Parlant conversational interface
- [ ] Integrate with Slack for notifications
- [ ] Add support for more deployment strategies (canary improvements)
- [ ] Implement multi-repository orchestration
- [ ] Add cost optimization features
- [ ] Integrate chaos engineering tests

## Documentation

- Full Architecture: `/opt/motia/CICD_ARCHITECTURE_COMPLETE.md`
- Configuration: `/opt/motia/config/cicd.yml`
- Motia Docs: `/opt/motia/README.md`

---

**Created**: October 15, 2025
**Architecture**: Motia + Pydantic AI + sns-core
**Status**: Implemented and Ready for Testing

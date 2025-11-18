# Parlant Integration for Conversational CI/CD

Integration specification for Layer 1: Parlant conversational interface with Ollama Cloud + sns-core

## Architecture Overview

```
User → Parlant (Ollama Cloud + sns-core) → Motia Event Bus → CI/CD Agents (Ollama Local + sns-core)
  ↑                                                                              ↓
  └───────────────────────────── Status Updates ─────────────────────────────────┘
```

## Configuration

### Ollama Cloud Setup

**Environment Variables**:
```bash
OLLAMA_CLOUD_URL=https://api.ollama.ai  # or your cloud endpoint
OLLAMA_CLOUD_API_KEY=your_api_key_here
OLLAMA_CLOUD_MODEL=qwen2.5:7b-instruct
```

**Parlant Configuration** (`/opt/motia/config/parlant.yml`):
```yaml
parlant:
  enabled: true

  # LLM Configuration
  llm:
    provider: ollama_cloud
    model: qwen2.5:7b-instruct
    endpoint: ${OLLAMA_CLOUD_URL}
    api_key: ${OLLAMA_CLOUD_API_KEY}
    timeout: 10
    streaming: true

  # sns-core Integration
  sns_core:
    enabled: true
    compression_level: high
    token_reduction_target: 60

    # Compress user queries and system responses
    compress_input: true
    compress_output: false  # Keep responses readable for users
    compress_internal: true  # Compress agent-to-agent communication

  # Session Management
  session:
    max_duration: 3600  # 1 hour
    context_window: 10  # Remember last 10 turns
    memory_backend: redis

  # Performance
  performance:
    max_concurrent_users: 50
    response_timeout: 5
    latency_target: 1000  # <1s response time
```

## sns-core Integration

### User Query Compression

**Example User Query**:
```
User: "What's the status of the last deployment to production for billionmail?"
```

**Without sns-core** (sent to LLM):
```json
{
  "query": "What's the status of the last deployment to production for billionmail?",
  "context": {
    "user_id": "buddha",
    "session_id": "sess_12345",
    "history": [...previous 5 turns...],
    "available_commands": ["status", "deploy", "rollback", "logs"]
  }
}
```
**Token count**: ~350 tokens

**With sns-core** (sent to LLM):
```
q:deploy_status|repo:billionmail|env:prod|user:buddha|sess:12345|cmd:status,deploy,rollback,logs
```
**Token count**: ~120 tokens (65% reduction)

### Internal Agent Communication

When Parlant needs to query CI/CD status:

**Without sns-core**:
```json
{
  "action": "get_deployment_status",
  "repository": "billionmail",
  "environment": "production",
  "include_history": true,
  "metrics": ["error_rate", "response_time", "health_status"]
}
```

**With sns-core**:
```
action:deploy_status|repo:billionmail|env:prod|hist:✓|metrics:error,response,health
```

## Conversational Commands

### Natural Language → Motia Events

**Build Commands**:
```
User: "Rebuild billionmail with no cache"
→ Parlant parses intent
→ Emits: cicd.build.requested {repo: "billionmail", strategy: "no-cache"}
```

**Deployment Commands**:
```
User: "Deploy billionmail to production using blue-green"
→ Parlant parses intent + checks permissions
→ Emits: cicd.deploy.requested {repo: "billionmail", env: "production", strategy: "blue-green"}
```

**Status Queries**:
```
User: "Show me the last 5 deployments"
→ Parlant queries Motia history
→ Returns: Formatted deployment history with sns-core compressed data
```

**Rollback Commands**:
```
User: "Roll back the production deployment"
→ Parlant confirms with user
→ Emits: cicd.rollback.triggered {repo: "billionmail", env: "production"}
```

## Implementation Steps

### Phase 1: Setup Parlant with Ollama Cloud

1. **Install Parlant SDK**:
```bash
cd /opt/motia
./venv/bin/pip install parlant-sdk ollama-api
```

2. **Configure Ollama Cloud Client**:
```python
# /opt/motia/agents/parlant/ollama_client.py
import os
from ollama import Client

class OllamaCloudClient:
    def __init__(self):
        self.client = Client(
            host=os.getenv('OLLAMA_CLOUD_URL'),
            api_key=os.getenv('OLLAMA_CLOUD_API_KEY')
        )
        self.model = os.getenv('OLLAMA_CLOUD_MODEL', 'qwen2.5:7b-instruct')

    def chat(self, messages, stream=True):
        return self.client.chat(
            model=self.model,
            messages=messages,
            stream=stream
        )
```

3. **Integrate sns-core Compression**:
```python
# /opt/motia/agents/parlant/parlant_agent.py
import sys
sys.path.insert(0, '/opt/motia/agents/shared')
from sns_core import CICDNotation

class ParlantAgent:
    def __init__(self):
        self.sns = CICDNotation()
        self.ollama = OllamaCloudClient()

    def process_query(self, user_query, context):
        # Compress context with sns-core
        compressed_context = self.sns.encode_dict(context)

        # Build compressed prompt
        prompt = f"q:{user_query}|ctx:{compressed_context}"

        # Send to Ollama Cloud
        response = self.ollama.chat([
            {"role": "system", "content": PARLANT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])

        return response
```

### Phase 2: Connect to Motia Event Bus

```python
# /opt/motia/agents/parlant/event_bridge.py
class ParlantEventBridge:
    def __init__(self, motia_emitter):
        self.emitter = motia_emitter

    async def handle_build_request(self, repo, strategy="cache"):
        await self.emitter.emit('cicd.build.requested', {
            'repo': repo,
            'strategy': strategy,
            'triggered_by': 'parlant'
        })

    async def handle_deploy_request(self, repo, env, strategy="blue-green"):
        await self.emitter.emit('cicd.deploy.requested', {
            'repo': repo,
            'environment': env,
            'strategy': strategy,
            'triggered_by': 'parlant'
        })

    async def handle_status_query(self, repo, env=None):
        # Query Motia for latest pipeline status
        # Return formatted response to user
        pass
```

### Phase 3: Add Conversational Endpoints

```typescript
// /opt/motia/steps/parlant/chat.step.ts
export const config: APIConfig = {
  type: 'api',
  name: 'ParlantChat',
  description: 'Conversational CI/CD interface',
  method: 'POST',
  path: '/api/parlant/chat',
};

export const handler: Handlers['ParlantChat'] = async (req, { emitter, logger }) => {
  const { message, session_id, user_id } = req.body;

  // Call Parlant agent via Python
  const venvPython = '/opt/motia/venv/bin/python';
  const parlantInput = JSON.stringify({ message, session_id, user_id });

  const { stdout } = await execAsync(
    `${venvPython} -c "import sys; sys.path.insert(0, '/opt/motia/agents/parlant'); from parlant_agent import ParlantAgent; import json; agent = ParlantAgent(); data = json.loads('${parlantInput.replace(/'/g, "\\'")}'); result = agent.process_query_sync(data['message'], {'session': data['session_id'], 'user': data['user_id']}); print(json.dumps(result))"`
  );

  const response = JSON.parse(stdout.trim());

  return {
    status: 200,
    body: {
      response: response.message,
      actions: response.actions,
      session_id: session_id
    }
  };
};
```

## Performance Targets

### User-Facing (Parlant Layer)

| Metric | Target | With sns-core |
|--------|--------|---------------|
| Response Latency | <1s | ✅ Achievable |
| Token Cost per Query | $0.0001-0.0005 | 50-70% reduction |
| Concurrent Users | 50+ | Scaled by Ollama Cloud |
| Context Retention | 10 turns | Compressed efficiently |

### Background Agents (CI/CD Layer)

| Metric | Target | With Local Ollama |
|--------|--------|-------------------|
| Decision Latency | 5-10s | ✅ Acceptable |
| Cost per Decision | $0 | Local inference |
| Throughput | 10 decisions/min | Limited by local GPU |

## Example Conversation Flow

```
User: "Hey, what's the status of billionmail in production?"

Parlant (Ollama Cloud):
→ Parses: status_query(repo=billionmail, env=production)
→ Queries Motia event history
→ Compresses data with sns-core for efficient processing
→ Returns: "Billionmail in production is healthy. Last deployment was 2 hours ago
           with blue-green strategy. Current error rate: 0.03%, Response time p95:
           145ms. All health checks passing."

User: "Great! Now deploy the latest commit to staging"

Parlant (Ollama Cloud):
→ Parses: deploy_request(repo=billionmail, env=staging, strategy=auto)
→ Emits: cicd.deploy.requested event
→ Returns: "Deployment to staging initiated. I'll monitor the progress and notify
           you when complete."

Background (Ollama Local):
→ DeployAgent analyzes (5s latency, $0 cost)
→ Executes deployment
→ MonitorAgent validates health
→ Emits: cicd.deploy.completed

Parlant:
→ Receives event notification
→ Notifies user: "Deployment to staging completed successfully! Health checks
                  passed. Ready for testing."
```

## Testing Parlant Integration

```bash
# Test Ollama Cloud connectivity
curl -X POST ${OLLAMA_CLOUD_URL}/api/chat \
  -H "Authorization: Bearer ${OLLAMA_CLOUD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:7b-instruct",
    "messages": [{"role": "user", "content": "test"}],
    "stream": false
  }'

# Test sns-core compression
cd /opt/motia/agents/shared
../../venv/bin/python test_sns_core.py

# Test Parlant agent
cd /opt/motia/agents/parlant
../../venv/bin/python parlant_agent.py
```

## Next Steps

- [ ] Configure Ollama Cloud credentials
- [ ] Implement ParlantAgent with Ollama Cloud client
- [ ] Integrate sns-core compression in Parlant layer
- [ ] Create conversational API endpoints
- [ ] Connect Parlant to Motia event bus
- [ ] Build conversation history and context management
- [ ] Add user authentication and authorization
- [ ] Implement streaming responses for better UX
- [ ] Add error handling and fallback logic
- [ ] Test end-to-end conversation → CI/CD → notification flow

---

**Architecture Benefit**: By using Ollama Cloud for Parlant and Local Ollama for CI/CD agents,
we achieve <1s user response times while maintaining $0 cost for background automation, all with
60-85% token reduction through sns-core compression.

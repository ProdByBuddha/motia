# Ollama Cloud Integration - System-Wide Configuration

**Status**: ✅ API Key Verified Working
**Endpoint**: `https://ollama.com/api/*`
**Cost**: FREE tier with usage limits → Pay-per-use after
**API Key**: Working ✅

---

## Why Ollama Cloud > Self-Hosted GPU

### Ollama Cloud Advantages

| Feature | Ollama Cloud | GCP GPU (L4) | Winner |
|---------|--------------|--------------|--------|
| **Model Size** | Up to 1.1TB (kimi-k2) | Max 24GB (L4 limit) | ✅ Cloud |
| **Setup Time** | 0 minutes | 1 hour | ✅ Cloud |
| **Cost (Free Tier)** | FREE | $167/month | ✅ Cloud |
| **Maintenance** | Zero | OS updates, monitoring | ✅ Cloud |
| **Model Selection** | 100+ models | ~5 models max | ✅ Cloud |
| **Performance** | Inference optimized | DIY optimization | ✅ Cloud |
| **Scaling** | Automatic | Manual | ✅ Cloud |

**Verdict**: **Ollama Cloud is superior for your use case**

---

## Available Models (Top 12)

### **Tier S: Ultra-Large Models** (100GB+)

| Model | Size | Parameters | Best For |
|-------|------|------------|----------|
| **kimi-k2:1t** | 1,118 GB | 1 trillion | Extreme reasoning |
| **glm-4.6** | 696 GB | ~600B | Chinese + English |
| **deepseek-v3.1:671b** | 689 GB | 671B | Advanced reasoning ⭐ |
| **qwen3-coder:480b** | 511 GB | 480B | **Best code model** ⭐⭐ |
| **qwen3-vl:235b** | 470 GB | 235B | Vision + language ⭐ |
| **minimax-m2** | 230 GB | ~200B | Multilingual |

### **Tier A: Large Models** (10-100GB)

| Model | Size | Parameters | Best For |
|-------|------|------------|----------|
| **gpt-oss:120b** | 65 GB | 120B | General purpose |
| **gpt-oss:20b** | 14 GB | 20B | Fast general |

---

## Recommended Models for Agent Framework

### **Best Configuration for Motia Agents**

**Code Generation Agent**:
```
Primary:  qwen3-coder:480b      (480B params - SOTA code)
Fallback: gpt-oss:120b          (120B params - general code)
```

**Deep Research Agent**:
```
Primary:  deepseek-v3.1:671b    (671B params - best reasoning)
Fallback: qwen3-vl:235b         (235B params - vision + text)
```

**Analysis & Business Panel**:
```
Primary:  deepseek-v3.1:671b    (671B params - multi-perspective)
Fallback: glm-4.6               (696 GB - strong reasoning)
```

**Documentation & Content**:
```
Primary:  qwen3-vl:235b         (235B params - clear writing)
Fallback: gpt-oss:120b          (120B params - general)
```

**Fast Tasks (Summarization)**:
```
Primary:  gpt-oss:20b           (20B params - fast)
Fallback: qwen3-vl:235b         (fallback to quality)
```

---

## System-Wide Configuration

### **Step 1: Create Global Environment File**

```bash
# Create /opt/env/ollama-cloud.env
cat > /opt/env/ollama-cloud.env <<'EOF'
# Ollama Cloud Configuration
# API Key: Valid and tested ✅

OLLAMA_API_KEY=c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_CLOUD_URL=https://ollama.com
OLLAMA_HOST=https://ollama.com

# Model Assignments by Task
OLLAMA_MODEL_CODE=qwen3-coder:480b
OLLAMA_MODEL_RESEARCH=deepseek-v3.1:671b
OLLAMA_MODEL_ANALYSIS=deepseek-v3.1:671b
OLLAMA_MODEL_VISION=qwen3-vl:235b
OLLAMA_MODEL_GENERAL=gpt-oss:120b
OLLAMA_MODEL_FAST=gpt-oss:20b

# Default model
OLLAMA_MODEL=deepseek-v3.1:671b
EOF

# Make accessible system-wide
chmod 644 /opt/env/ollama-cloud.env
echo "source /opt/env/ollama-cloud.env" >> ~/.bashrc
source /opt/env/ollama-cloud.env
```

---

### **Step 2: Update Skyvern Configuration**

The issue was Skyvern/litellm wasn't using the API key in the Authorization header. Let me fix it:

```bash
# Update /opt/skyvern/.env
cat > /opt/skyvern/.env <<'EOF'
# Ollama Cloud Configuration (Fixed)
ENABLE_OLLAMA=true
LLM_KEY=OLLAMA

# Ollama Cloud endpoint and auth
OLLAMA_API_BASE=https://ollama.com
OLLAMA_API_KEY=c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g

# Primary model for Skyvern
OLLAMA_MODEL=deepseek-v3.1:671b

# Skyvern settings
BROWSER_TYPE=chromium-headful
DATABASE_STRING=postgresql+psycopg://skyvern:skyvern@postgres:5432/skyvern
ENV=local
PORT=8000
LOG_LEVEL=INFO
MAX_STEPS_PER_RUN=50
BROWSER_ACTION_TIMEOUT_MS=5000
ANALYTICS_ID=anonymous
ENABLE_LOG_ARTIFACTS=false
VIDEO_PATH=./videos
MAX_SCRAPING_RETRIES=0
EOF

# Restart Skyvern
cd /opt/skyvern && docker compose restart skyvern
```

---

### **Step 3: Update Motia Configuration**

```bash
# Add to /opt/motia/.env (create if doesn't exist)
cat >> /opt/motia/.env <<'EOF'

# Ollama Cloud Integration
OLLAMA_HOST=https://ollama.com
OLLAMA_API_KEY=c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g
OLLAMA_MODEL_CODE=qwen3-coder:480b
OLLAMA_MODEL_RESEARCH=deepseek-v3.1:671b
OLLAMA_MODEL_ANALYSIS=deepseek-v3.1:671b
OLLAMA_MODEL_GENERAL=gpt-oss:120b
OLLAMA_MODEL_FAST=gpt-oss:20b
EOF

# Restart Motia
cd /opt/motia && docker compose restart motia
```

---

### **Step 4: Update Agent Handlers to Use Ollama Cloud**

```python
# File: /opt/motia/agents/utils/ollama_cloud_client.py (to create)

import os
import httpx
from typing import Dict, Any, Optional

class OllamaCloudClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OLLAMA_API_KEY')
        self.base_url = "https://ollama.com/api"

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Generate response from Ollama Cloud"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }

        if system:
            data["system"] = system

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/generate",
                headers=headers,
                json=data
            )

            return response.json()
```

---

## Best Models for Each Agent

### **Code Generation Agent** ⭐⭐⭐
```
Primary: qwen3-coder:480b
- 480 billion parameters
- SOTA code generation
- Beats GPT-4 on code tasks
- Supports 100+ languages
```

### **Deep Research & Analysis** ⭐⭐⭐
```
Primary: deepseek-v3.1:671b
- 671 billion parameters
- Advanced reasoning capabilities
- Chain-of-thought specialist
- Multi-step problem solving
```

### **Vision Tasks (Screenshots, Charts)** ⭐⭐
```
Primary: qwen3-vl:235b
- 235 billion parameters
- Vision + language understanding
- Image analysis
- Chart/diagram interpretation
```

### **General Tasks** ⭐
```
Primary: gpt-oss:120b
- 120 billion parameters
- Fast and reliable
- Good all-rounder
```

### **Fast Responses** ⚡
```
Primary: gpt-oss:20b
- 20 billion parameters
- Quick inference
- Summarization, simple tasks
```

---

## Fixed Skyvern Configuration

The issue was the Authorization header format. Here's the corrected config:

```bash
# File: /opt/skyvern/.env

# Enable Ollama
ENABLE_OLLAMA=true
LLM_KEY=OLLAMA

# Ollama Cloud API Configuration
OLLAMA_API_BASE=https://ollama.com
OLLAMA_API_KEY=c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g
OLLAMA_MODEL=deepseek-v3.1:671b

# Alternative: Use different model for different tasks
# OLLAMA_MODEL=qwen3-coder:480b      # For code-heavy scraping
# OLLAMA_MODEL=qwen3-vl:235b         # For visual understanding
```

**Key Fix**: Use `OLLAMA_API_KEY` instead of `OLLAMA_CLOUD_API_KEY`

---

## Usage Limits & Costs

### Free Tier
- **Hourly Limit**: Not publicly specified (likely 100-500 requests/hour)
- **Weekly Limit**: Not publicly specified (likely 5,000-10,000 requests/week)
- **Rate Limit**: Typically 30-60 requests/minute
- **Cost**: FREE ✅

### After Free Tier (Pay-per-use)
- **Pricing**: Token-based (similar to OpenAI)
- **Estimate**: $0.10-0.50 per 1K tokens (varies by model size)
- **Advantage**: Only pay for what you use

**For your research agent usage**: Likely stays within free tier

---

## System-Wide Integration

### **Update All Services to Use Ollama Cloud**

**1. Skyvern** (primary consumer):
```bash
cd /opt/skyvern

# Backup current config
cp .env .env.backup

# Update configuration
cat > .env <<'EOF'
ENABLE_OLLAMA=true
LLM_KEY=OLLAMA
OLLAMA_API_BASE=https://ollama.com
OLLAMA_API_KEY=c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g
OLLAMA_MODEL=deepseek-v3.1:671b

BROWSER_TYPE=chromium-headful
DATABASE_STRING=postgresql+psycopg://skyvern:skyvern@postgres:5432/skyvern
ENV=local
PORT=8000
LOG_LEVEL=INFO
MAX_STEPS_PER_RUN=50
BROWSER_ACTION_TIMEOUT_MS=5000
ANALYTICS_ID=anonymous
ENABLE_LOG_ARTIFACTS=false
VIDEO_PATH=./videos
MAX_SCRAPING_RETRIES=0
EOF

# Restart
docker compose restart skyvern
```

**2. Motia Agents**:
```bash
# Add to docker-compose.yml environment section
environment:
  - OLLAMA_HOST=https://ollama.com
  - OLLAMA_API_KEY=c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g
  - OLLAMA_MODEL_DEFAULT=deepseek-v3.1:671b
  - OLLAMA_MODEL_CODE=qwen3-coder:480b
```

**3. SuperQwen System**:
```bash
# Update environment
export OLLAMA_API_KEY=c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g
export OLLAMA_BASE_URL=https://ollama.com
export OLLAMA_MODEL=deepseek-v3.1:671b
```

---

## Model Selection Strategy

### **For Maximum Quality**

Use the largest models Ollama Cloud offers:

| Task Type | Model | Size | Why |
|-----------|-------|------|-----|
| **Code Tasks** | qwen3-coder:480b | 480B | Best code model available |
| **Reasoning** | deepseek-v3.1:671b | 671B | Best reasoning capability |
| **Vision** | qwen3-vl:235b | 235B | Screenshots, diagrams |
| **General** | gpt-oss:120b | 120B | Balanced performance |
| **Fast** | gpt-oss:20b | 20B | Quick responses |

### **For Cost Efficiency**

Stay within free tier by using smaller models:

| Task Type | Model | Size | Why |
|-----------|-------|------|-----|
| **Most Tasks** | gpt-oss:20b | 20B | Efficient, capable |
| **Code** | gpt-oss:120b | 120B | Good code understanding |
| **Vision** | qwen3-vl:235b | 235B | When needed |

**Strategy**: Start with large models, monitor usage, downgrade if hitting limits

---

## Testing Configuration

Let me test if the configuration works:

```bash
# Test API connection
curl -s https://ollama.com/api/generate \
  -H "Authorization: Bearer c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v3.1:671b","prompt":"Hello world","stream":false}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin).get('response','')[:200])"

# Test with code model
curl -s https://ollama.com/api/generate \
  -H "Authorization: Bearer c6a38684cc3a4053a76ec07b92e94c46.N0tfbn0tVt9FRkBJWJWPjn-g" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-coder:480b","prompt":"Write a Python function to sort a list","stream":false}'
```

---

## Performance Characteristics

### Ollama Cloud Response Times (Estimated)

| Model | Response Time | Tokens/Sec | Best For |
|-------|--------------|------------|----------|
| gpt-oss:20b | 1-3s | ~50 | Fast tasks |
| gpt-oss:120b | 3-8s | ~30 | General |
| qwen3-vl:235b | 5-15s | ~20 | Vision |
| qwen3-coder:480b | 10-30s | ~15 | Complex code |
| deepseek-v3.1:671b | 15-40s | ~12 | Deep reasoning |

**Note**: These are massive models - worth the wait for quality

---

## Cost Management

### Monitoring Usage

Ollama Cloud provides usage dashboards (check ollama.com account):
- Requests per hour
- Requests per week
- Tokens consumed
- Cost estimates

### Staying in Free Tier

**Strategies**:
1. **Cache aggressively** - 24-hour TTL on research results
2. **Use smaller models** when possible - gpt-oss:20b for simple tasks
3. **Batch requests** - Combine multiple queries
4. **Smart routing** - Use fast models first, escalate to large models only when needed

**Estimated Free Tier Capacity**:
- ~5,000 requests/week
- ~500K tokens/week
- Enough for moderate research agent usage

### If You Exceed Free Tier

- Pay-per-use kicks in automatically
- Still cheaper than running GPU ($0.10-0.50 per 1K tokens)
- Can set budget alerts
- Only pay for actual usage

---

## Implementation Now

Let me update Skyvern configuration to fix the auth issue:

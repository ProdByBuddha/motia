SuperQwen Remote GPU (Qwen3:8B) – Quick Guide

Environment
- export OLLAMA_HOST=https://genuine-shepherd-decent.ngrok-free.app
- export OLLAMA_BASE_URL=https://genuine-shepherd-decent.ngrok-free.app
- export OLLAMA_MODEL=qwen3:8b
- export SUPERQWEN_ENABLE_TOOLS=1
- export SUPERQWEN_TOOLS_JSON=/opt/motia/agents/superqwen/.qwen/tools.json

Python (SuperQwen) smoke test
- scp scripts/sq_test.py vps:/tmp/sq_test.py
- ssh vps 'PYTHONPATH=/opt/motia/agents/shared \
  OLLAMA_MODEL=qwen3:8b \
  SUPERQWEN_OLLAMA_BASE_URL=$OLLAMA_HOST \
  SUPERQWEN_ENABLE_TOOLS=1 \
  SUPERQWEN_TOOLS_JSON=/opt/motia/agents/superqwen/.qwen/tools.json \
  /opt/motia/venv/bin/python /tmp/sq_test.py'

Node (Parlant) smoke test
- scp scripts/sq_node_test.js vps:/tmp/sq_node_test.js
- ssh vps 'export OLLAMA_HOST=$OLLAMA_HOST OLLAMA_MODEL=qwen3:8b; node /tmp/sq_node_test.js'

Deploy updated Parlant bridge
- scp superqwen-parlant.js vps:/tmp/superqwen-parlant.js
- ssh vps 'sudo mv /tmp/superqwen-parlant.js /opt/motia/agents/parlant/superqwen-parlant.js && sudo chown root:root /opt/motia/agents/parlant/superqwen-parlant.js && sudo chmod 644 /opt/motia/agents/parlant/superqwen-parlant.js'

Central tools registry
- scp tools.superqwen.json vps:/tmp/tools.superqwen.json
- ssh vps 'sudo mv /tmp/tools.superqwen.json /opt/motia/agents/superqwen/.qwen/tools.json && sudo chown root:root /opt/motia/agents/superqwen/.qwen/tools.json && sudo chmod 644 /opt/motia/agents/superqwen/.qwen/tools.json'

Server persistence (recommended)
- ssh vps 'grep -q "^export OLLAMA_MODEL=qwen3:8b$" /home/buddha/.bashrc || echo "export OLLAMA_MODEL=qwen3:8b" | sudo tee -a /home/buddha/.bashrc > /dev/null'
- ssh vps 'grep -q "^export OLLAMA_HOST=" /home/buddha/.bashrc || echo "export OLLAMA_HOST=$OLLAMA_HOST" | sudo tee -a /home/buddha/.bashrc > /dev/null'
- ssh vps 'grep -q "^export OLLAMA_BASE_URL=" /home/buddha/.bashrc || echo "export OLLAMA_BASE_URL=$OLLAMA_HOST" | sudo tee -a /home/buddha/.bashrc > /dev/null'
- ssh vps 'grep -q "^export SUPERQWEN_ENABLE_TOOLS=1$" /home/buddha/.bashrc || echo "export SUPERQWEN_ENABLE_TOOLS=1" | sudo tee -a /home/buddha/.bashrc > /dev/null'
- ssh vps 'grep -q "^export SUPERQWEN_TOOLS_JSON=" /home/buddha/.bashrc || echo "export SUPERQWEN_TOOLS_JSON=/opt/motia/agents/superqwen/.qwen/tools.json" | sudo tee -a /home/buddha/.bashrc > /dev/null'

Life OS .env (optional)
- ssh vps 'grep -q "^OLLAMA_MODEL=" /home/buddha/life-os/backend/.env || echo "OLLAMA_MODEL=qwen3:8b" | sudo tee -a /home/buddha/life-os/backend/.env > /dev/null'

Notes
- The Python provider and Node bridge both attach OpenAI tools to /v1/chat/completions and default to model qwen3:8b; override with OLLAMA_MODEL if needed.
- On API errors, both paths report a readable error instead of crashing.

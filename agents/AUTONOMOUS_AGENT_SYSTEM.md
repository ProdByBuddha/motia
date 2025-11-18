# Autonomous Agent System

**Multi-Platform Dev Agency with Cross-Platform Persistent Memory**

---

## Overview

A complete autonomous AI agent system that works like a dev agency:

- **Multiple specialized agents** work together on projects
- **You are the lead** - agents report to you and request approval for critical actions
- **Multi-platform access** - Control agents via Discord or Telegram
- **Persistent memory** - Conversations persist across platforms through Redis
- **Auto-running** - Everything starts automatically on system boot
- **SuperQwen-powered** - 13 expert personas and 17 command workflows

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  YOU (The Lead)                              │
│         Discord ←→ Redis ←→ Telegram                         │
└────────────────────┬────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │   Agent Coordinator  │
          │  (Task Delegation)   │
          └──────────┬───────────┘
                     │
    ┌────────────────┼────────────────────────────┐
    │                │                            │
┌───┴────┐    ┌─────┴──────┐            ┌───────┴────┐
│Architect│    │Backend Dev │   ...      │   QA       │
│(Design) │    │(Implement) │            │  (Test)    │
└────────┘    └────────────┘            └────────────┘
    │                │                            │
    └────────────────┴────────────────────────────┘
                     │
            ┌────────┴─────────┐
            │ SuperQwen Framework │
            │  13 Personas        │
            │  17 Commands        │
            └─────────────────────┘
```

---

## Agent Team

Your autonomous dev agency includes:

| Agent | Role | SuperQwen Persona |
|-------|------|-------------------|
| **Architect** | System design and architecture | system-architect |
| **Backend Developer** | Backend implementation | backend-architect |
| **Frontend Developer** | UI/UX implementation | frontend-architect |
| **DevOps Engineer** | Infrastructure & deployment | devops-architect |
| **QA Engineer** | Testing and quality | quality-engineer |
| **Security Engineer** | Security audits | security-engineer |
| **Technical Writer** | Documentation | technical-writer |

---

## Setup Instructions

### 1. Prerequisites

✅ Already installed:
- Ollama (running)
- Redis (port 6380)
- SuperQwen Framework
- Python environment with dependencies

### 2. Get Bot Tokens

#### Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Give it a name (e.g., "Agent Coordinator")
4. Go to "Bot" section
5. Click "Reset Token" and copy the token
6. Enable these intents:
   - Message Content Intent
   - Server Members Intent
7. Go to "OAuth2" → "URL Generator"
8. Select scopes: `bot`, `applications.commands`
9. Select bot permissions: `Administrator` (or specific permissions)
10. Copy the generated URL and invite bot to your server

#### Telegram Bot

1. Open Telegram and message @BotFather
2. Send `/newbot`
3. Follow prompts to create bot
4. Copy the token BotFather gives you

### 3. Configure Bot Tokens

Create environment file:

```bash
sudo mkdir -p /etc/motia
sudo nano /etc/motia/bot-tokens.env
```

Add your tokens:

```bash
DISCORD_BOT_TOKEN=your_discord_token_here
TELEGRAM_BOT_TOKEN=your_telegram_token_here
```

Save and set permissions:

```bash
sudo chmod 600 /etc/motia/bot-tokens.env
```

### 4. Install and Start Services

```bash
# Install systemd services
sudo cp /tmp/agent-bots.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable agent-bots.service
sudo systemctl enable superqwen-parlant.service

# Start services
sudo systemctl start superqwen-parlant.service
sudo systemctl start agent-bots.service

# Check status
sudo systemctl status superqwen-parlant.service
sudo systemctl status agent-bots.service
```

### 5. View Logs

```bash
# Agent system logs
sudo journalctl -u agent-bots.service -f

# TypeScript runtime logs
sudo journalctl -u superqwen-parlant.service -f

# Both together
sudo journalctl -u agent-bots.service -u superqwen-parlant.service -f
```

---

## Usage Guide

### Discord Commands

Once bot is invited to your server:

```
!agent help_agent              # Show all commands
!agent build <description>     # Have agents build an app
!agent task <role> <action> <description>  # Create specific task
!agent approve <task_id>       # Approve a pending task
!agent status <task_id>        # Check task status
!agent pending                 # List pending approvals
!agent talk <role> <message>   # Chat with an agent
!agent agents                  # List all agents
```

**Example:**
```
!agent build Create a REST API for a todo app with PostgreSQL and JWT auth
!agent talk architect What technologies do you recommend for this project?
!agent approve task_abc123
```

### Telegram Commands

Start chat with your bot on Telegram:

```
/start                         # Initialize and set yourself as lead
/help                          # Show all commands
/build <description>           # Have agents build an app
/task <role> <action> <description>  # Create specific task
/approve <task_id>             # Approve a pending task
/status <task_id>              # Check task status
/pending                       # List pending approvals
/talk <role> <message>         # Chat with an agent
/agents                        # List all agents
```

**Example:**
```
/build Create a REST API for a todo app with PostgreSQL and JWT auth
/talk devops How should we deploy this app?
/approve task_abc123
```

### How It Works

1. **You create a high-level task**: "Build a todo app"

2. **Architect designs the system**:
   - Analyzes requirements
   - Creates architecture
   - Delegates subtasks to other agents

3. **Agents work autonomously**:
   - Backend Dev implements API
   - Frontend Dev builds UI
   - DevOps sets up infrastructure
   - Agents communicate with each other as needed

4. **Approval workflow**:
   - Safe actions (reading, analysis, planning) execute automatically
   - Moderate actions (file changes, config) request approval
   - Destructive actions (deletions, deployments) require explicit approval

5. **You stay informed**:
   - Agents notify you of progress
   - You approve critical actions
   - Check status anytime on any platform

---

## Task Types and Approval Levels

### Safe (Auto-Execute)
- Code analysis
- Documentation reading
- Design and planning
- Test execution

### Moderate (Request Approval)
- File modifications
- Configuration changes
- Database schema updates
- Package installations

### Destructive (Require Explicit Approval)
- File/directory deletions
- Production deployments
- Database migrations
- Infrastructure changes

---

## Agent Roles

Use these role identifiers in commands:

| Role Identifier | Agent |
|----------------|-------|
| `architect` | System Architect |
| `backend_dev` | Backend Developer |
| `frontend_dev` | Frontend Developer |
| `devops` | DevOps Engineer |
| `qa` | QA Engineer |
| `security` | Security Engineer |
| `tech_writer` | Technical Writer |

---

## Cross-Platform Memory

**Your conversations persist across platforms!**

- Start a conversation on Discord
- Continue it on Telegram
- Agents remember the full context
- All powered by Redis

**How it works:**
1. All conversations stored in Redis
2. Each agent maintains conversation history
3. Platform-agnostic message IDs
4. Cross-platform user identification

---

## Advanced Features

### Agent-to-Agent Communication

Agents can communicate with each other:

```python
# Architect asks Backend Dev about database design
response = await coordinator.send_message_to_agent(
    from_agent=AgentRole.ARCHITECT,
    to_agent=AgentRole.BACKEND_DEV,
    message="What database schema do you recommend for this app?"
)
```

### Conversation History

View conversation between agents:

```python
history = await coordinator.get_agent_conversation_history(
    AgentRole.ARCHITECT,
    AgentRole.BACKEND_DEV
)
```

### Task Hierarchy

Tasks can create subtasks:

```
Parent Task: "Build Todo App"
├─ Subtask 1: "Design database schema" (backend_dev)
├─ Subtask 2: "Create API endpoints" (backend_dev)
├─ Subtask 3: "Build UI components" (frontend_dev)
└─ Subtask 4: "Write tests" (qa)
```

---

## Example Workflow

Let's say you want to build a new feature:

### Discord

```
You: !agent build Add user authentication with JWT to our API

Bot: 🏗️ Building Application
     Task ID: task_a1b2c3d4
     Status: In Progress

     Process:
     1. ✅ Architect designs system
     2. ⏳ Agents implement components
     3. ⏳ QA tests
     4. ⏳ DevOps deploys

(5 minutes later)

Bot: ✅ Task Complete
     Task: Build: Add user authentication
     Assigned to: architect

     Result shows design with subtasks

Bot: 🔔 Approval Required
     Task: Implement JWT middleware
     Type: moderate
     Assigned to: backend_dev
     Description: Create JWT middleware for Express

You: !agent approve task_e5f6g7h8

Bot: ✅ Task approved and executing

(10 minutes later)

Bot: ✅ Task Complete
     All authentication components implemented

You: !agent status task_a1b2c3d4

Bot: 📊 Task Status
     All subtasks completed:
     ✅ JWT middleware
     ✅ Authentication routes
     ✅ Tests

     Ready for deployment
```

### Continue on Telegram

```
You: /pending

Bot: ⏳ Pending Approvals (1 task)

     task_i9j0k1l2
     Deploy authentication to production
     Role: devops | Type: destructive

You: /approve task_i9j0k1l2

Bot: ✅ Task approved and executing

(deployment happens)

Bot: ✅ Task Complete
     Authentication deployed to production
```

---

## Monitoring and Debugging

### Check System Status

```bash
# All services
sudo systemctl status agent-bots.service superqwen-parlant.service

# Redis connection
redis-cli -p 6380 ping

# View task queue
redis-cli -p 6380 hgetall tasks
```

### Debugging

```bash
# Live logs
sudo journalctl -u agent-bots.service -f

# Recent errors
sudo journalctl -u agent-bots.service -p err --since "1 hour ago"

# Full logs
sudo journalctl -u agent-bots.service --no-pager
```

### Restart Services

```bash
# Restart bot system
sudo systemctl restart agent-bots.service

# Restart TypeScript runtime
sudo systemctl restart superqwen-parlant.service

# Restart all
sudo systemctl restart agent-bots.service superqwen-parlant.service
```

---

## Troubleshooting

### Bot not responding

```bash
# Check if services are running
sudo systemctl status agent-bots.service

# Check logs for errors
sudo journalctl -u agent-bots.service -n 50

# Verify bot tokens
cat /etc/motia/bot-tokens.env

# Test Redis connection
redis-cli -p 6380 ping
```

### Agents not executing tasks

```bash
# Check Ollama is running
docker ps | grep ollama

# Check SuperQwen Parlant runtime
sudo systemctl status superqwen-parlant.service

# View coordination logs
sudo journalctl -u agent-bots.service | grep AgentCoordinator
```

### Memory not persisting

```bash
# Check Redis is running
sudo systemctl status redis

# Test Redis writes
redis-cli -p 6380 set test_key test_value
redis-cli -p 6380 get test_key

# View stored conversations
redis-cli -p 6380 keys "agent_conv:*"
```

---

## Security Considerations

1. **Bot Token Security**:
   - Stored in `/etc/motia/bot-tokens.env` with 600 permissions
   - Never commit tokens to git
   - Rotate tokens if compromised

2. **Approval Workflow**:
   - Destructive actions always require approval
   - Only the lead user can approve
   - All actions logged in Redis

3. **Redis Security**:
   - Runs on localhost only
   - No external access
   - Data encrypted at rest (optional)

4. **Agent Permissions**:
   - Agents run with configured user permissions
   - Filesystem access controlled
   - Network access monitored

---

## Architecture Details

### Components

1. **Agent Coordinator** (`agent_coordinator.py`)
   - Central orchestration
   - Task delegation
   - Approval workflow
   - Memory management

2. **Discord Bot** (`discord_bot.py`)
   - Discord.py integration
   - Command handlers
   - Reaction-based approvals

3. **Telegram Bot** (`telegram_bot.py`)
   - python-telegram-bot integration
   - Command handlers
   - Inline button approvals

4. **Unified Orchestrator** (`unified_agent_orchestrator.py`)
   - Python and TypeScript runtime coordination
   - Intelligent task routing
   - Performance optimization

5. **SuperQwen Integration**
   - 13 expert personas
   - 17 command workflows
   - Conversational and background modes

---

## Performance

### Latency

| Operation | Latency | Notes |
|-----------|---------|-------|
| Message response | <1s | Via Redis cache |
| Task creation | <500ms | Async execution |
| Agent analysis | 30-60s | Ollama inference |
| Approval notification | <2s | Multi-platform |

### Resource Usage

- **Memory**: ~500MB per agent (Ollama)
- **CPU**: Varies with Ollama workload
- **Redis**: ~100MB for typical workload
- **Network**: Minimal (local Ollama + bot APIs)

---

## Future Enhancements

Planned features:

- [ ] Web dashboard
- [ ] Slack integration
- [ ] Voice commands
- [ ] Mobile app
- [ ] Agent performance metrics
- [ ] Custom agent creation
- [ ] Multi-project support
- [ ] Team collaboration features

---

## Summary

✅ **Complete System**:
- Multi-agent coordination
- Discord and Telegram bots
- Cross-platform persistent memory
- Approval workflow
- Auto-start on boot
- SuperQwen Framework integration

✅ **Easy to Use**:
- Natural language commands
- Intuitive approval system
- Real-time notifications
- Status tracking

✅ **Production Ready**:
- Systemd services
- Logging and monitoring
- Error recovery
- Security best practices

**Your autonomous dev agency is ready to build!** 🚀

import asyncio
import json
import uuid
import time
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Redis (async) client (optional)
try:
    import redis.asyncio as aioredis  # redis-py >= 4.2
except Exception:
    aioredis = None

import aiohttp

# Tools-aware provider (OpenAI-compatible)
from superqwen_ollama import SuperQwenOllama


# =========================
# Public enums
# =========================

class AgentRole(Enum):
    ARCHITECT = "architect"
    BACKEND = "backend"
    FRONTEND = "frontend"
    DEVOPS = "devops"
    QA = "qa"
    SECURITY = "security"
    TECH_WRITER = "tech_writer"
    PM = "pm"
    RESEARCH = "research"
    SOCRATIC_MENTOR = "socratic_mentor"
    # Common variants some users may type
    BACKEND_DEV = "backend_dev"
    FRONTEND_DEV = "frontend_dev"


class ActionType(Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DESTRUCTIVE = "destructive"


# =========================
# Role aliasing
# =========================

ROLE_ALIAS: Dict[str, str] = {
    "backend_dev": "backend",
    "frontend_dev": "frontend",
    "techwriter": "tech_writer",
    "tech-writer": "tech_writer",
    "project_manager": "pm",
    "product_manager": "pm",
    "program_manager": "pm",
    "socratic-mentor": "socratic_mentor",
    # canonical passthroughs
    "architect": "architect",
    "backend": "backend",
    "frontend": "frontend",
    "devops": "devops",
    "qa": "qa",
    "security": "security",
    "tech_writer": "tech_writer",
    "pm": "pm",
    "research": "research",
    "socratic_mentor": "socratic_mentor",
}


# =========================
# Task model
# =========================

@dataclass
class Task:
    task_id: str
    title: str
    description: str
    assigned_to: AgentRole
    action_type: ActionType
    created_by: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"  # pending -> in_progress -> completed/failed
    requires_approval: bool = False
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "assigned_to": self.assigned_to.value if isinstance(self.assigned_to, AgentRole) else str(self.assigned_to),
            "action_type": self.action_type.value if isinstance(self.action_type, ActionType) else str(self.action_type),
            "created_by": self.created_by,
            "created_at": self.created_at,
            "status": self.status,
            "requires_approval": self.requires_approval,
            "result": self.result,
        }


# =========================
# AgentCoordinator
# =========================

class AgentCoordinator:
    """
    Orchestrates agents, tasks, approvals, channels (Discord/Telegram), memory (Redis),
    and per-user multi-session conversational state.
    """

    def __init__(self, redis_url: str = "redis://localhost:6380/0"):
        self.redis_url = redis_url
        self.redis_client = None  # async redis
        self.provider: Optional[SuperQwenOllama] = None

        # Channels and lead user
        self.channels: Dict[str, Any] = {}
        self.lead_user_id: Optional[str] = None

        # Task state
        self.tasks: Dict[str, Task] = {}
        self.pending_approvals: List[str] = []

        # Pydantic agent registry (orchestrator fills this elsewhere)
        self.pydantic_agents: Dict[str, Any] = {}
        # AgentRole -> agent mapping for UI/logs (what launcher expects)
        self.agents: Dict[AgentRole, Any] = {}

        # Session state
        # session_id -> {"owner": "platform:user", "name": "<name>", "created_at": iso, "state": {...}, "messages": [...]}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        # "platform:user" -> active session_id
        self.user_active_session: Dict[str, str] = {}

    # ---------- Low-level helpers ----------

    def resolve_role_key(self, role: Any) -> str:
        """Normalize role (enum or str) to orchestrator key."""
        key = role.value if hasattr(role, "value") else str(role)
        key = key.strip().lower().replace("-", "_")
        return ROLE_ALIAS.get(key, key)

    def _user_key(self, platform: str, user_id: str) -> str:
        return f"{platform}:{user_id}"

    def _new_session_id(self) -> str:
        return "sess_" + uuid.uuid4().hex[:10]

    async def _connect_redis(self):
        if aioredis is None:
            print("[AgentCoordinator] Redis not available; continuing without persistence")
            self.redis_client = None
            return
        try:
            self.redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
        except Exception as e:
            print(f"[AgentCoordinator] Redis connection failed ({e}); continuing without persistence")
            self.redis_client = None

    async def _init_orchestrator(self):
        """
        Placeholder: your orchestrator likely populates pydantic_agents itself.
        We ensure canonical keys and build AgentRole mapping for the launcher UI.
        """
        for key in ("architect", "backend", "frontend", "devops", "qa", "security", "tech_writer", "pm", "research", "socratic_mentor"):
            self.pydantic_agents.setdefault(key, object())

        # Instantiate enhanced Pydantic agents where missing
        try:
            from superqwen_pydantic import (
                create_pm_agent_superqwen,
                create_research_agent_superqwen,
                create_socratic_mentor_agent_superqwen,
            )
            if not isinstance(self.pydantic_agents.get("pm"), object):
                pass
            # Only create if current value is a bare placeholder object()
            if isinstance(self.pydantic_agents.get("pm"), object):
                self.pydantic_agents["pm"] = create_pm_agent_superqwen()
            if isinstance(self.pydantic_agents.get("research"), object):
                self.pydantic_agents["research"] = create_research_agent_superqwen()
            if isinstance(self.pydantic_agents.get("socratic_mentor"), object):
                self.pydantic_agents["socratic_mentor"] = create_socratic_mentor_agent_superqwen()
        except Exception as e:
            print(f"[AgentCoordinator] Note: could not instantiate extended Pydantic agents ({e})")

        self.agents = {
            AgentRole.ARCHITECT: self.pydantic_agents.get("architect"),
            AgentRole.BACKEND: self.pydantic_agents.get("backend"),
            AgentRole.FRONTEND: self.pydantic_agents.get("frontend"),
            AgentRole.DEVOPS: self.pydantic_agents.get("devops"),
            AgentRole.QA: self.pydantic_agents.get("qa"),
            AgentRole.SECURITY: self.pydantic_agents.get("security"),
            AgentRole.TECH_WRITER: self.pydantic_agents.get("tech_writer"),
            AgentRole.PM: self.pydantic_agents.get("pm"),
            AgentRole.RESEARCH: self.pydantic_agents.get("research"),
            AgentRole.SOCRATIC_MENTOR: self.pydantic_agents.get("socratic_mentor"),
        }

        self.provider = SuperQwenOllama(mode="conversational")

    async def _post_parlant(self, url: str, action: str, **payload):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"action": action, **payload},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                try:
                    return await resp.json()
                except Exception:
                    text = await resp.text()
                    return {"success": False, "error": f"non-JSON (HTTP {resp.status}) {text[:200]}"}

    # ---------- Public lifecycle ----------

    async def initialize(self):
        await self._connect_redis()
        await self._init_orchestrator()
        print("[AgentCoordinator] Initialized", len(self.pydantic_agents), "agents")

    # ---------- Channels / lead ----------

    def register_channel(self, platform: str, channel_instance: Any):
        self.channels[platform] = channel_instance
        print(f"[AgentCoordinator] Registered channel: {platform}")

    def set_lead_user(self, user_id: str):
        self.lead_user_id = user_id
        print(f"[AgentCoordinator] Lead user set: {user_id}")

    # ---------- Tasks / approvals ----------

    async def create_task(
        self,
        title: str,
        description: str,
        assigned_to: AgentRole,
        action_type: ActionType,
        created_by: str,
        requires_approval: Optional[bool] = None,
    ) -> Task:
        """Create a task. Defaults to requiring approval for destructive actions."""
        role_key = self.resolve_role_key(assigned_to)
        if role_key not in self.pydantic_agents:
            raise ValueError(f"Unknown Pydantic agent: {role_key}")

        if requires_approval is None:
            requires_approval = action_type == ActionType.DESTRUCTIVE

        task_id = "task_" + uuid.uuid4().hex[:8]
        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            assigned_to=assigned_to if isinstance(assigned_to, AgentRole) else AgentRole(assigned_to),
            action_type=action_type if isinstance(action_type, ActionType) else ActionType(action_type),
            created_by=created_by,
            requires_approval=requires_approval,
            status="pending" if requires_approval else "in_progress",
        )
        self.tasks[task_id] = task
        if task.requires_approval and task_id not in self.pending_approvals:
            self.pending_approvals.append(task_id)

        print(f"[AgentCoordinator] Created task: {task_id} ({title})")
        return task

    async def approve_task(self, task_id: str, approver_id: str):
        """Approve a pending task and move it to in_progress"""
        if task_id not in self.tasks:
            raise ValueError(f"Task not found: {task_id}")
        task = self.tasks[task_id]
        if not task.requires_approval:
            return
        if task_id in self.pending_approvals:
            self.pending_approvals.remove(task_id)
        task.requires_approval = False
        task.status = "in_progress"
        print(f"[AgentCoordinator] Task approved by {approver_id}: {task_id}")

    async def get_pending_approvals(self) -> List[Task]:
        return [self.tasks[tid] for tid in self.pending_approvals if tid in self.tasks]

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        if task_id not in self.tasks:
            raise ValueError(f"Task not found: {task_id}")
        return self.tasks[task_id].to_dict()

    # ---------- Redis-backed agent conversations (optional) ----------

    async def log_agent_message(
        self,
        from_agent: AgentRole,
        to_agent: AgentRole,
        message: str,
        response: str,
    ):
        """Persist a conversation hop between two agents."""
        if not self.redis_client:
            return
        a_from = self.resolve_role_key(from_agent)
        a_to = self.resolve_role_key(to_agent)
        conv_key = f"agent_conv:{a_from}:{a_to}"
        await self.redis_client.rpush(
            conv_key,
            json.dumps(
                {
                    "from": a_from,
                    "to": a_to,
                    "message": message,
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )

    async def get_agent_conversation_history(
        self,
        agent1: AgentRole,
        agent2: AgentRole,
    ) -> List[Dict[str, Any]]:
        if not self.redis_client:
            return []
        a1 = self.resolve_role_key(agent1)
        a2 = self.resolve_role_key(agent2)
        conv_key = f"agent_conv:{a1}:{a2}"
        messages = await self.redis_client.lrange(conv_key, 0, -1)
        return [json.loads(msg) for msg in messages]

    # =========================
    # Sessions (multi-thread)
    # =========================

    def _get_or_create_default_session(self, platform: str, user_id: str) -> str:
        """Return active session for user or create a default 'default' session."""
        uk = self._user_key(platform, user_id)
        sess_id = self.user_active_session.get(uk)
        if sess_id and sess_id in self.sessions:
            return sess_id
        # Create default
        sess_id = self._new_session_id()
        self.sessions[sess_id] = {
            "owner": uk,
            "name": "default",
            "created_at": datetime.utcnow().isoformat(),
            "state": {"persona": None, "mode": "conversational"},
            "messages": [],
        }
        self.user_active_session[uk] = sess_id
        return sess_id

    def list_sessions(self, platform: str, user_id: str) -> List[Dict[str, Any]]:
        """List sessions owned by user (metadata only)."""
        uk = self._user_key(platform, user_id)
        out = []
        for sid, meta in self.sessions.items():
            if meta.get("owner") == uk:
                out.append(
                    {
                        "id": sid,
                        "name": meta.get("name"),
                        "created_at": meta.get("created_at"),
                        "active": self.user_active_session.get(uk) == sid,
                        "messages": len(meta.get("messages", [])),
                    }
                )
        return sorted(out, key=lambda x: (not x["active"], x["created_at"]))

    def create_session(self, platform: str, user_id: str, name: str) -> Dict[str, Any]:
        uk = self._user_key(platform, user_id)
        # ensure no duplicate name for owner
        for meta in self.sessions.values():
            if meta.get("owner") == uk and meta.get("name") == name:
                raise ValueError("Session name already exists")
        sid = self._new_session_id()
        self.sessions[sid] = {
            "owner": uk,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            "state": {"persona": None, "mode": "conversational"},
            "messages": [],
        }
        # make newly created session active
        self.user_active_session[uk] = sid
        return {"id": sid, "name": name}

    def use_session(self, platform: str, user_id: str, selector: str) -> Dict[str, Any]:
        """
        Switch active session by name or id.
        Returns metadata of active session.
        """
        uk = self._user_key(platform, user_id)
        # Find by id first
        if selector in self.sessions and self.sessions[selector].get("owner") == uk:
            self.user_active_session[uk] = selector
            meta = self.sessions[selector]
            return {"id": selector, "name": meta["name"]}
        # Find by name
        for sid, meta in self.sessions.items():
            if meta.get("owner") == uk and meta.get("name") == selector:
                self.user_active_session[uk] = sid
                return {"id": sid, "name": selector}
        raise ValueError("Session not found")

    def rename_session(self, platform: str, user_id: str, old_name: str, new_name: str) -> Dict[str, Any]:
        uk = self._user_key(platform, user_id)
        # name not already in use
        for meta in self.sessions.values():
            if meta.get("owner") == uk and meta.get("name") == new_name:
                raise ValueError("Target session name already exists")
        # find old
        for sid, meta in self.sessions.items():
            if meta.get("owner") == uk and meta.get("name") == old_name:
                meta["name"] = new_name
                return {"id": sid, "name": new_name}
        raise ValueError("Session not found for rename")

    def close_session(self, platform: str, user_id: str, selector: str) -> str:
        """Delete a session by name or id; switch to default if active."""
        uk = self._user_key(platform, user_id)
        # resolve id
        target_id = None
        if selector in self.sessions and self.sessions[selector].get("owner") == uk:
            target_id = selector
        else:
            for sid, meta in self.sessions.items():
                if meta.get("owner") == uk and meta.get("name") == selector:
                    target_id = sid
                    break
        if not target_id:
            raise ValueError("Session not found")

        # if active, move to default
        if self.user_active_session.get(uk) == target_id:
            del self.user_active_session[uk]
            self._get_or_create_default_session(platform, user_id)

        del self.sessions[target_id]
        return target_id

    # ---------- Natural-language handler with tool execution ----------

    async def _post_chat(
        self,
        base_url: str,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ):
        url = base_url.rstrip("/") + "/v1/chat/completions"
        payload: Dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if isinstance(max_tokens, int) and max_tokens > 0:
            payload["max_tokens"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except Exception:
                    return {"error": {"message": f"non-JSON (HTTP {resp.status})"}, "raw": text}
                if resp.status != 200 or "choices" not in data:
                    return {"error": data.get("error") or {"message": text[:200]}, "raw": data}
                return data

    def _exec_tool(self, name: str, args: Dict[str, Any], sess_id: str, provider: SuperQwenOllama) -> str:
        meta = self.sessions.get(sess_id, {})
        state = meta.setdefault("state", {"persona": None, "mode": "conversational"})
        # Local tool execution
        try:
            if name == "ping":
                return json.dumps({"ok": True, "echo": args.get("msg")})
            if name == "set_persona":
                persona = args.get("persona")
                state["persona"] = persona
                return json.dumps({"ok": True, "persona": persona})
            if name == "set_mode":
                mode = args.get("mode")
                if mode in ("conversational", "background"):
                    state["mode"] = mode
                    return json.dumps({"ok": True, "mode": mode})
                return json.dumps({"ok": False, "error": "invalid mode"})
            if name == "get_stats":
                return json.dumps({"ok": True, "mode": state.get("mode")})
            if name == "clear_conversation":
                meta["messages"] = []
                return json.dumps({"ok": True, "cleared": True})
            if name == "execute_command":
                cmd = args.get("command")
                ctx = args.get("context", "")
                try:
                    res = provider.execute_command_sync(cmd, ctx, max_tokens=4096)
                    return json.dumps({"ok": True, "result": res})
                except Exception as e:
                    return json.dumps({"ok": False, "error": str(e)})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

        return json.dumps({"ok": False, "error": f"unsupported tool: {name}"})

    async def handle_natural_message(
        self,
        platform: str,
        user_id: str,
        text: str,
        session: Optional[str] = None,
    ) -> str:
        """
        Natural language entrypoint:
        - Uses active session (or provided session id) for per-thread memory
        - Calls OpenAI-compatible chat with tools
        - Executes tool_calls and returns final assistant reply
        """
        prefer_parlant = os.environ.get("PREFER_PARLANT_BRIDGE", "1") == "1"
        bridge_url = os.environ.get("PARLANT_BRIDGE_URL", "http://127.0.0.1:3010")

        # resolve session
        if session and session in self.sessions:
            sess_id = session
        else:
            sess_id = self._get_or_create_default_session(platform, user_id)

        if prefer_parlant:
            # Use session-aware Parlant bridge
            data = await self._post_parlant(bridge_url, "chat", message=text, sessionId=sess_id)
            if isinstance(data, dict) and data.get("success"):
                res = data.get("result") or {}
                out = {"text": (res.get("content") or "").strip() or "[no content]"}
                notifications = res.get("notifications") or []
                if notifications:
                    out["notifications"] = notifications
                return out
            # error path
            err = (data.get("error") if isinstance(data, dict) else data) or "unknown error"
            return {"text": f"[error] {err}"}

        # Local provider path
        meta = self.sessions[sess_id]
        messages = meta.setdefault("messages", [])
        state = meta.setdefault("state", {"persona": None, "mode": "conversational"})

        provider = self.provider
        base_url, model = provider.base_url, provider.model_name
        tools = getattr(provider, "tools", [])

        # Ensure persona system message at start if set
        if state.get("persona") and (not messages or messages[0].get("role") != "system"):
            messages.insert(0, {"role": "system", "content": f"You are now acting as: {state['persona']}"})

        # Append user message
        messages.append({"role": "user", "content": text})

        # First call
        t0 = time.perf_counter()
        data = await self._post_chat(base_url, model, messages, tools, max_tokens=1024)
        t1 = time.perf_counter()
        print(f"[Coordinator] chat round1 {t1 - t0:.2f}s")
        if data.get("error"):
            return f"[error] {data['error'].get('message', 'unknown error')}"

        choice = data["choices"][0]
        message_obj = choice.get("message", {})
        content = message_obj.get("content")
        tool_calls = message_obj.get("tool_calls") or []

        if content:
            messages.append({"role": "assistant", "content": content})
            if not tool_calls:
                return content

        # Execute tools
        follow_tool_messages: List[Dict[str, Any]] = []
        for call in tool_calls:
            func = (call.get("function") or {})
            name = func.get("name")
            args_str = func.get("arguments") or "{}"
            try:
                args = json.loads(args_str)
            except Exception:
                args = {}
            result = self._exec_tool(name or "", args, sess_id, provider)
            follow_tool_messages.append({"role": "tool", "content": result})

        if follow_tool_messages:
            messages.extend(follow_tool_messages)
            # Follow-up call for final assistant message
            t2 = time.perf_counter()
            data2 = await self._post_chat(base_url, model, messages, tools, max_tokens=1024)
            t3 = time.perf_counter()
            print(f"[Coordinator] chat round2 {t3 - t2:.2f}s")
            if data2.get("error"):
                return f"[error] {data2['error'].get('message', 'unknown error')}"
            msg2 = data2["choices"][0].get("message", {})
            content2 = msg2.get("content")
            if content2:
                messages.append({"role": "assistant", "content": content2})
                return content2

        return content or "[no content]"


# =========================
# Factory
# =========================

async def create_agent_coordinator(redis_url: str = "redis://localhost:6380/0") -> AgentCoordinator:
    c = AgentCoordinator(redis_url=redis_url)
    await c.initialize()
    return c

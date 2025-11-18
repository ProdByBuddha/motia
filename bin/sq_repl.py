#!/usr/bin/env python3
"""
SuperQwen conversational REPL with automatic tool-calling and execution.

This wrapper replicates `ollama run` style interaction but sends tools to
the OpenAI-compatible /v1/chat/completions API and auto-executes tool calls.

Usage (examples):
  export OLLAMA_HOST=https://genuine-shepherd-decent.ngrok-free.app
  export OLLAMA_MODEL=qwen3:8b
  export SUPERQWEN_TOOLS_JSON=/opt/motia/agents/superqwen/.qwen/tools.json
  export SUPERQWEN_ENABLE_TOOLS=1
  /opt/motia/venv/bin/python /opt/motia/bin/sq_repl.py

Commands inside REPL:
  /bye                Exit
  /save <path>        Save conversation to JSON
  /load <path>        Load conversation from JSON

Notes:
  - Tools are auto-attached from SUPERQWEN_TOOLS_JSON (or default set)
  - Tool executions are handled locally and fed back into the conversation
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

try:
    import requests
except Exception as e:
    print("This script requires the 'requests' package.\n"
          "Install it in your venv: /opt/motia/venv/bin/pip install requests",
          file=sys.stderr)
    sys.exit(1)


def read_json_file(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def default_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "ping",
                "description": "Echo a message",
                "parameters": {
                    "type": "object",
                    "properties": {"msg": {"type": "string"}},
                    "required": ["msg"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_persona",
                "description": "Activate a SuperQwen agent persona",
                "parameters": {
                    "type": "object",
                    "properties": {"persona": {"type": "string"}},
                    "required": ["persona"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_mode",
                "description": "Switch between conversational and background modes",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "enum": ["conversational", "background"]}
                    },
                    "required": ["mode"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": "Execute a SuperQwen command workflow",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "context": {"type": "string"},
                    },
                    "required": ["command", "context"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_agents",
                "description": "List available SuperQwen agent personas",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_commands",
                "description": "List available SuperQwen commands",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_stats",
                "description": "Get current runtime statistics",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "clear_conversation",
                "description": "Clear the conversation history",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_conversation",
                "description": "Save conversation history to a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "load_conversation",
                "description": "Load conversation history from a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
    ]


def load_tools() -> List[Dict[str, Any]]:
    if (os.environ.get("SUPERQWEN_ENABLE_TOOLS", "1").lower() in ("1", "true", "yes", "on")):
        path = os.environ.get("SUPERQWEN_TOOLS_JSON")
        if path:
            p = Path(path)
            if p.exists():
                data = read_json_file(p)
                if isinstance(data, list):
                    return data
    return default_tools()


def exec_tool(name: str, args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Execute supported tools locally and return a JSON-serializable string result."""
    # Context provides access to agents/commands directories and convo state
    agents_dir: Path = context.get("agents_dir")
    commands_dir: Path = context.get("commands_dir")
    state = context.get("state")

    try:
        if name == "ping":
            return json.dumps({"ok": True, "echo": args.get("msg")})

        if name == "set_persona":
            persona = args.get("persona")
            state["persona"] = persona
            # We'll add a system message in the turn integration
            return json.dumps({"ok": True, "persona": persona})

        if name == "set_mode":
            mode = args.get("mode")
            if mode in ("conversational", "background"):
                state["mode"] = mode
                return json.dumps({"ok": True, "mode": mode})
            return json.dumps({"ok": False, "error": "invalid mode"})

        if name == "execute_command":
            # Stub: you can route to your command system here
            return json.dumps({
                "ok": True,
                "command": args.get("command"),
                "context": args.get("context"),
                "note": "command execution is stubbed in REPL"
            })

        if name == "list_agents":
            names = []
            if agents_dir and agents_dir.exists():
                for f in agents_dir.glob("*.md"):
                    names.append(f.stem)
            return json.dumps({"ok": True, "agents": sorted(names)})

        if name == "list_commands":
            names = []
            if commands_dir and commands_dir.exists():
                for f in commands_dir.glob("*.toml"):
                    names.append(f.stem)
            return json.dumps({"ok": True, "commands": sorted(names)})

        if name == "get_stats":
            return json.dumps({
                "ok": True,
                "model": context.get("model"),
                "endpoint": context.get("endpoint"),
                "persona": state.get("persona"),
                "mode": state.get("mode"),
            })

        if name == "clear_conversation":
            state["messages"].clear()
            return json.dumps({"ok": True, "cleared": True})

        if name == "save_conversation":
            path = args.get("path")
            if not path:
                return json.dumps({"ok": False, "error": "missing path"})
            Path(path).write_text(json.dumps(state.get("messages", []), indent=2))
            return json.dumps({"ok": True, "saved": path})

        if name == "load_conversation":
            path = args.get("path")
            if not path or not Path(path).exists():
                return json.dumps({"ok": False, "error": "missing or invalid path"})
            msgs = json.loads(Path(path).read_text())
            if isinstance(msgs, list):
                state["messages"] = msgs
                return json.dumps({"ok": True, "loaded": path, "count": len(msgs)})
            return json.dumps({"ok": False, "error": "invalid content"})

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})

    return json.dumps({"ok": False, "error": f"unsupported tool: {name}"})


def post_chat(base_url: str, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    resp = requests.post(url, json=payload, timeout=60)
    try:
        data = resp.json()
    except Exception:
        data = {"error": {"message": resp.text[:200]}}
    return data


def main():
    base_url = os.environ.get("SUPERQWEN_OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    tools = load_tools()

    # Discover SuperQwen directories for local tool exec context
    sq_root = Path("/opt/motia/agents/superqwen/.qwen")
    agents_dir = sq_root / "agents"
    commands_dir = sq_root / "commands"

    state = {"persona": None, "mode": "conversational", "messages": []}

    print(f"SuperQwen REPL: model={model} endpoint={base_url}")
    print("Type /bye to exit. Use /save <path>, /load <path> for history.")

    while True:
        try:
            user = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/bye", "/exit", "/quit"):
            break
        if user.startswith("/save "):
            path = user.split(" ", 1)[1].strip()
            try:
                Path(path).write_text(json.dumps(state["messages"], indent=2))
                print(f"Saved conversation to {path}")
            except Exception as e:
                print(f"Save failed: {e}")
            continue
        if user.startswith("/load "):
            path = user.split(" ", 1)[1].strip()
            try:
                msgs = json.loads(Path(path).read_text())
                if isinstance(msgs, list):
                    state["messages"] = msgs
                    print(f"Loaded {len(msgs)} messages from {path}")
                else:
                    print("Invalid file content")
            except Exception as e:
                print(f"Load failed: {e}")
            continue

        # Inject persona as system if set and not already present
        if state["persona"] and (not state["messages"] or state["messages"][0].get("role") != "system"):
            state["messages"].insert(0, {
                "role": "system",
                "content": f"You are now acting as: {state['persona']}"
            })

        state["messages"].append({"role": "user", "content": user})

        # First completion call
        data = post_chat(base_url, model, state["messages"], tools)
        if not isinstance(data, dict) or not data.get("choices"):
            err = (data.get("error", {}) if isinstance(data, dict) else {})
            msg = err.get("message") if isinstance(err, dict) else str(data)
            print(f"[error] {msg}")
            continue

        choice = data["choices"][0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls") or []
        content = message.get("content")
        if content:
            print(content)
            state["messages"].append({"role": "assistant", "content": content})

        # Handle tool calls (execute locally and follow-up)
        if tool_calls:
            follow_tool_messages: List[Dict[str, Any]] = []
            for call in tool_calls:
                func = (call.get("function") or {})
                name = func.get("name")
                args_str = func.get("arguments") or "{}"
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}
                result = exec_tool(name or "", args, {
                    "agents_dir": agents_dir,
                    "commands_dir": commands_dir,
                    "state": state,
                    "model": model,
                    "endpoint": base_url,
                })
                # As per OpenAI format, include tool role message
                follow_tool_messages.append({
                    "role": "tool",
                    "content": result,
                    # tool_call_id is optional for many server impls; omit for simplicity
                })

            state["messages"].extend(follow_tool_messages)
            # Second completion after tool execution
            data2 = post_chat(base_url, model, state["messages"], tools)
            if isinstance(data2, dict) and data2.get("choices"):
                msg2 = data2["choices"][0].get("message", {})
                content2 = msg2.get("content")
                if content2:
                    print(content2)
                    state["messages"].append({"role": "assistant", "content": content2})
            else:
                err2 = (data2.get("error", {}) if isinstance(data2, dict) else {})
                msg2 = err2.get("message") if isinstance(err2, dict) else str(data2)
                print(f"[error] {msg2}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()


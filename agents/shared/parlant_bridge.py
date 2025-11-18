"""
Python Bridge to SuperQwen-Enhanced Parlant (Node.js/TypeScript)

Enables Python code to interact with Parlant conversational AI agents
via HTTP bridge to Node.js runtime.
"""

import json
import asyncio
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path

import aiohttp
import os

BRIDGE_URL = os.getenv('PARLANT_BRIDGE_URL')
BRIDGE_PORT = int(os.getenv('PARLANT_BRIDGE_PORT', '3010'))

class ParlantBridge:
    """
    Python bridge to SuperQwen-enhanced Parlant running in Node.js

    Features:
    - Async communication with Node.js Parlant server
    - Conversation management
    - Persona activation
    - Command execution
    - Automatic server lifecycle management
    """

    def __init__(
        self,
        port: int = 3010,
        auto_start: bool = True,
        parlant_script: str = "/opt/motia/agents/parlant/superqwen-parlant.js"
    ):
        """
        Initialize Parlant bridge

        Args:
            port: HTTP server port
            auto_start: Automatically start Node.js server if not running
            parlant_script: Path to superqwen-parlant.js
        """
        self.parlant_script = parlant_script
        self.port = int(os.getenv('PARLANT_BRIDGE_PORT', str(port)))
        self.base_url = os.getenv('PARLANT_BRIDGE_URL') or f"http://127.0.0.1:{self.port}"
        self.auto_start = auto_start and (os.getenv('PARLANT_BRIDGE_URL') is None)
        self.proc = None

        if auto_start:
            self.start_server()

    def start_server(self):
        """Start Node.js Parlant bridge server"""
        if self.is_server_running():
            print(f"[ParlantBridge] Server already running on port {self.port}")
            return

        if self.auto_start:
            print(f"[ParlantBridge] Starting Node.js server on port {self.port}...")
            env = os.environ.copy()
            env['PORT'] = str(self.port)
            self.proc = subprocess.Popen(
                ["/usr/bin/node", self.parlant_script],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            print(f"[ParlantBridge] Using external Parlant bridge at {self.base_url} (no auto-start)")

        # Wait for server to start
        import time
        for _ in range(10):
            if self.is_server_running():
                print("[ParlantBridge] Server started successfully")
                return
            time.sleep(0.5)

        raise RuntimeError("Failed to start Parlant bridge server")

    def is_server_running(self) -> bool:
        """Check if server is running"""
        try:
            import requests
            response = requests.post(
                self.base_url,
                json={'action': 'getStats'},
                timeout=1
            )
            return response.status_code == 200
        except:
            return False

    def stop_server(self):
        """Stop Node.js server"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            print("[ParlantBridge] Server stopped")

    async def _make_request(self, action: str, **kwargs) -> Dict[str, Any]:
      """Make async HTTP request to Parlant server (env/port aware)."""
      payload = {"action": action, **kwargs}
      timeout = aiohttp.ClientTimeout(total=60)
      async with aiohttp.ClientSession() as session:
          try:
              async with session.post(self.base_url, json=payload, timeout=timeout) as response:
                  text = await response.text()
                  try:
                      data = json.loads(text)
                  except Exception:
                      raise RuntimeError(f"Parlant bridge returned non-JSON (HTTP {response.status}): {text[:200]}")
                  if response.status != 200 or not data.get("success"):
                      raise RuntimeError(f"Parlant error (HTTP {response.status}): {data.get('error') or text[:200]}")
                  return data["result"]
          except aiohttp.ClientError as e:
              raise RuntimeError(f"Parlant bridge request failed: {e}")

    def _make_request_sync(self, action: str, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for _make_request"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._make_request(action, **kwargs))

    async def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Send message to Parlant conversational agent

        Args:
            message: User message
            system_prompt: Optional system prompt override
            max_tokens: Maximum response tokens

        Returns:
            Response with content and metadata
        """
        options = {'maxTokens': max_tokens}
        if system_prompt:
            options['systemPrompt'] = system_prompt

        return await self._make_request('chat', message=message, options=options)

    def chat_sync(self, message: str, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for chat()"""
        return self._make_request_sync('chat', message=message, options=kwargs)

    async def execute_command(
        self,
        command_name: str,
        context: str,
        **options
    ) -> Dict[str, Any]:
        """
        Execute SuperQwen command via Parlant

        Args:
            command_name: Command to execute
            context: Context/prompt for command
            **options: Additional options

        Returns:
            Command execution result
        """
        return await self._make_request(
            'executeCommand',
            command=command_name,
            context=context,
            options=options
        )

    def execute_command_sync(self, command_name: str, context: str, **options) -> Dict[str, Any]:
        """Synchronous wrapper for execute_command()"""
        return self._make_request_sync('executeCommand', command=command_name, context=context, options=options)

    async def set_persona(self, persona_name: str) -> Dict[str, Any]:
        """Activate a SuperQwen persona"""
        return await self._make_request('setPersona', persona=persona_name)

    def set_persona_sync(self, persona_name: str) -> Dict[str, Any]:
        """Synchronous wrapper for set_persona()"""
        return self._make_request_sync('setPersona', persona=persona_name)

    async def clear_conversation(self):
        """Clear conversation history"""
        return await self._make_request('clearConversation')

    def clear_conversation_sync(self):
        """Synchronous wrapper for clear_conversation()"""
        return self._make_request_sync('clearConversation')

    async def get_stats(self) -> Dict[str, Any]:
        """Get Parlant agent statistics"""
        return await self._make_request('getStats')

    def get_stats_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_stats()"""
        return self._make_request_sync('getStats')

    async def list_agents(self) -> List[str]:
        """List available SuperQwen agent personas"""
        result = await self._make_request('listAgents')
        return result['agents']

    def list_agents_sync(self) -> List[str]:
        """Synchronous wrapper for list_agents()"""
        return self._make_request_sync('listAgents')['agents']

    async def list_commands(self) -> List[str]:
        """List available SuperQwen commands"""
        result = await self._make_request('listCommands')
        return result['commands']

    def list_commands_sync(self) -> List[str]:
        """Synchronous wrapper for list_commands()"""
        return self._make_request_sync('listCommands')['commands']

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop server"""
        self.stop_server()


if __name__ == '__main__':
    """Test Parlant bridge"""

    print("=== Parlant Bridge Test ===\n")

    # Initialize bridge (auto-starts server)
    bridge = ParlantBridge(port=3010)

    print("Server stats:")
    stats = bridge.get_stats_sync()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    print("Available agents:", ', '.join(bridge.list_agents_sync()))
    print("Available commands:", ', '.join(bridge.list_commands_sync()))
    print()

    # Test persona activation
    print("Activating python-expert persona...")
    bridge.set_persona_sync("python-expert")

    # Test conversational chat
    print("\nTesting conversational chat...")
    response = bridge.chat_sync("What are SOLID principles in Python?")
    print(f"Response: {response['content'][:300]}...")
    print()

    # Test command execution
    print("Testing command execution...")
    result = bridge.execute_command_sync(
        "explain",
        "Explain how async/await works in Python"
    )
    print(f"Explanation: {result['content'][:300]}...")
    print()

    # Cleanup
    bridge.stop_server()
    print("Test complete!")

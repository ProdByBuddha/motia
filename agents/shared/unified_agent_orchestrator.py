"""
Unified Agent Orchestrator - SuperQwen-Enhanced Multi-Runtime AI System

Orchestrates between:
- Pydantic AI (Python): Structured outputs, CI/CD agents, background tasks
- Parlant (TypeScript/Node.js): Conversational AI, multi-turn dialogue
- SuperQwen Framework: Agent personas, command workflows

Intelligent routing based on task requirements:
- Conversational tasks → Parlant (better at dialogue)
- Structured outputs → Pydantic AI (type-safe models)
- Background async → Either, based on language affinity
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
from enum import Enum

from superqwen_pydantic import SuperQwenPydanticAgent
from parlant_bridge import ParlantBridge


class AgentRuntime(Enum):
    """Agent runtime options"""
    PYTHON = "python"  # Pydantic AI
    TYPESCRIPT = "typescript"  # Parlant
    AUTO = "auto"  # Intelligent routing


class TaskType(Enum):
    """Task classification for routing"""
    CONVERSATIONAL = "conversational"  # Multi-turn dialogue
    STRUCTURED = "structured"  # Pydantic model output
    ANALYSIS = "analysis"  # Code/system analysis
    IMPLEMENTATION = "implementation"  # Code generation
    COMMAND = "command"  # SuperQwen command workflow


class UnifiedAgentOrchestrator:
    """
    Unified orchestrator for Python and TypeScript AI agents

    Intelligently routes tasks to optimal runtime based on:
    - Task type (conversational vs structured)
    - Output requirements (Pydantic model vs text)
    - Performance needs (async background vs interactive)
    - Language affinity (Python code → Pydantic AI, TypeScript → Parlant)
    """

    def __init__(
        self,
        default_runtime: AgentRuntime = AgentRuntime.AUTO,
        enable_parlant: bool = True,
        parlant_port: int = 3000
    ):
        """
        Initialize unified orchestrator

        Args:
            default_runtime: Default agent runtime (AUTO for intelligent routing)
            enable_parlant: Enable Parlant bridge (TypeScript runtime)
            parlant_port: Port for Parlant HTTP bridge
        """
        self.default_runtime = default_runtime
        self.pydantic_agents: Dict[str, SuperQwenPydanticAgent] = {}
        self.parlant_bridge: Optional[ParlantBridge] = None

        # Initialize Parlant bridge if enabled
        if enable_parlant:
            try:
                self.parlant_bridge = ParlantBridge(port=parlant_port, auto_start=True)
                print("[UnifiedOrchestrator] Parlant bridge initialized")
            except Exception as e:
                print(f"[UnifiedOrchestrator] Failed to initialize Parlant: {e}")
                print("  Continuing with Python-only runtime")

        print("[UnifiedOrchestrator] Ready")
        print(f"  Default runtime: {default_runtime.value}")
        print(f"  Parlant enabled: {self.parlant_bridge is not None}")

    def register_pydantic_agent(self, name: str, agent: SuperQwenPydanticAgent):
        """Register a Pydantic AI agent"""
        self.pydantic_agents[name] = agent
        print(f"[UnifiedOrchestrator] Registered Pydantic agent: {name}")

    def _select_runtime(
        self,
        task_type: TaskType,
        prefer_runtime: Optional[AgentRuntime] = None,
        requires_structured_output: bool = False
    ) -> AgentRuntime:
        """
        Intelligently select runtime based on task characteristics

        Args:
            task_type: Type of task
            prefer_runtime: User preference override
            requires_structured_output: Whether task needs Pydantic model output

        Returns:
            Selected runtime
        """
        # User preference override
        if prefer_runtime and prefer_runtime != AgentRuntime.AUTO:
            return prefer_runtime

        # Structured outputs require Python/Pydantic AI
        if requires_structured_output:
            return AgentRuntime.PYTHON

        # Task-based routing
        if task_type == TaskType.CONVERSATIONAL:
            # Parlant excels at multi-turn conversation
            return AgentRuntime.TYPESCRIPT if self.parlant_bridge else AgentRuntime.PYTHON

        elif task_type == TaskType.STRUCTURED:
            # Pydantic AI for type-safe structured outputs
            return AgentRuntime.PYTHON

        elif task_type in [TaskType.ANALYSIS, TaskType.IMPLEMENTATION]:
            # Python for code analysis/generation
            return AgentRuntime.PYTHON

        elif task_type == TaskType.COMMAND:
            # SuperQwen commands work in both runtimes
            return AgentRuntime.PYTHON if not self.parlant_bridge else AgentRuntime.TYPESCRIPT

        # Default fallback
        return AgentRuntime.PYTHON

    async def chat(
        self,
        message: str,
        persona: Optional[str] = None,
        runtime: Optional[AgentRuntime] = None
    ) -> Dict[str, Any]:
        """
        Conversational chat with intelligent runtime selection

        Args:
            message: User message
            persona: Optional SuperQwen persona
            runtime: Force specific runtime

        Returns:
            Response with content and metadata
        """
        selected_runtime = self._select_runtime(
            TaskType.CONVERSATIONAL,
            prefer_runtime=runtime
        )

        if selected_runtime == AgentRuntime.TYPESCRIPT and self.parlant_bridge:
            # Use Parlant for conversation
            if persona:
                await self.parlant_bridge.set_persona(persona)

            response = await self.parlant_bridge.chat(message)
            response['runtime'] = 'typescript'
            return response

        else:
            # Use Pydantic AI conversational mode
            # For this, we need a conversational Pydantic agent
            # Let's use BuildAgent as example with conversational mode
            if 'conversational' not in self.pydantic_agents:
                from superqwen_pydantic import create_build_agent_superqwen
                agent = create_build_agent_superqwen(persona=persona, mode='conversational')
                self.pydantic_agents['conversational'] = agent

            agent = self.pydantic_agents['conversational']
            if persona:
                agent.set_persona(persona)

            content = await agent.run_conversational(message)
            return {
                'content': content,
                'runtime': 'python'
            }

    def chat_sync(self, message: str, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for chat()"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.chat(message, **kwargs))

    async def execute_structured(
        self,
        agent_name: str,
        prompt: str,
        deps: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute task with structured output (Pydantic model)

        Args:
            agent_name: Registered Pydantic agent name
            prompt: Task prompt
            deps: Optional dependencies/context

        Returns:
            Pydantic model instance
        """
        if agent_name not in self.pydantic_agents:
            raise ValueError(f"Unknown Pydantic agent: {agent_name}")

        agent = self.pydantic_agents[agent_name]
        return await agent.run_structured(prompt, deps=deps)

    def execute_structured_sync(self, agent_name: str, prompt: str, **kwargs) -> Any:
        """Synchronous wrapper for execute_structured()"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.execute_structured(agent_name, prompt, **kwargs))

    async def execute_command(
        self,
        command_name: str,
        context: str,
        runtime: Optional[AgentRuntime] = None
    ) -> Dict[str, Any]:
        """
        Execute SuperQwen command workflow

        Args:
            command_name: Command to execute
            context: Context/prompt for command
            runtime: Force specific runtime

        Returns:
            Command execution result
        """
        selected_runtime = self._select_runtime(
            TaskType.COMMAND,
            prefer_runtime=runtime
        )

        if selected_runtime == AgentRuntime.TYPESCRIPT and self.parlant_bridge:
            result = await self.parlant_bridge.execute_command(command_name, context)
            result['runtime'] = 'typescript'
            return result
        else:
            # Use first available Pydantic agent for command execution
            if not self.pydantic_agents:
                raise RuntimeError("No Pydantic agents registered")

            agent = next(iter(self.pydantic_agents.values()))
            content = await agent.execute_command(command_name, context)

            return {
                'content': content,
                'command': command_name,
                'runtime': 'python'
            }

    def execute_command_sync(self, command_name: str, context: str, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for execute_command()"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.execute_command(command_name, context, **kwargs))

    def get_available_agents(self) -> Dict[str, List[str]]:
        """List all available agents across runtimes"""
        agents = {
            'python_pydantic': list(self.pydantic_agents.keys()),
            'typescript_parlant': []
        }

        if self.parlant_bridge:
            agents['typescript_parlant'] = self.parlant_bridge.list_agents_sync()

        return agents

    def get_available_commands(self) -> Dict[str, List[str]]:
        """List all available SuperQwen commands"""
        commands = {
            'python': [],
            'typescript': []
        }

        # Get commands from Pydantic agent
        if self.pydantic_agents:
            agent = next(iter(self.pydantic_agents.values()))
            commands['python'] = agent.provider.list_commands()

        # Get commands from Parlant
        if self.parlant_bridge:
            commands['typescript'] = self.parlant_bridge.list_commands_sync()

        return commands

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        stats = {
            'default_runtime': self.default_runtime.value,
            'pydantic_agents_count': len(self.pydantic_agents),
            'parlant_enabled': self.parlant_bridge is not None,
            'available_runtimes': ['python']
        }

        if self.parlant_bridge:
            stats['available_runtimes'].append('typescript')
            stats['parlant_stats'] = self.parlant_bridge.get_stats_sync()

        return stats

    def shutdown(self):
        """Shutdown orchestrator and cleanup resources"""
        if self.parlant_bridge:
            self.parlant_bridge.stop_server()
        print("[UnifiedOrchestrator] Shutdown complete")


# Example usage and integration
if __name__ == '__main__':
    """Test unified agent orchestrator"""

    print("=== Unified Agent Orchestrator Test ===\n")

    # Initialize orchestrator
    orchestrator = UnifiedAgentOrchestrator(
        default_runtime=AgentRuntime.AUTO,
        enable_parlant=True
    )

    # Register Python Pydantic AI agents
    from superqwen_pydantic import create_build_agent_superqwen, create_test_agent_superqwen

    build_agent = create_build_agent_superqwen(persona="python-expert", mode="background")
    test_agent = create_test_agent_superqwen(persona="quality-engineer", mode="background")

    orchestrator.register_pydantic_agent('build', build_agent)
    orchestrator.register_pydantic_agent('test', test_agent)

    print("Available agents:")
    for runtime, agents in orchestrator.get_available_agents().items():
        print(f"  {runtime}: {', '.join(agents)}")
    print()

    print("Available commands:")
    for runtime, commands in orchestrator.get_available_commands().items():
        print(f"  {runtime}: {', '.join(commands)}")
    print()

    # Test 1: Conversational chat (routes to Parlant if available)
    print("Test 1: Conversational chat...")
    response = orchestrator.chat_sync(
        "Explain the benefits of AI-driven CI/CD",
        persona="devops-architect"
    )
    print(f"Runtime: {response['runtime']}")
    print(f"Response: {response['content'][:200]}...")
    print()

    # Test 2: Structured output (routes to Pydantic AI)
    print("Test 2: Structured build decision...")
    decision = orchestrator.execute_structured_sync(
        'build',
        "Files changed: api.py, tests.py. Should we build?"
    )
    print(f"Decision: {decision}")
    print()

    # Test 3: SuperQwen command (can use either runtime)
    print("Test 3: SuperQwen command execution...")
    result = orchestrator.execute_command_sync(
        "analyze",
        "Analyze build performance bottlenecks"
    )
    print(f"Runtime: {result['runtime']}")
    print(f"Analysis: {result['content'][:200]}...")
    print()

    # Show stats
    print("Orchestrator stats:")
    stats = orchestrator.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Cleanup
    orchestrator.shutdown()

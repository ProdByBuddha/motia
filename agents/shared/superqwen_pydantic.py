"""
SuperQwen-Enhanced Pydantic AI Agent Wrapper

Extends existing Pydantic AI agents with SuperQwen Framework capabilities:
- Persona-enhanced system prompts
- Command workflow execution
- Dual mode operation (conversational/background)
- Conversation history with Redis caching
"""

import os
import asyncio
from typing import Dict, Any, Optional, List, TypeVar, Generic, Union
from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import Agent

from superqwen_ollama import SuperQwenOllama
from redis_cache import AgentCache


OutputT = TypeVar('OutputT', bound=BaseModel)


class SuperQwenPydanticAgent(Generic[OutputT]):
    """
    SuperQwen-enhanced Pydantic AI agent wrapper

    Combines:
    - Pydantic AI structured outputs
    - SuperQwen agent personas
    - SuperQwen command workflows
    - Redis caching for both modes
    - Conversation history management
    """

    def __init__(
        self,
        agent_type: str,
        output_type: type[OutputT],
        base_system_prompt: str,
        superqwen_persona: Optional[str] = None,
        mode: str = "background",
        enable_cache: bool = True
    ):
        """
        Initialize SuperQwen-enhanced Pydantic AI agent

        Args:
            agent_type: Agent identifier (e.g., 'build', 'test', 'deploy')
            output_type: Pydantic model for structured outputs
            base_system_prompt: Base system prompt for the agent
            superqwen_persona: Optional SuperQwen persona to activate
            mode: Operation mode ('conversational' or 'background')
            enable_cache: Enable Redis caching
        """
        self.agent_type = agent_type
        self.output_type = output_type
        self.base_system_prompt = base_system_prompt
        self.mode = mode

        # Initialize SuperQwen Ollama provider
        self.provider = SuperQwenOllama(mode=mode)

        # Initialize Pydantic AI agent
        self.agent = Agent(
            self.provider.get_model(),
            output_type=output_type,
            system_prompt=self._build_enhanced_prompt(superqwen_persona)
        )

        # Initialize cache
        self.cache = AgentCache() if enable_cache else None

        # Activate persona if provided
        if superqwen_persona:
            self.provider.set_persona(superqwen_persona)

        print(f"[SuperQwenPydantic] Initialized {agent_type} agent")
        print(f"  Mode: {mode}")
        print(f"  Persona: {superqwen_persona or 'None'}")
        print(f"  Cache: {'Enabled' if self.cache and self.cache.enabled else 'Disabled'}")

    def _build_enhanced_prompt(self, persona: Optional[str]) -> str:
        """Build enhanced system prompt with optional SuperQwen persona"""
        prompt = self.base_system_prompt

        if persona and persona in self.provider.agents:
            persona_data = self.provider.agents[persona]
            prompt += f"\n\n## SuperQwen Persona: {persona}\n\n"
            prompt += persona_data['content']

        return prompt

    async def run_structured(
        self,
        prompt: str,
        deps: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> OutputT:
        """
        Run agent with structured output (Pydantic model)

        Args:
            prompt: User prompt
            deps: Dependencies/context for the agent
            use_cache: Whether to use Redis cache

        Returns:
            Structured output (Pydantic model instance)
        """
        # Check cache if enabled
        if use_cache and self.cache and self.cache.enabled:
            cache_key = {'prompt': prompt, 'deps': deps, 'type': 'structured'}
            cached = self.cache.get_cached_result(self.agent_type, cache_key)

            if cached:
                result_data = cached.get('result', cached)
                print(f"[SuperQwenPydantic] ✨ Cache HIT for {self.agent_type}")
                return self.output_type(**result_data)

        # Run Pydantic AI agent
        result = await self.agent.run(prompt, deps=deps)

        # Cache result if confidence is high
        if use_cache and self.cache and self.cache.enabled:
            confidence = getattr(result.data, 'confidence', 0.9)  # Default high confidence
            cache_key = {'prompt': prompt, 'deps': deps, 'type': 'structured'}
            self.cache.cache_result(
                self.agent_type,
                cache_key,
                result.data.dict() if hasattr(result.data, 'dict') else result.data.model_dump(),
                confidence=confidence
            )

        return result.data

    def run_structured_sync(self, prompt: str, **kwargs) -> OutputT:
        """Synchronous wrapper for run_structured()"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.run_structured(prompt, **kwargs))

    async def run_conversational(
        self,
        message: str,
        use_cache: bool = False  # Cache less useful in conversational mode
    ) -> str:
        """
        Run agent in conversational mode (unstructured response)

        Args:
            message: User message
            use_cache: Whether to attempt caching (usually False for conversations)

        Returns:
            Text response
        """
        if self.mode != "conversational":
            print("[SuperQwenPydantic] Warning: run_conversational() called in background mode")

        response = await self.provider.chat(message)
        return response['content']

    def run_conversational_sync(self, message: str, **kwargs) -> str:
        """Synchronous wrapper for run_conversational()"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.run_conversational(message, **kwargs))

    async def execute_command(
        self,
        command_name: str,
        context: str,
        structured_output: bool = False
    ) -> Union[str, OutputT]:
        """
        Execute a SuperQwen command workflow

        Args:
            command_name: Command to execute (e.g., 'implement', 'analyze')
            context: Context for the command
            structured_output: Whether to parse output into Pydantic model

        Returns:
            Command result (text or structured)
        """
        result = await self.provider.execute_command(command_name, context)

        if structured_output and self.mode == "background":
            # Try to parse response into Pydantic model
            # This requires the LLM to output JSON matching the model
            try:
                import json
                # Extract JSON from response if wrapped in markdown
                content = result['content']
                if '```json' in content:
                    json_start = content.index('```json') + 7
                    json_end = content.index('```', json_start)
                    json_str = content[json_start:json_end].strip()
                else:
                    json_str = content

                data = json.loads(json_str)
                return self.output_type(**data)
            except Exception as e:
                print(f"[SuperQwenPydantic] Failed to parse structured output: {e}")
                return result['content']
        else:
            return result['content']

    def execute_command_sync(self, command_name: str, context: str, **kwargs) -> Union[str, OutputT]:
        """Synchronous wrapper for execute_command()"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.execute_command(command_name, context, **kwargs))

    def set_mode(self, mode: str):
        """Switch between conversational and background modes"""
        self.provider.set_mode(mode)
        self.mode = mode
        print(f"[SuperQwenPydantic] Mode set to: {mode}")

    def set_persona(self, persona_name: str):
        """Activate a different SuperQwen persona"""
        self.provider.set_persona(persona_name)

        # Rebuild Pydantic AI agent with new persona
        self.agent = Agent(
            self.provider.get_model(),
            output_type=self.output_type,
            system_prompt=self._build_enhanced_prompt(persona_name)
        )

        print(f"[SuperQwenPydantic] Persona changed to: {persona_name}")

    def clear_conversation(self):
        """Clear conversation history"""
        self.provider.clear_conversation()

    def save_conversation(self, filepath: str):
        """Save conversation to file"""
        self.provider.save_conversation(filepath)

    def load_conversation(self, filepath: str):
        """Load conversation from file"""
        self.provider.load_conversation(filepath)

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        stats = self.provider.get_stats()
        stats.update({
            'agent_type': self.agent_type,
            'output_type': self.output_type.__name__,
            'cache_enabled': self.cache and self.cache.enabled,
        })
        return stats


# Convenience factory functions for existing agents
def create_build_agent_superqwen(persona: Optional[str] = "python-expert", mode: str = "background"):
    """Create SuperQwen-enhanced BuildAgent"""
    from pydantic import BaseModel, Field

    class BuildDecision(BaseModel):
        should_build: bool = Field(description="Whether to build")
        strategy: str = Field(description="Build strategy")
        estimated_time: int = Field(description="Estimated time in seconds")
        reason: str = Field(description="Explanation")

    system_prompt = """You are an expert build decision agent.
Analyze code changes and determine optimal build strategies."""

    return SuperQwenPydanticAgent(
        agent_type='build',
        output_type=BuildDecision,
        base_system_prompt=system_prompt,
        superqwen_persona=persona,
        mode=mode
    )


def create_test_agent_superqwen(persona: Optional[str] = "quality-engineer", mode: str = "background"):
    """Create SuperQwen-enhanced TestAgent"""
    from pydantic import BaseModel, Field

    class TestDecision(BaseModel):
        tests_to_run: List[str] = Field(description="Tests to execute")
        tests_to_skip: List[str] = Field(description="Tests to skip")
        reason: str = Field(description="Test selection rationale")
        estimated_time: int = Field(description="Estimated time in seconds")

    system_prompt = """You are an expert test selection agent.
Intelligently select which tests to run based on code changes."""

    return SuperQwenPydanticAgent(
        agent_type='test',
        output_type=TestDecision,
        base_system_prompt=system_prompt,
        superqwen_persona=persona,
        mode=mode
    )


if __name__ == '__main__':
    """Test SuperQwen-enhanced Pydantic AI agents"""

    print("=== SuperQwen-Enhanced Pydantic AI Agent Test ===\n")

    # Test BuildAgent with python-expert persona
    print("Test 1: Structured output with python-expert persona")
    build_agent = create_build_agent_superqwen(persona="python-expert", mode="background")

    decision = build_agent.run_structured_sync(
        "Files changed: api.py, models.py, tests/test_api.py. Should we build?"
    )

    print(f"Decision: {decision}")
    print()

    # Test conversational mode
    print("Test 2: Conversational mode")
    build_agent.set_mode("conversational")

    response = build_agent.run_conversational_sync(
        "What are the key factors in deciding whether to trigger a build?"
    )

    print(f"Response: {response[:300]}...")
    print()

    # Test command execution
    print("Test 3: Execute SuperQwen command")
    build_agent.set_mode("background")

    result = build_agent.execute_command_sync(
        "analyze",
        "Analyze the build decision logic for performance bottlenecks"
    )

    print(f"Analysis: {result[:300]}...")
    print()

    # Show stats
    print("Agent stats:")
    stats = build_agent.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    
def create_pm_agent_superqwen(persona: Optional[str] = "pm-agent", mode: str = "background"):
    """Create SuperQwen-enhanced Project Management agent"""
    from pydantic import BaseModel, Field

    class PMPlan(BaseModel):
        objective: str = Field(description="Primary goal")
        milestones: list[str] = Field(default_factory=list, description="Key milestones")
        risks: list[str] = Field(default_factory=list, description="Top risks")
        timeline: str = Field(description="High-level timeline")
        acceptance_criteria: list[str] = Field(default_factory=list, description="Acceptance checks")

    system_prompt = (
        "You are a pragmatic project manager. Write concise plans, call out risks early,"
        " and define clear acceptance criteria. Keep stakeholders aligned."
    )

    return SuperQwenPydanticAgent(
        agent_type='pm',
        output_type=PMPlan,
        base_system_prompt=system_prompt,
        superqwen_persona=persona,
        mode=mode
    )


def create_research_agent_superqwen(persona: Optional[str] = "deep-research-agent", mode: str = "background"):
    """Create SuperQwen-enhanced Research agent"""
    from pydantic import BaseModel, Field

    class ResearchSummary(BaseModel):
        question: str = Field(description="Research question")
        summary: str = Field(description="Concise answer")
        findings: list[str] = Field(default_factory=list, description="Key findings")
        sources: list[str] = Field(default_factory=list, description="Cited sources or references")

    system_prompt = (
        "You are a deep research agent. Gather facts, contrast viewpoints, cite sources," 
        " and produce a crisp, actionable summary. Avoid speculation."
    )

    return SuperQwenPydanticAgent(
        agent_type='research',
        output_type=ResearchSummary,
        base_system_prompt=system_prompt,
        superqwen_persona=persona,
        mode=mode
    )


def create_socratic_mentor_agent_superqwen(persona: Optional[str] = "socratic-mentor", mode: str = "conversational"):
    """Create SuperQwen-enhanced Socratic mentor agent (best in conversational mode)"""
    from pydantic import BaseModel, Field

    class MentorGuide(BaseModel):
        next_questions: list[str] = Field(default_factory=list, description="Socratic questions to unblock thinking")
        guidance: str = Field(description="Short guidance")

    system_prompt = (
        "You are a Socratic mentor. Ask incisive questions, avoid giving full solutions outright,"
        " and guide towards insight. Keep tone supportive and concise."
    )

    return SuperQwenPydanticAgent(
        agent_type='socratic_mentor',
        output_type=MentorGuide,
        base_system_prompt=system_prompt,
        superqwen_persona=persona,
        mode=mode
    )

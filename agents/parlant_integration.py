"""
Parlant Integration Layer

Provides conversational interface for agent interactions via Parlant framework.
Parlant handles natural language understanding and multi-turn conversations.
"""

from typing import Optional, Dict, Any, AsyncGenerator
from datetime import datetime
import json
import logging
from dataclasses import dataclass

from .models.agent_base import (
    AgentRequest,
    AgentResponse,
    ExecutionStatus,
    AgentMode,
)
from .registry import get_registry


logger = logging.getLogger(__name__)


# ============================================================================
# Parlant Message Models
# ============================================================================

@dataclass
class ParlantMessage:
    """Message in Parlant conversation"""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {},
        }


@dataclass
class ParlantConversation:
    """Conversation session with agent(s)"""

    conversation_id: str
    user_id: str
    agent_ids: list[str]
    messages: list[ParlantMessage]
    context: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Add message to conversation"""
        self.messages.append(ParlantMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata,
        ))
        self.updated_at = datetime.now()

    def get_conversation_text(self) -> str:
        """Get formatted conversation text for context"""
        lines = []
        for msg in self.messages[-10:]:  # Last 10 messages
            lines.append(f"{msg.role.upper()}: {msg.content}")
        return "\n".join(lines)


# ============================================================================
# Parlant Agent Adapter
# ============================================================================

class ParlantAgentAdapter:
    """
    Adapter between Parlant conversational interface and agent execution.

    Handles:
    - Natural language to agent request conversion
    - Agent response formatting for Parlant
    - Multi-turn conversation management
    - Context persistence
    """

    def __init__(self, agent_id: str, registry=None):
        """
        Initialize adapter for specific agent.

        Args:
            agent_id: ID of agent to adapt
            registry: Agent registry (uses global if None)
        """
        self.agent_id = agent_id
        self.registry = registry or get_registry()
        self.metadata = self.registry.get_agent(agent_id)
        self.handler = self.registry.get_handler(agent_id)

        if not self.metadata:
            raise ValueError(f"Agent {agent_id} not found in registry")
        if not self.handler:
            raise ValueError(f"No handler for agent {agent_id}")

    async def process_message(
        self,
        message: str,
        conversation: ParlantConversation,
        mode: AgentMode = AgentMode.BACKGROUND,
    ) -> AsyncGenerator[str, None]:
        """
        Process user message through agent.

        Args:
            message: User message
            conversation: Current conversation context
            mode: Execution mode

        Yields:
            Streaming response tokens
        """
        try:
            # Add user message to conversation
            conversation.add_message("user", message)

            # Extract agent request from natural language
            agent_request = self._extract_request(message, conversation)

            # Record execution
            execution = self.registry.record_execution(
                agent_id=self.agent_id,
                capability=self.metadata.capability,
                request_data=agent_request.dict(),
            )

            # Execute agent
            yield f"🔄 Processing with {self.metadata.name}...\n"

            try:
                response = await self.handler(agent_request, conversation.context)

                # Update execution
                self.registry.update_execution(
                    execution_id=execution.execution_id,
                    status=ExecutionStatus.COMPLETED,
                    response_data=response.dict() if hasattr(response, 'dict') else response,
                )

                # Format and yield response
                formatted_response = self._format_response(response)
                conversation.add_message(
                    "assistant",
                    formatted_response,
                    metadata={"execution_id": execution.execution_id}
                )

                yield formatted_response

            except Exception as e:
                error_msg = f"Agent execution failed: {str(e)}"
                logger.error(error_msg, exc_info=True)

                self.registry.update_execution(
                    execution_id=execution.execution_id,
                    status=ExecutionStatus.FAILED,
                    error=str(e),
                )

                conversation.add_message("assistant", f"❌ {error_msg}")
                yield f"❌ {error_msg}"

        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}", exc_info=True)
            error_msg = f"Error processing message: {str(e)}"
            conversation.add_message("assistant", error_msg)
            yield error_msg

    def _extract_request(
        self,
        message: str,
        conversation: ParlantConversation,
    ) -> AgentRequest:
        """
        Convert natural language message to structured agent request.

        Args:
            message: Natural language input
            conversation: Conversation context

        Returns:
            AgentRequest ready for agent execution
        """
        # In production, use LLM to extract structured request
        # For now, use simple heuristics

        return AgentRequest(
            query=message,
            context=conversation.context,
            mode=AgentMode.BACKGROUND,
            metadata={
                "conversation_id": conversation.conversation_id,
                "user_id": conversation.user_id,
            },
        )

    def _format_response(self, response: AgentResponse) -> str:
        """
        Format agent response for Parlant display.

        Args:
            response: Agent response

        Returns:
            Formatted text for display
        """
        lines = []

        # Status indicator
        status_emoji = {
            ExecutionStatus.COMPLETED: "✅",
            ExecutionStatus.FAILED: "❌",
            ExecutionStatus.RUNNING: "🔄",
        }.get(response.status, "❓")

        lines.append(f"{status_emoji} **{response.agent_id}** - {response.status}")
        lines.append(f"*Duration: {response.duration_ms}ms*\n")

        # Main result
        if response.result:
            lines.append("**Result:**")
            for key, value in response.result.items():
                if isinstance(value, list):
                    lines.append(f"- {key}:")
                    for item in value[:5]:  # Limit to 5 items
                        lines.append(f"  - {item}")
                    if len(value) > 5:
                        lines.append(f"  - ... and {len(value) - 5} more")
                else:
                    lines.append(f"- {key}: {value}")

        # Findings
        if response.findings:
            lines.append("\n**Key Findings:**")
            for finding in response.findings[:5]:
                lines.append(f"- {finding}")

        # Confidence
        confidence_pct = int(response.confidence * 100)
        lines.append(f"\n**Confidence:** {confidence_pct}%")

        # Error if present
        if response.error:
            lines.append(f"\n⚠️ **Error:** {response.error}")

        return "\n".join(lines)


# ============================================================================
# Parlant Multi-Agent Orchestrator
# ============================================================================

class ParlantOrchestrator:
    """
    Manages multi-agent conversations via Parlant.

    Handles:
    - Agent selection based on user intent
    - Sequential agent orchestration
    - Conversation state management
    - Cross-agent communication
    """

    def __init__(self, registry=None):
        """Initialize orchestrator"""
        self.registry = registry or get_registry()
        self.adapters: Dict[str, ParlantAgentAdapter] = {}
        self.conversations: Dict[str, ParlantConversation] = {}

    def create_conversation(
        self,
        conversation_id: str,
        user_id: str,
        agent_ids: list[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> ParlantConversation:
        """Create new conversation session"""
        conversation = ParlantConversation(
            conversation_id=conversation_id,
            user_id=user_id,
            agent_ids=agent_ids,
            messages=[],
            context=context or {},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.conversations[conversation_id] = conversation

        # Initialize adapters
        for agent_id in agent_ids:
            if agent_id not in self.adapters:
                self.adapters[agent_id] = ParlantAgentAdapter(agent_id, self.registry)

        logger.info(f"Conversation created: {conversation_id}")
        return conversation

    async def route_to_agent(
        self,
        conversation_id: str,
        message: str,
        agent_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Route message to appropriate agent.

        Args:
            conversation_id: Current conversation
            message: User message
            agent_id: Specific agent (if None, auto-select)

        Yields:
            Response tokens
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            yield "❌ Conversation not found"
            return

        # Select agent if not specified
        if not agent_id:
            agent_id = self._select_agent(message, conversation)

        if agent_id not in conversation.agent_ids:
            yield f"❌ Agent {agent_id} not available in this conversation"
            return

        # Route to agent
        adapter = self.adapters[agent_id]
        async for token in adapter.process_message(message, conversation):
            yield token

    def _select_agent(self, message: str, conversation: ParlantConversation) -> str:
        """
        Select appropriate agent for message.

        Args:
            message: User message
            conversation: Conversation context

        Returns:
            Selected agent_id
        """
        # Simple heuristics - in production, use intent classification
        message_lower = message.lower()

        keywords = {
            "research": "deep-research-agent",
            "analyze": "sequential-analysis-agent",
            "code": "code-generation-agent",
            "test": "testing-agent",
            "review": "code-review-agent",
            "plan": "planning-agent",
            "document": "documentation-agent",
        }

        for keyword, agent_id in keywords.items():
            if keyword in message_lower and agent_id in conversation.agent_ids:
                return agent_id

        # Default to first agent
        return conversation.agent_ids[0]

    def get_conversation_summary(self, conversation_id: str) -> str:
        """Get summary of conversation"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return "Conversation not found"

        stats = self.registry.get_stats()

        summary = f"""
**Conversation Summary**
- ID: {conversation_id}
- User: {conversation.user_id}
- Agents: {', '.join(conversation.agent_ids)}
- Messages: {len(conversation.messages)}
- Duration: {(conversation.updated_at - conversation.created_at).total_seconds():.1f}s

**Total System Stats**
- Agents: {stats['total_agents']}
- Total Executions: {stats['total_executions']}
        """

        return summary.strip()


# ============================================================================
# Parlant REST Endpoints (for integration)
# ============================================================================

async def create_agent_conversation(user_id: str, agent_ids: list[str]) -> Dict[str, Any]:
    """REST endpoint: Create conversation"""
    from uuid import uuid4
    orchestrator = ParlantOrchestrator()
    conversation_id = str(uuid4())

    conversation = orchestrator.create_conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        agent_ids=agent_ids,
    )

    return {
        "conversation_id": conversation_id,
        "agents": agent_ids,
        "status": "ready",
    }


async def send_message(
    conversation_id: str,
    message: str,
    agent_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """REST endpoint: Send message to conversation"""
    orchestrator = ParlantOrchestrator()

    async for token in orchestrator.route_to_agent(
        conversation_id=conversation_id,
        message=message,
        agent_id=agent_id,
    ):
        yield token

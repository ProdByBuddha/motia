"""
Agent Registry and Factory

Manages agent lifecycle, registration, and instantiation.
Provides factory pattern for creating agents with proper validation and configuration.
"""

from typing import Dict, Type, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from enum import Enum

from .models.agent_base import (
    AgentCapability,
    AgentMetadata,
    AgentExecution,
    ExecutionStatus,
    AgentMode,
)


logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Central registry for all agents in the system.

    Responsibilities:
    - Register agent definitions
    - Track agent instances
    - Provide agent lookup
    - Manage agent execution records
    """

    def __init__(self):
        """Initialize agent registry"""
        self._agents: Dict[str, AgentMetadata] = {}
        self._handlers: Dict[str, Callable] = {}
        self._executions: Dict[str, AgentExecution] = {}
        self._execution_history: list[AgentExecution] = []

    def register(
        self,
        agent_id: str,
        metadata: AgentMetadata,
        handler: Callable,
    ) -> None:
        """
        Register an agent with the system.

        Args:
            agent_id: Unique agent identifier
            metadata: Agent metadata and configuration
            handler: Async function that executes the agent
        """
        if agent_id in self._agents:
            logger.warning(f"Agent {agent_id} already registered, overwriting")

        self._agents[agent_id] = metadata
        self._handlers[agent_id] = handler
        logger.info(f"Agent registered: {agent_id} ({metadata.name})")

    def get_agent(self, agent_id: str) -> Optional[AgentMetadata]:
        """Get agent metadata"""
        return self._agents.get(agent_id)

    def get_handler(self, agent_id: str) -> Optional[Callable]:
        """Get agent execution handler"""
        return self._handlers.get(agent_id)

    def list_agents(
        self,
        capability: Optional[AgentCapability] = None,
        tags: Optional[list[str]] = None,
    ) -> list[AgentMetadata]:
        """
        List all registered agents, optionally filtered.

        Args:
            capability: Filter by capability
            tags: Filter by tags (any tag match)

        Returns:
            List of matching agent metadata
        """
        agents = list(self._agents.values())

        if capability:
            agents = [a for a in agents if a.capability == capability]

        if tags:
            agents = [a for a in agents if any(t in a.tags for t in tags)]

        return agents

    def record_execution(
        self,
        agent_id: str,
        capability: AgentCapability,
        request_data: Dict[str, Any],
        status: ExecutionStatus = ExecutionStatus.PENDING,
    ) -> AgentExecution:
        """
        Create an execution record for audit trail.

        Args:
            agent_id: Agent that will execute
            capability: Agent capability type
            request_data: Input data
            status: Initial status

        Returns:
            AgentExecution record
        """
        execution = AgentExecution(
            agent_id=agent_id,
            agent_capability=capability,
            request_data=request_data,
            status=status,
            started_at=datetime.now() if status != ExecutionStatus.PENDING else None,
        )

        self._executions[execution.execution_id] = execution
        self._execution_history.append(execution)

        return execution

    def update_execution(
        self,
        execution_id: str,
        status: ExecutionStatus,
        response_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update execution status and result.

        Args:
            execution_id: Execution ID to update
            status: New status
            response_data: Result data if successful
            error: Error message if failed
        """
        execution = self._executions.get(execution_id)
        if not execution:
            logger.warning(f"Execution {execution_id} not found for update")
            return

        execution.status = status
        execution.response_data = response_data
        execution.error = error
        execution.completed_at = datetime.now()

        if execution.started_at:
            execution.duration_ms = int(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )

        logger.info(
            f"Execution {execution_id} updated: {status} "
            f"({execution.duration_ms}ms)"
        )

    def get_execution(self, execution_id: str) -> Optional[AgentExecution]:
        """Get execution record"""
        return self._executions.get(execution_id)

    def get_execution_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[AgentExecution]:
        """Get execution history, optionally filtered by agent"""
        history = self._execution_history

        if agent_id:
            history = [e for e in history if e.agent_id == agent_id]

        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        total_agents = len(self._agents)
        total_executions = len(self._execution_history)

        capabilities = {}
        for agent in self._agents.values():
            cap = agent.capability
            capabilities[cap] = capabilities.get(cap, 0) + 1

        execution_status = {}
        for execution in self._execution_history:
            status = execution.status
            execution_status[status] = execution_status.get(status, 0) + 1

        return {
            "total_agents": total_agents,
            "agents_by_capability": capabilities,
            "total_executions": total_executions,
            "executions_by_status": execution_status,
            "registered_at": datetime.now().isoformat(),
        }


# ============================================================================
# Built-in Agent Registry
# ============================================================================

def create_default_registry() -> AgentRegistry:
    """
    Create and populate default agent registry.

    Returns:
        Configured AgentRegistry with all built-in agents
    """
    registry = AgentRegistry()

    # Research agents will be registered here
    # Analysis agents will be registered here
    # Code agents will be registered here
    # etc.

    return registry


# Global registry instance
_global_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get global agent registry (lazy initialization)"""
    global _global_registry
    if _global_registry is None:
        _global_registry = create_default_registry()
    return _global_registry


def reset_registry() -> None:
    """Reset global registry (for testing)"""
    global _global_registry
    _global_registry = None

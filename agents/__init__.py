"""
Motia Agents Package

Comprehensive agent ecosystem for orchestrated AI workflows.
Provides 15 specialized agents for research, analysis, generation, and quality assurance.

Features:
- Pydantic-validated inputs/outputs
- Parlant conversational interface
- Redis caching for performance
- PostgreSQL audit trails
- Multi-agent orchestration

Usage:
    from motia.agents import get_registry, ParlantOrchestrator

    # Get agent registry
    registry = get_registry()

    # Create multi-agent conversation
    orchestrator = ParlantOrchestrator(registry)
    conversation = orchestrator.create_conversation(
        conversation_id="conv-123",
        user_id="user-456",
        agent_ids=["deep-research-agent", "sequential-analysis-agent"]
    )

    # Send message through orchestrator
    async for response in orchestrator.route_to_agent(
        conversation_id="conv-123",
        message="Research AI orchestration platforms"
    ):
        print(response)
"""

from .models.agent_base import (
    # Enums
    AgentMode,
    AgentCapability,
    ExecutionStatus,
    # Base models
    AgentRequest,
    AgentResponse,
    AgentExecution,
    AgentMetadata,
    # Research models
    ResearchQuery,
    ResearchResult,
    Source,
    # Analysis models
    AnalysisRequest,
    AnalysisResult,
    # Code models
    CodeGenerationRequest,
    CodeGenerationResult,
    CodeBlock,
    # Testing models
    TestRequest,
    TestingResult,
    TestResult,
    # Review models
    ReviewRequest,
    ReviewResult,
    Issue,
    # Documentation models
    DocumentRequest,
    DocumentationResult,
    DocumentSection,
    # Planning models
    PlanningRequest,
    PlanningResult,
    PlanStep,
)

from .registry import (
    AgentRegistry,
    get_registry,
    reset_registry,
    create_default_registry,
)

from .parlant_integration import (
    ParlantMessage,
    ParlantConversation,
    ParlantAgentAdapter,
    ParlantOrchestrator,
)

__version__ = "2.0.0"
__all__ = [
    # Enums
    "AgentMode",
    "AgentCapability",
    "ExecutionStatus",
    # Base classes
    "AgentRequest",
    "AgentResponse",
    "AgentExecution",
    "AgentMetadata",
    # Models
    "ResearchQuery",
    "ResearchResult",
    "Source",
    "AnalysisRequest",
    "AnalysisResult",
    "CodeGenerationRequest",
    "CodeGenerationResult",
    "CodeBlock",
    "TestRequest",
    "TestingResult",
    "TestResult",
    "ReviewRequest",
    "ReviewResult",
    "Issue",
    "DocumentRequest",
    "DocumentationResult",
    "DocumentSection",
    "PlanningRequest",
    "PlanningResult",
    "PlanStep",
    # Registry
    "AgentRegistry",
    "get_registry",
    "reset_registry",
    "create_default_registry",
    # Parlant
    "ParlantMessage",
    "ParlantConversation",
    "ParlantAgentAdapter",
    "ParlantOrchestrator",
]

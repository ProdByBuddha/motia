"""
Agent Handlers Package

Production implementations of specialized agents.

Available Handlers:
- Deep Research Agent: Multi-hop research with entity expansion
- (More agents to be added in Phase 2b/2c)
"""

from .deep_research_agent import DeepResearchAgent, create_deep_research_handler

__all__ = [
    "DeepResearchAgent",
    "create_deep_research_handler",
]

__version__ = "2.0.0"

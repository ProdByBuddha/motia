"""
Agent Base Models

Pydantic models defining the agent ecosystem architecture.
All agents conform to these base contracts for consistency and interoperability.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class AgentMode(str, Enum):
    """Agent execution modes"""
    INTERACTIVE = "interactive"  # Real-time conversation
    BACKGROUND = "background"    # Async execution
    BATCH = "batch"              # Bulk processing
    STREAMING = "streaming"      # Continuous output


class AgentCapability(str, Enum):
    """Core agent capabilities"""
    RESEARCH = "research"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    COORDINATION = "coordination"
    LEARNING = "learning"


class ExecutionStatus(str, Enum):
    """Execution statuses"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


# ============================================================================
# Input/Output Base Models
# ============================================================================

class AgentRequest(BaseModel):
    """Base request to any agent"""

    query: str = Field(..., description="Primary instruction or question")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Contextual information")
    mode: AgentMode = Field(default=AgentMode.BACKGROUND, description="Execution mode")
    timeout_seconds: Optional[int] = Field(default=None, description="Max execution time")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Custom metadata")

    class Config:
        use_enum_values = True


class AgentResponse(BaseModel):
    """Base response from any agent"""

    agent_id: str = Field(..., description="ID of agent that produced response")
    status: ExecutionStatus = Field(..., description="Execution status")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Main result data")
    findings: Optional[List[str]] = Field(default=None, description="Key findings")
    confidence: float = Field(default=0.5, ge=0, le=1, description="Confidence score")
    duration_ms: int = Field(..., description="Execution time in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Response metadata")

    class Config:
        use_enum_values = True


# ============================================================================
# Research Agent Models
# ============================================================================

class ResearchQuery(BaseModel):
    """Research agent input"""

    query: str = Field(..., min_length=5, description="Research topic")
    depth: str = Field(default="standard", description="quick|standard|deep")
    max_hops: int = Field(default=3, ge=1, le=10, description="Max search iterations")
    domain: Optional[str] = Field(default=None, description="Restrict to domain")
    include_sources: bool = Field(default=True, description="Include source citations")


class Source(BaseModel):
    """Citation source"""

    url: str = Field(..., description="Source URL")
    title: str = Field(..., description="Source title")
    relevance: float = Field(default=0.5, ge=0, le=1, description="Relevance score")
    accessed_at: Optional[datetime] = Field(default=None, description="Access time")


class ResearchResult(BaseModel):
    """Research agent output"""

    query: str
    findings: List[str] = Field(..., description="Key findings discovered")
    sources: List[Source] = Field(default=[], description="Source citations")
    confidence: float = Field(ge=0, le=1, description="Result confidence")
    hops_used: int = Field(..., description="Number of search hops used")
    total_sources: int = Field(..., description="Total sources examined")


# ============================================================================
# Analysis Agent Models
# ============================================================================

class AnalysisRequest(BaseModel):
    """Analysis agent input"""

    subject: str = Field(..., min_length=10, description="What to analyze")
    framework: str = Field(
        default="sequential",
        description="sequential|comparative|causal|systems"
    )
    depth: str = Field(default="moderate", description="surface|moderate|deep")
    format: str = Field(default="structured", description="structured|narrative|bullets")


class AnalysisResult(BaseModel):
    """Analysis agent output"""

    subject: str
    framework: str
    analysis: str = Field(..., description="Main analysis content")
    key_points: List[str] = Field(..., description="Distilled insights")
    risks: List[str] = Field(default=[], description="Identified risks")
    opportunities: List[str] = Field(default=[], description="Opportunities")
    recommendations: List[str] = Field(default=[], description="Next steps")
    confidence: float = Field(ge=0, le=1)


# ============================================================================
# Code Generation Agent Models
# ============================================================================

class CodeGenerationRequest(BaseModel):
    """Code generation agent input"""

    description: str = Field(..., description="What code to generate")
    language: str = Field(default="python", description="Target language")
    style: str = Field(default="production", description="production|test|example")
    requirements: Optional[List[str]] = Field(default=None, description="Specific requirements")
    existing_code: Optional[str] = Field(default=None, description="Context from existing code")


class CodeBlock(BaseModel):
    """Generated code block"""

    language: str
    code: str = Field(..., description="The code")
    explanation: Optional[str] = Field(default=None, description="Code explanation")
    filename: Optional[str] = Field(default=None, description="Suggested filename")
    tests_included: bool = Field(default=False, description="Whether tests are included")


class CodeGenerationResult(BaseModel):
    """Code generation agent output"""

    description: str
    blocks: List[CodeBlock] = Field(..., description="Generated code blocks")
    dependencies: List[str] = Field(default=[], description="Required dependencies")
    instructions: List[str] = Field(default=[], description="Setup/usage instructions")
    validation_passed: bool = Field(default=False, description="Validation status")


# ============================================================================
# Testing Agent Models
# ============================================================================

class TestRequest(BaseModel):
    """Testing agent input"""

    code: str = Field(..., description="Code to test")
    language: str = Field(default="python", description="Code language")
    test_type: str = Field(default="unit", description="unit|integration|e2e")
    coverage_target: float = Field(default=0.8, ge=0, le=1, description="Min coverage")


class TestResult(BaseModel):
    """Individual test result"""

    test_name: str
    passed: bool
    duration_ms: int
    error: Optional[str] = None
    coverage: Optional[float] = None


class TestingResult(BaseModel):
    """Testing agent output"""

    code_hash: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    coverage: float = Field(ge=0, le=1, description="Code coverage percentage")
    test_results: List[TestResult] = []
    recommendations: List[str] = []


# ============================================================================
# Document Generation Agent Models
# ============================================================================

class DocumentRequest(BaseModel):
    """Documentation agent input"""

    subject: str = Field(..., description="What to document")
    doc_type: str = Field(
        default="api",
        description="api|guide|architecture|tutorial|reference"
    )
    audience: str = Field(default="developer", description="Target audience")
    include_examples: bool = Field(default=True, description="Include code examples")


class DocumentSection(BaseModel):
    """Document section"""

    title: str
    content: str
    level: int = Field(default=1, ge=1, le=6, description="Heading level")
    examples: Optional[List[str]] = Field(default=None, description="Code examples")


class DocumentationResult(BaseModel):
    """Documentation agent output"""

    subject: str
    doc_type: str
    title: str
    sections: List[DocumentSection]
    table_of_contents: List[str]
    metadata: Optional[Dict[str, str]] = None


# ============================================================================
# Review Agent Models
# ============================================================================

class ReviewRequest(BaseModel):
    """Review agent input"""

    content: str = Field(..., description="Content to review")
    review_type: str = Field(
        default="code",
        description="code|documentation|design|performance"
    )
    focus_areas: Optional[List[str]] = Field(default=None, description="Areas to focus on")


class Issue(BaseModel):
    """Review issue"""

    severity: str = Field(description="critical|high|medium|low")
    location: Optional[str] = Field(default=None, description="Line/section reference")
    description: str = Field(..., description="Issue description")
    suggestion: Optional[str] = Field(default=None, description="Suggested fix")


class ReviewResult(BaseModel):
    """Review agent output"""

    content_hash: str
    review_type: str
    quality_score: float = Field(ge=0, le=100, description="Overall quality 0-100")
    issues_found: List[Issue] = []
    strengths: List[str] = []
    recommendations: List[str] = []
    overall_assessment: str


# ============================================================================
# Planning Agent Models
# ============================================================================

class PlanningRequest(BaseModel):
    """Planning agent input"""

    objective: str = Field(..., description="Goal to plan for")
    constraints: Optional[List[str]] = Field(default=None, description="Constraints")
    available_resources: Optional[List[str]] = Field(default=None, description="Resources")


class PlanStep(BaseModel):
    """Plan step"""

    sequence: int
    action: str
    duration_estimate: Optional[str] = None
    dependencies: List[int] = Field(default=[], description="Prerequisite step indices")
    success_criteria: List[str] = []


class PlanningResult(BaseModel):
    """Planning agent output"""

    objective: str
    total_steps: int
    estimated_duration: str
    steps: List[PlanStep]
    risks: List[str] = []
    contingencies: List[str] = []


# ============================================================================
# Agent Execution Model
# ============================================================================

class AgentExecution(BaseModel):
    """Record of agent execution"""

    execution_id: str = Field(default_factory=lambda: f"exec-{datetime.now().timestamp()}")
    agent_id: str
    agent_capability: AgentCapability
    request_data: Dict[str, Any]
    response_data: Optional[Dict[str, Any]] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    retry_count: int = 0

    class Config:
        use_enum_values = True


# ============================================================================
# Agent Registry Models
# ============================================================================

class AgentMetadata(BaseModel):
    """Agent registration metadata"""

    agent_id: str
    name: str
    description: str
    capability: AgentCapability
    version: str = "1.0.0"
    input_model: str = Field(..., description="Pydantic model name")
    output_model: str = Field(..., description="Pydantic model name")
    supported_modes: List[AgentMode] = [AgentMode.BACKGROUND]
    timeout_default: int = 300  # seconds
    retry_policy: Optional[Dict[str, int]] = None
    tags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True

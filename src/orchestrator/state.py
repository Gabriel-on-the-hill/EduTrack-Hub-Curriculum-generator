"""
Graph State Definition (Blueprint Section 14)

This module defines the state that flows through the LangGraph execution.
Each node reads and writes to this shared state.

Per Blueprint Section 14.4:
- Fallback tiers enforced
- Cost guards per-request
- No node retries infinitely (max 2)
- Halts are explicit states
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.base import ConfidenceScore, FallbackTier


class NodeStatus(str, Enum):
    """Status of a node in the graph execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    HALTED = "halted"  # Explicit halt state per Blueprint


class GraphExecutionMode(str, Enum):
    """Execution mode for the graph."""
    NORMAL = "normal"
    SHADOW = "shadow"  # Shadow execution mode per Blueprint Section 24


class NodeExecution(BaseModel):
    """Tracks execution of a single node."""
    node_name: str
    status: NodeStatus = NodeStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = Field(default=0, ge=0, le=2)  # Max 2 retries per Blueprint
    error_message: str | None = None
    output_data: dict[str, Any] | None = None


class CostTracking(BaseModel):
    """
    Tracks cost for the current request.
    
    Per Blueprint Section 21.3 (Cost Guards):
    Per-request cap: $0.02
    Daily cap: $2.00
    """
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0
    model_calls: int = 0
    
    # Blueprint limits
    PER_REQUEST_CAP_USD: float = 0.02
    DAILY_CAP_USD: float = 2.00
    
    def is_within_budget(self) -> bool:
        """Check if current request is within per-request budget."""
        return self.estimated_cost_usd < self.PER_REQUEST_CAP_USD
    
    def add_cost(self, tokens: int, cost_usd: float) -> None:
        """Add cost from a model call."""
        self.tokens_used += tokens
        self.estimated_cost_usd += cost_usd
        self.model_calls += 1


class GraphState(BaseModel):
    """
    Shared state flowing through the LangGraph execution.
    
    This is the single source of truth for all nodes.
    Each node can read the full state and update specific fields.
    
    Blueprint Section 14.1 defines the node flow:
    NormalizeRequest → ResolveJurisdiction → VaultLookup →
    [EnqueueColdStart | Generate] → ...
    """
    
    # =========================================================================
    # REQUEST IDENTIFICATION
    # =========================================================================
    request_id: UUID = Field(description="Unique request identifier")
    raw_prompt: str = Field(description="Original user input")
    
    # =========================================================================
    # EXECUTION CONTEXT
    # =========================================================================
    execution_mode: GraphExecutionMode = Field(
        default=GraphExecutionMode.NORMAL,
        description="Normal or shadow execution"
    )
    current_fallback_tier: FallbackTier = Field(
        default=FallbackTier.TIER_0,
        description="Current fallback tier for model selection"
    )
    
    # =========================================================================
    # NODE TRACKING
    # =========================================================================
    node_history: list[NodeExecution] = Field(
        default_factory=list,
        description="Execution history of all nodes"
    )
    current_node: str | None = Field(
        default=None,
        description="Currently executing node"
    )
    
    # =========================================================================
    # NORMALIZED REQUEST DATA (from NormalizeRequest node)
    # =========================================================================
    normalized_country: str | None = None
    normalized_country_code: str | None = None
    normalized_grade: str | None = None
    normalized_subject: str | None = None
    normalization_confidence: ConfidenceScore | None = None
    
    # =========================================================================
    # JURISDICTION DATA (from ResolveJurisdiction node)
    # =========================================================================
    jurisdiction_level: str | None = None
    jurisdiction_name: str | None = None
    jas_score: ConfidenceScore | None = None
    jurisdiction_confidence: ConfidenceScore | None = None
    
    # =========================================================================
    # VAULT DATA (from VaultLookup node)
    # =========================================================================
    vault_found: bool = False
    curriculum_id: UUID | None = None
    vault_confidence: ConfidenceScore | None = None
    needs_cold_start: bool = False
    
    # =========================================================================
    # INGESTION DATA (from Scout/Gatekeeper/Architect/Embedder)
    # =========================================================================
    scout_job_id: UUID | None = None
    candidate_urls: list[str] = Field(default_factory=list)
    approved_source_url: str | None = None
    competency_count: int = 0
    extraction_confidence: ConfidenceScore | None = None
    
    # =========================================================================
    # GENERATION DATA (from Generate node)
    # =========================================================================
    generation_output_id: UUID | None = None
    generated_content: str | None = None
    generation_coverage: ConfidenceScore | None = None
    
    # =========================================================================
    # COST TRACKING
    # =========================================================================
    cost: CostTracking = Field(default_factory=CostTracking)
    
    # =========================================================================
    # ERROR HANDLING
    # =========================================================================
    has_error: bool = False
    error_node: str | None = None
    error_message: str | None = None
    requires_human_alert: bool = False
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_total_attempts_for_node(self, node_name: str) -> int:
        """Count total attempts (including current) for a node."""
        count = 0
        for execution in self.node_history:
            if execution.node_name == node_name:
                count += 1
        return count
    
    def record_node_start(self, node_name: str) -> None:
        """Record that a node has started execution."""
        self.current_node = node_name
        # Clear error state when starting fresh
        self.has_error = False
        
        execution = NodeExecution(
            node_name=node_name,
            status=NodeStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        self.node_history.append(execution)
    
    def record_node_success(self, node_name: str, output: dict[str, Any] | None = None) -> None:
        """Record successful node completion."""
        for execution in reversed(self.node_history):
            if execution.node_name == node_name and execution.status == NodeStatus.RUNNING:
                execution.status = NodeStatus.SUCCESS
                execution.completed_at = datetime.utcnow()
                execution.output_data = output
                break
        self.current_node = None
    
    def record_node_failure(self, node_name: str, error: str) -> None:
        """Record node failure."""
        for execution in reversed(self.node_history):
            if execution.node_name == node_name and execution.status == NodeStatus.RUNNING:
                execution.status = NodeStatus.FAILED
                execution.completed_at = datetime.utcnow()
                execution.error_message = error
                break
        self.has_error = True
        self.error_node = node_name
        self.error_message = error
    
    def can_retry_node(self, node_name: str) -> bool:
        """
        Check if a node can be retried (max 2 attempts per Blueprint).
        
        Counts total attempts from node_history.
        """
        total_attempts = self._get_total_attempts_for_node(node_name)
        return total_attempts < 2
    
    def escalate_fallback_tier(self) -> None:
        """Escalate to next fallback tier."""
        if self.current_fallback_tier == FallbackTier.TIER_0:
            self.current_fallback_tier = FallbackTier.TIER_1
        elif self.current_fallback_tier == FallbackTier.TIER_1:
            self.current_fallback_tier = FallbackTier.TIER_2
    
    def should_halt(self) -> bool:
        """
        Determine if execution should halt.
        
        Per Blueprint: Halts are explicit states.
        """
        return (
            self.has_error and not self.can_retry_node(self.error_node or "")
        ) or (
            self.current_fallback_tier == FallbackTier.TIER_2 and self.has_error
        ) or (
            not self.cost.is_within_budget()
        )

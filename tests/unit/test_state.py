"""
Unit tests for GraphState and state management.

Tests verify:
1. State initialization
2. Node tracking
3. Retry limits (max 2 per Blueprint)
4. Cost budget enforcement
5. Fallback tier escalation
"""

from uuid import uuid4

import pytest

from src.orchestrator.state import (
    GraphState,
    NodeStatus,
    CostTracking,
    GraphExecutionMode,
)
from src.schemas.base import FallbackTier


class TestGraphState:
    """Tests for GraphState."""

    def test_initial_state(self) -> None:
        """Initial state should have correct defaults."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="Grade 9 Biology for Nigeria"
        )
        
        assert state.execution_mode == GraphExecutionMode.NORMAL
        assert state.current_fallback_tier == FallbackTier.TIER_0
        assert len(state.node_history) == 0
        assert state.has_error is False
        assert state.vault_found is False

    def test_record_node_lifecycle(self) -> None:
        """Node start/success should be tracked."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test"
        )
        
        # Start node
        state.record_node_start("TestNode")
        assert state.current_node == "TestNode"
        assert len(state.node_history) == 1
        assert state.node_history[0].status == NodeStatus.RUNNING
        
        # Complete node
        state.record_node_success("TestNode", {"result": "ok"})
        assert state.current_node is None
        assert state.node_history[0].status == NodeStatus.SUCCESS

    def test_record_node_failure(self) -> None:
        """Node failure should be tracked with error details."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test"
        )
        
        state.record_node_start("FailingNode")
        state.record_node_failure("FailingNode", "Something went wrong")
        
        assert state.has_error is True
        assert state.error_node == "FailingNode"
        assert state.error_message == "Something went wrong"
        assert state.node_history[0].status == NodeStatus.FAILED

    def test_retry_limit_enforced(self) -> None:
        """Blueprint: Max 2 attempts per node."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test"
        )
        
        # First attempt
        state.record_node_start("RetryNode")
        state.record_node_failure("RetryNode", "Error 1")
        assert state.can_retry_node("RetryNode") is True  # 1 attempt, can retry
        
        # Second attempt
        state.record_node_start("RetryNode")
        state.record_node_failure("RetryNode", "Error 2")
        assert state.can_retry_node("RetryNode") is False  # 2 attempts, cannot retry

    def test_fallback_tier_escalation(self) -> None:
        """Fallback tiers should escalate correctly."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test"
        )
        
        assert state.current_fallback_tier == FallbackTier.TIER_0
        
        state.escalate_fallback_tier()
        assert state.current_fallback_tier == FallbackTier.TIER_1
        
        state.escalate_fallback_tier()
        assert state.current_fallback_tier == FallbackTier.TIER_2
        
        # Should stay at TIER_2
        state.escalate_fallback_tier()
        assert state.current_fallback_tier == FallbackTier.TIER_2


class TestCostTracking:
    """Tests for cost tracking."""

    def test_initial_cost(self) -> None:
        """Initial cost should be zero."""
        cost = CostTracking()
        assert cost.tokens_used == 0
        assert cost.estimated_cost_usd == 0.0
        assert cost.is_within_budget() is True

    def test_add_cost(self) -> None:
        """Adding cost should update tracking."""
        cost = CostTracking()
        cost.add_cost(tokens=1000, cost_usd=0.005)
        
        assert cost.tokens_used == 1000
        assert cost.estimated_cost_usd == 0.005
        assert cost.model_calls == 1

    def test_budget_exceeded(self) -> None:
        """Blueprint: Per-request cap is $0.02."""
        cost = CostTracking()
        cost.add_cost(tokens=5000, cost_usd=0.025)  # Exceeds $0.02
        
        assert cost.is_within_budget() is False


class TestHaltConditions:
    """Tests for halt decision logic."""

    def test_halt_on_error_after_retries(self) -> None:
        """Should halt when error occurs and retries exhausted."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test"
        )
        
        # Exhaust retries (2 attempts max)
        state.record_node_start("Node")
        state.record_node_failure("Node", "Error 1")
        state.record_node_start("Node")
        state.record_node_failure("Node", "Error 2")
        
        # Now can't retry, should halt
        assert state.can_retry_node("Node") is False
        assert state.should_halt() is True

    def test_halt_on_budget_exceeded(self) -> None:
        """Should halt when budget is exceeded."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test"
        )
        
        state.cost.add_cost(tokens=10000, cost_usd=0.05)
        assert state.should_halt() is True

    def test_no_halt_on_success(self) -> None:
        """Should not halt when everything is fine."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test"
        )
        
        state.record_node_start("Node")
        state.record_node_success("Node")
        
        assert state.should_halt() is False

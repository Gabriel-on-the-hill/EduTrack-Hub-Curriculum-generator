"""
Unit tests for LangGraph orchestration.

Tests verify:
1. Graph construction
2. Node execution flow
3. Conditional edge routing
4. Error handling paths
5. Human alert triggers
"""

from uuid import uuid4

import pytest

from src.orchestrator.state import GraphState, NodeStatus
from src.orchestrator.graph import (
    build_curriculum_graph,
    compile_curriculum_graph,
    create_initial_state,
    vault_lookup_decision,
    after_scout_decision,
    after_gatekeeper_decision,
    after_generate_decision,
)


class TestGraphConstruction:
    """Tests for graph building."""

    def test_graph_builds_successfully(self) -> None:
        """Graph should build without errors."""
        graph = build_curriculum_graph()
        assert graph is not None

    def test_graph_compiles(self) -> None:
        """Graph should compile for execution."""
        compiled = compile_curriculum_graph()
        assert compiled is not None


class TestInitialState:
    """Tests for initial state creation."""

    def test_create_initial_state(self) -> None:
        """Initial state should be properly configured."""
        state = create_initial_state("Grade 9 Biology for Nigeria")
        
        assert state.raw_prompt == "Grade 9 Biology for Nigeria"
        assert state.request_id is not None
        assert state.has_error is False


class TestConditionalEdges:
    """Tests for conditional edge routing logic."""

    def test_vault_lookup_found(self) -> None:
        """Should route to generate when curriculum found with good confidence."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            vault_found=True,
            vault_confidence=0.92,
        )
        
        result = vault_lookup_decision(state)
        assert result == "found"

    def test_vault_lookup_cold_start(self) -> None:
        """Should route to cold start when curriculum not found."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            vault_found=False,
        )
        
        result = vault_lookup_decision(state)
        assert result == "cold_start"

    def test_vault_lookup_low_confidence(self) -> None:
        """Should route to cold start when confidence too low."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            vault_found=True,
            vault_confidence=0.6,  # Below 0.8 threshold
        )
        
        result = vault_lookup_decision(state)
        assert result == "cold_start"

    def test_scout_no_urls_halts(self) -> None:
        """Should halt when scout finds no URLs."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            candidate_urls=[],
        )
        
        result = after_scout_decision(state)
        assert result == "halt"

    def test_scout_with_urls_continues(self) -> None:
        """Should continue when scout finds URLs."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            candidate_urls=["https://example.com/curriculum.pdf"],
        )
        
        result = after_scout_decision(state)
        assert result == "continue"

    def test_gatekeeper_no_approved_triggers_alert(self) -> None:
        """Should trigger human alert when no sources approved."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            approved_source_url=None,
        )
        
        result = after_gatekeeper_decision(state)
        assert result == "human_alert"

    def test_generate_low_coverage_triggers_alert(self) -> None:
        """Blueprint: coverage < 0.8 → human alert."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            generation_coverage=0.7,  # Below 0.8 threshold
        )
        
        result = after_generate_decision(state)
        assert result == "human_alert"

    def test_generate_good_coverage_ends(self) -> None:
        """Should end successfully with good coverage."""
        state = GraphState(
            request_id=uuid4(),
            raw_prompt="test",
            generation_coverage=0.92,
        )
        
        result = after_generate_decision(state)
        assert result == "end"


class TestGraphExecution:
    """Tests for actual graph execution."""

    def test_graph_processes_request(self) -> None:
        """Graph should process a request through nodes."""
        compiled = compile_curriculum_graph()
        initial_state = create_initial_state("Grade 9 Biology for Nigeria")
        
        # Convert to dict for LangGraph
        state_dict = initial_state.model_dump()
        
        # Run the graph
        # Note: This uses mock implementations, so it should complete
        final_state = compiled.invoke(state_dict)
        
        # Verify execution happened
        assert final_state is not None
        assert "node_history" in final_state
        assert len(final_state["node_history"]) > 0

    def test_graph_tracks_nodes(self) -> None:
        """Graph should track all node executions."""
        compiled = compile_curriculum_graph()
        initial_state = create_initial_state("Test prompt")
        
        state_dict = initial_state.model_dump()
        final_state = compiled.invoke(state_dict)
        
        # Should have executed at least normalize → jurisdiction → vault_lookup
        # node_history contains NodeExecution objects (as dicts after serialization)
        node_names = []
        for n in final_state["node_history"]:
            if isinstance(n, dict):
                node_names.append(n["node_name"])
            else:
                node_names.append(n.node_name)
        
        assert "NormalizeRequest" in node_names
        assert "ResolveJurisdiction" in node_names
        assert "VaultLookup" in node_names

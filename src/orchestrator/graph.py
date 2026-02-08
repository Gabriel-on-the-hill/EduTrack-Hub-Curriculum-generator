"""
Graph Builder (Blueprint Section 14)

This module constructs the LangGraph execution graph with:
- Nodes from nodes.py
- Conditional edges based on state
- Fallback tier enforcement
- Explicit halt states

Blueprint Section 14.4 requirements:
- Fallback tiers enforced
- Cost guards per-request
- No node retries infinitely (max 2)
- Halts are explicit states
"""

import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from src.orchestrator.state import GraphState, NodeStatus
from src.orchestrator.nodes import (
    normalize_request_node,
    resolve_jurisdiction_node,
    vault_lookup_node,
    enqueue_cold_start_node,
    scout_agent_node,
    gatekeeper_agent_node,
    architect_agent_node,
    embedder_node,
    vault_store_node,
    generate_node,
    human_alert_node,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONDITIONAL EDGE FUNCTIONS
# =============================================================================

def should_halt_after_normalize(state: GraphState) -> Literal["continue", "halt"]:
    """
    Check if we should halt after normalization.
    
    Halt if:
    - Normalization failed (has_error)
    - Confidence too low
    - Cost budget exceeded
    """
    if state.should_halt():
        return "halt"
    if state.has_error:
        return "halt"
    return "continue"


def should_halt_after_jurisdiction(state: GraphState) -> Literal["continue", "halt"]:
    """Check if we should halt after jurisdiction resolution."""
    if state.should_halt():
        return "halt"
    if state.has_error:
        return "halt"
    return "continue"


def vault_lookup_decision(state: GraphState) -> Literal["found", "cold_start", "halt"]:
    """
    Decide next step after vault lookup.
    
    Blueprint Section 13.3:
    - found = false → enqueue cold start
    - found = true → generate
    """
    if state.should_halt():
        return "halt"
    if state.has_error:
        return "halt"
    
    if state.vault_found and state.vault_confidence and state.vault_confidence >= 0.8:
        return "found"
    
    return "cold_start"


def after_cold_start_decision(state: GraphState) -> Literal["continue", "halt"]:
    """Decide whether to continue with Scout or halt."""
    if state.should_halt():
        return "halt"
    if state.has_error:
        return "halt"
    return "continue"


def after_scout_decision(state: GraphState) -> Literal["continue", "halt", "human_alert"]:
    """
    Decide next step after Scout.
    
    Blueprint Section 13.4:
    - candidate_urls.length = 0 → failed
    """
    if state.should_halt():
        return "halt"
    if state.has_error:
        if state.requires_human_alert:
            return "human_alert"
        return "halt"
    if len(state.candidate_urls) == 0:
        return "halt"
    return "continue"


def after_gatekeeper_decision(state: GraphState) -> Literal["continue", "halt", "human_alert"]:
    """
    Decide next step after Gatekeeper.
    
    Blueprint Section 13.5:
    - approved_sources = 0 → failed
    - status = conflicted → human alert
    """
    if state.should_halt():
        return "halt"
    if state.has_error:
        if state.requires_human_alert:
            return "human_alert"
        return "halt"
    if not state.approved_source_url:
        return "human_alert"
    return "continue"


def after_architect_decision(state: GraphState) -> Literal["continue", "halt", "human_alert"]:
    """
    Decide next step after Architect.
    
    Blueprint Section 13.6:
    - competencies = 0 → failed
    - average_confidence < 0.75 → low_confidence
    """
    if state.should_halt():
        return "halt"
    if state.has_error:
        return "halt"
    if state.competency_count == 0:
        return "halt"
    if state.extraction_confidence and state.extraction_confidence < 0.75:
        return "human_alert"
    return "continue"


def after_embedder_decision(state: GraphState) -> Literal["continue", "halt"]:
    """Decide whether to store or halt."""
    if state.should_halt():
        return "halt"
    if state.has_error:
        return "halt"
    return "continue"


def after_vault_store_decision(state: GraphState) -> Literal["generate", "halt"]:
    """Decide whether to generate or halt."""
    if state.should_halt():
        return "halt"
    if state.has_error:
        return "halt"
    return "generate"


def after_generate_decision(state: GraphState) -> Literal["end", "human_alert"]:
    """
    Decide final step after generation.
    
    Blueprint Section 9:
    - coverage < 0.8 → rejected (human alert)
    """
    if state.has_error:
        return "human_alert"
    if state.generation_coverage and state.generation_coverage < 0.8:
        return "human_alert"
    return "end"


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def build_curriculum_graph() -> StateGraph:
    """
    Build the LangGraph execution graph.
    
    Blueprint Section 14.1 Node Flow:
    NormalizeRequest → ResolveJurisdiction → VaultLookup →
    [EnqueueColdStart → Scout → Gatekeeper → Architect → Embedder → VaultStore] →
    Generate → END
    
    With conditional edges for:
    - Error handling
    - Vault found/not found
    - Human alerts
    - Explicit halts
    """
    
    # Initialize graph with our state type
    graph = StateGraph(GraphState)
    
    # =========================================================================
    # ADD NODES
    # =========================================================================
    
    graph.add_node("normalize_request", normalize_request_node)
    graph.add_node("resolve_jurisdiction", resolve_jurisdiction_node)
    graph.add_node("vault_lookup", vault_lookup_node)
    graph.add_node("enqueue_cold_start", enqueue_cold_start_node)
    graph.add_node("scout_agent", scout_agent_node)
    graph.add_node("gatekeeper_agent", gatekeeper_agent_node)
    graph.add_node("architect_agent", architect_agent_node)
    graph.add_node("embedder", embedder_node)
    graph.add_node("vault_store", vault_store_node)
    graph.add_node("generate", generate_node)
    graph.add_node("human_alert", human_alert_node)
    
    # =========================================================================
    # SET ENTRY POINT
    # =========================================================================
    
    graph.set_entry_point("normalize_request")
    
    # =========================================================================
    # ADD CONDITIONAL EDGES
    # =========================================================================
    
    # After normalization
    graph.add_conditional_edges(
        "normalize_request",
        should_halt_after_normalize,
        {
            "continue": "resolve_jurisdiction",
            "halt": END,
        }
    )
    
    # After jurisdiction resolution
    graph.add_conditional_edges(
        "resolve_jurisdiction",
        should_halt_after_jurisdiction,
        {
            "continue": "vault_lookup",
            "halt": END,
        }
    )
    
    # After vault lookup - key decision point
    graph.add_conditional_edges(
        "vault_lookup",
        vault_lookup_decision,
        {
            "found": "generate",  # Curriculum exists, go to generation
            "cold_start": "enqueue_cold_start",  # Need to fetch
            "halt": END,
        }
    )
    
    # After cold start enqueue
    graph.add_conditional_edges(
        "enqueue_cold_start",
        after_cold_start_decision,
        {
            "continue": "scout_agent",
            "halt": END,
        }
    )
    
    # After scout
    graph.add_conditional_edges(
        "scout_agent",
        after_scout_decision,
        {
            "continue": "gatekeeper_agent",
            "halt": END,
            "human_alert": "human_alert",
        }
    )
    
    # After gatekeeper
    graph.add_conditional_edges(
        "gatekeeper_agent",
        after_gatekeeper_decision,
        {
            "continue": "architect_agent",
            "halt": END,
            "human_alert": "human_alert",
        }
    )
    
    # After architect
    graph.add_conditional_edges(
        "architect_agent",
        after_architect_decision,
        {
            "continue": "embedder",
            "halt": END,
            "human_alert": "human_alert",
        }
    )
    
    # After embedder
    graph.add_conditional_edges(
        "embedder",
        after_embedder_decision,
        {
            "continue": "vault_store",
            "halt": END,
        }
    )
    
    # After vault store
    graph.add_conditional_edges(
        "vault_store",
        after_vault_store_decision,
        {
            "generate": "generate",
            "halt": END,
        }
    )
    
    # After generate - final decision
    graph.add_conditional_edges(
        "generate",
        after_generate_decision,
        {
            "end": END,
            "human_alert": "human_alert",
        }
    )
    
    # Human alert always ends
    graph.add_edge("human_alert", END)
    
    return graph


def compile_curriculum_graph():
    """
    Compile the graph for execution.
    
    Returns a compiled graph that can process GraphState.
    """
    graph = build_curriculum_graph()
    return graph.compile()


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def create_initial_state(raw_prompt: str) -> GraphState:
    """
    Create initial state for a new request.
    
    This is the entry point for processing a user request.
    """
    from uuid import uuid4
    
    return GraphState(
        request_id=uuid4(),
        raw_prompt=raw_prompt,
    )

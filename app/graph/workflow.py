"""
Learning graph workflow (Phase 12).

Simplified flow:

    START → build_profile → generate_roadmap → evaluate_roadmap
          → (refine ONCE) → save_roadmap
          → generate_prompts (includes save)
          → END

The prompt evaluation and refinement steps were removed.
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    build_profile_node,
    evaluate_roadmap_node,
    generate_prompts_node,
    generate_roadmap_node,
    refine_roadmap_node,
    save_roadmap_node,
)
from app.graph.state import LearningState

logger = structlog.get_logger(__name__)


# Canonical node names
NODE_BUILD_PROFILE = "build_profile"
NODE_GENERATE_ROADMAP = "generate_roadmap"
NODE_EVALUATE_ROADMAP = "evaluate_roadmap"
NODE_REFINE_ROADMAP = "refine_roadmap"
NODE_SAVE_ROADMAP = "save_roadmap"
NODE_GENERATE_PROMPTS = "generate_prompts"


# ============================================================
# Routing
# ============================================================

def route_after_roadmap_evaluation(state: LearningState) -> str:
    """Route after roadmap evaluation: refine (once) or save."""
    acceptable = state.get("roadmap_acceptable", False)
    iterations = state.get("roadmap_iterations", 0)

    if acceptable or iterations >= 1:
        return "save"
    return "refine"


# ============================================================
# Builder
# ============================================================

def build_learning_graph() -> CompiledStateGraph:
    """Build and compile the simplified learning graph."""
    log = logger.bind(graph="learning_workflow")
    log.info("building_learning_graph")

    graph: StateGraph = StateGraph(LearningState)

    # --- Nodes ---
    graph.add_node(NODE_BUILD_PROFILE, build_profile_node)
    graph.add_node(NODE_GENERATE_ROADMAP, generate_roadmap_node)
    graph.add_node(NODE_EVALUATE_ROADMAP, evaluate_roadmap_node)
    graph.add_node(NODE_REFINE_ROADMAP, refine_roadmap_node)
    graph.add_node(NODE_SAVE_ROADMAP, save_roadmap_node)
    graph.add_node(NODE_GENERATE_PROMPTS, generate_prompts_node)

    # --- Entry & linear flow ---
    graph.add_edge(START, NODE_BUILD_PROFILE)
    graph.add_edge(NODE_BUILD_PROFILE, NODE_GENERATE_ROADMAP)
    graph.add_edge(NODE_GENERATE_ROADMAP, NODE_EVALUATE_ROADMAP)

    # --- Roadmap refinement loop ---
    graph.add_conditional_edges(
        NODE_EVALUATE_ROADMAP,
        route_after_roadmap_evaluation,
        {
            "refine": NODE_REFINE_ROADMAP,
            "save": NODE_SAVE_ROADMAP,
        },
    )
    graph.add_edge(NODE_REFINE_ROADMAP, NODE_EVALUATE_ROADMAP)

    # --- From save_roadmap to briefs generation ---
    graph.add_edge(NODE_SAVE_ROADMAP, NODE_GENERATE_PROMPTS)
    graph.add_edge(NODE_GENERATE_PROMPTS, END)

    compiled = graph.compile()
    log.info("learning_graph_compiled")
    return compiled


# ============================================================
# Singleton
# ============================================================

_graph: CompiledStateGraph | None = None


def get_learning_graph() -> CompiledStateGraph:
    global _graph
    if _graph is None:
        _graph = build_learning_graph()
    return _graph


__all__ = [
    "build_learning_graph",
    "get_learning_graph",
    "NODE_BUILD_PROFILE",
    "NODE_GENERATE_ROADMAP",
    "NODE_EVALUATE_ROADMAP",
    "NODE_REFINE_ROADMAP",
    "NODE_SAVE_ROADMAP",
    "NODE_GENERATE_PROMPTS",
]

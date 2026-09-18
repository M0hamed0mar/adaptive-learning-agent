"""
Roadmap nodes (Phase 11 redesign).

Four nodes:
    - generate_roadmap_node  → uses roadmap_titles_agent
    - evaluate_roadmap_node  → uses roadmap_titles_critic
    - refine_roadmap_node    → uses roadmap_titles_refiner (once)
    - save_roadmap_node      → persists the final roadmap skeleton
"""

from __future__ import annotations

import structlog

from app.agents.roadmap.titles_agent import roadmap_titles_agent
from app.agents.roadmap.titles_critic import roadmap_titles_critic
from app.agents.roadmap.titles_refiner import roadmap_titles_refiner
from app.config.constants import ROADMAP_MAX_REFINEMENTS
from app.database import get_session
from app.graph.state import LearningState
from app.services import roadmap_service

logger = structlog.get_logger(__name__)


# ============================================================
# Generate
# ============================================================

async def generate_roadmap_node(state: LearningState) -> dict:
    """Generate a roadmap skeleton from the profile."""
    log = logger.bind(
        node="generate_roadmap", session_id=state.get("session_id")
    )
    log.info("generate_roadmap_started")

    profile = state["profile"]
    roadmap = await roadmap_titles_agent.generate(profile)

    log.info(
        "generate_roadmap_completed",
        title=roadmap.title,
        total_modules=roadmap.total_modules,
    )
    return {
        "roadmap": roadmap,
        "roadmap_iterations": 0,
        "roadmap_acceptable": False,
    }


# ============================================================
# Evaluate
# ============================================================

async def evaluate_roadmap_node(state: LearningState) -> dict:
    """Evaluate the current roadmap skeleton."""
    log = logger.bind(
        node="evaluate_roadmap",
        session_id=state.get("session_id"),
        iteration=state.get("roadmap_iterations", 0),
    )
    log.info("evaluate_roadmap_started")

    profile = state["profile"]
    roadmap = state["roadmap"]
    critique = await roadmap_titles_critic.evaluate(profile, roadmap)

    log.info(
        "evaluate_roadmap_completed",
        score=critique.score,
        is_acceptable=critique.is_acceptable,
    )
    return {
        "roadmap_critique": critique,
        "roadmap_acceptable": critique.is_acceptable,
    }


# ============================================================
# Refine
# ============================================================

async def refine_roadmap_node(state: LearningState) -> dict:
    """Refine the current roadmap skeleton (once)."""
    log = logger.bind(
        node="refine_roadmap",
        session_id=state.get("session_id"),
        iteration=state.get("roadmap_iterations", 0),
    )
    log.info("refine_roadmap_started")

    profile = state["profile"]
    roadmap = state["roadmap"]
    critique = state["roadmap_critique"]
    iteration = state.get("roadmap_iterations", 0)

    if iteration >= ROADMAP_MAX_REFINEMENTS:
        log.warning("refine_roadmap_max_reached", iteration=iteration)
        return {"roadmap_iterations": iteration}

    refined = await roadmap_titles_refiner.refine(profile, roadmap, critique)

    log.info("refine_roadmap_completed", new_title=refined.title)
    return {
        "roadmap": refined,
        "roadmap_iterations": iteration + 1,
    }


# ============================================================
# Save
# ============================================================

async def save_roadmap_node(state: LearningState) -> dict:
    """Persist the final roadmap skeleton."""
    log = logger.bind(
        node="save_roadmap", session_id=state.get("session_id")
    )
    log.info("save_roadmap_started")

    session_id = state["session_id"]
    roadmap = state["roadmap"]

    async with get_session() as db:
        existing = await roadmap_service.get_by_session(db, session_id)
        if existing is not None:
            await roadmap_service.replace_from_titles(db, existing, roadmap)
        else:
            await roadmap_service.create_from_titles(
                db, session_id=session_id, roadmap=roadmap
            )

    log.info("save_roadmap_completed")
    return {}


__all__ = [
    "generate_roadmap_node",
    "evaluate_roadmap_node",
    "refine_roadmap_node",
    "save_roadmap_node",
]

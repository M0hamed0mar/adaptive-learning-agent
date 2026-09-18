"""
Profile node (Phase 11 redesign).

Builds the UserProfile from the raw_input + 4 answers and persists it.
"""

from __future__ import annotations

import structlog

from app.agents.profile.agent import profile_agent
from app.config.constants import (
    DEFAULT_LANGUAGE,
    LearningGoal,
    LearningStyle,
    UserLevel,
)
from app.database import get_session
from app.graph.state import LearningState
from app.services import profile_service

logger = structlog.get_logger(__name__)


async def build_profile_node(state: LearningState) -> dict:
    """
    Build and persist a UserProfile for the session.

    Reads:
        - session_id
        - raw_input
        - profile_answers

    Produces:
        - profile
    """
    log = logger.bind(
        node="build_profile", session_id=state.get("session_id")
    )
    log.info("build_profile_started")

    session_id = state["session_id"]
    raw_input = state["raw_input"]
    answers = state.get("profile_answers", {})

    # Normalize answers with safe defaults.
    normalized = {
        "level": answers.get("level", UserLevel.BEGINNER.value),
        "goal": answers.get(
            "goal", LearningGoal.UNDERSTAND_FUNDAMENTALS.value
        ),
        "role": answers.get("role", "General Learner"),
        "learning_style": answers.get(
            "learning_style", LearningStyle.BALANCED.value
        ),
    }

    profile = await profile_agent.build_profile(
        topic="",  # topic is inferred from raw_input by the LLM
        raw_input=raw_input,
        answers=normalized,
        language=DEFAULT_LANGUAGE,
    )

    # Persist.
    async with get_session() as db:
        existing = await profile_service.get_by_session(db, session_id)
        if existing is not None:
            await profile_service.update_from_pydantic(db, existing, profile)
        else:
            await profile_service.create_from_pydantic(
                db, session_id=session_id, profile=profile
            )

    log.info("build_profile_completed", topic=profile.topic)
    return {"profile": profile}


__all__ = ["build_profile_node"]

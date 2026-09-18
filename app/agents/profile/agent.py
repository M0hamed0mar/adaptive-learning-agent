"""
Profile Agent (Phase 11 redesign).

Builds a `UserProfile` from the user's raw description + 4 answers.

Design:
    - The 4 answers (level, goal, role, learning_style) are provided
      by the user via the API/UI.
    - The `topic` and `language` are inferred by the LLM from
      `raw_input`.
    - If the user's raw_input is already rich, we still only fill the
      4 fields.

No `analyze_topic`, no `generate_questions` — the UI provides the
answers directly.
"""

from __future__ import annotations

import structlog

from app.config.constants import DEFAULT_LANGUAGE
from app.core.exceptions import (
    LLMError,
    ProfileAgentError,
)
from app.core.llm_client import llm_client
from app.prompts.profile import (
    PROFILE_BUILDING_SYSTEM,
    build_profile_building_prompt,
)
from app.schemas.profile import UserProfile

logger = structlog.get_logger(__name__)


# ============================================================
# Profile Agent
# ============================================================

class ProfileAgent:
    """Stateless agent that builds a `UserProfile`."""

    async def build_profile(
        self,
        *,
        topic: str,  # may be empty — the LLM will infer it
        raw_input: str,
        answers: dict[str, str],
        language: str = DEFAULT_LANGUAGE,
    ) -> UserProfile:
        """
        Build a `UserProfile`.

        Args:
            topic: The normalized topic, or "" to let the LLM infer it.
            raw_input: The user's original free-text description.
            answers: The 4 answers (level, goal, role, learning_style).
            language: Output language for lessons (default Arabic).

        Returns:
            A fully validated `UserProfile`.

        Raises:
            ProfileAgentError: If the LLM call fails or returns
                invalid data.
        """
        log = logger.bind(
            agent="ProfileAgent",
            step="build_profile",
            raw_input_preview=raw_input[:80],
            answer_fields=list(answers.keys()),
        )
        log.info("profile_building_started")

        prompt = build_profile_building_prompt(
            raw_input=raw_input,
            answers=answers,
            topic=topic,
            language=language,
        )

        try:
            profile = await llm_client.generate_structured(
                prompt=prompt,
                schema=UserProfile,
                instructions=PROFILE_BUILDING_SYSTEM,
                temperature=0.1,
                metadata={
                    "agent": "ProfileAgent",
                    "step": "build_profile",
                },
            )
        except LLMError as exc:
            log.error(
                "profile_building_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise ProfileAgentError(
                "Failed to build the user profile.",
                details={
                    "raw_input_preview": raw_input[:120],
                    "cause": str(exc),
                },
            ) from exc

        # Enforce raw_input and language exactly as provided.
        updates = {}
        if profile.raw_input != raw_input:
            updates["raw_input"] = raw_input
        if profile.language != language:
            updates["language"] = language
        if updates:
            log.debug("profile_fields_overridden", fields=list(updates.keys()))
            profile = profile.model_copy(update=updates)

        log.info(
            "profile_building_completed",
            topic=profile.topic,
            level=profile.level.value,
            goal=profile.goal.value,
        )
        return profile


# ============================================================
# Singleton
# ============================================================

profile_agent = ProfileAgent()


__all__ = ["ProfileAgent", "profile_agent"]

"""
Roadmap Titles Critic (Phase 11).

Evaluates a roadmap skeleton against the user's profile and against
general quality criteria. Returns a `RoadmapTitlesCritique`.

The critic is stateless and deterministic (low temperature).

Usage:
    from app.agents.roadmap.titles_critic import roadmap_titles_critic

    critique = await roadmap_titles_critic.evaluate(profile, roadmap)
    if critique.is_acceptable:
        proceed()
"""

from __future__ import annotations

import structlog

from app.config.constants import ROADMAP_APPROVAL_THRESHOLD
from app.core.exceptions import (
    LLMError,
    RoadmapAgentError,
)
from app.core.llm_client import llm_client
from app.prompts.roadmap_titles_evaluation import (
    ROADMAP_TITLES_EVALUATION_SYSTEM,
    build_roadmap_titles_evaluation_prompt,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import (
    RoadmapTitles,
    RoadmapTitlesCritique,
)

logger = structlog.get_logger(__name__)


class RoadmapTitlesCritic:
    """Stateless critic for RoadmapTitles."""

    async def evaluate(
        self,
        profile: UserProfile,
        roadmap: RoadmapTitles,
    ) -> RoadmapTitlesCritique:
        """
        Evaluate a roadmap skeleton against the user's profile.

        Args:
            profile: The user's learning profile.
            roadmap: The roadmap skeleton to evaluate.

        Returns:
            A `RoadmapTitlesCritique` with score, acceptance flag,
            issues, suggestions, and reasoning.

        Raises:
            RoadmapAgentError: If the LLM call fails.
        """
        log = logger.bind(
            agent="RoadmapTitlesCritic",
            step="evaluate",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
            roadmap_title=roadmap.title,
            total_modules=roadmap.total_modules,
        )
        log.info("roadmap_titles_evaluation_started")

        prompt = build_roadmap_titles_evaluation_prompt(profile, roadmap)

        try:
            critique = await llm_client.generate_structured(
                prompt=prompt,
                schema=RoadmapTitlesCritique,
                instructions=ROADMAP_TITLES_EVALUATION_SYSTEM,
                temperature=0.1,
                metadata={
                    "agent": "RoadmapTitlesCritic",
                    "step": "evaluate",
                },
            )
        except LLMError as exc:
            log.error(
                "roadmap_titles_evaluation_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise RoadmapAgentError(
                "Failed to evaluate roadmap titles.",
                details={
                    "topic": profile.topic,
                    "roadmap_title": roadmap.title,
                    "cause": str(exc),
                },
            ) from exc

        # Enforce threshold consistency.
        expected = critique.score >= ROADMAP_APPROVAL_THRESHOLD
        if critique.is_acceptable != expected:
            log.warning(
                "critic_acceptance_mismatch",
                score=critique.score,
                llm_acceptable=critique.is_acceptable,
                threshold=ROADMAP_APPROVAL_THRESHOLD,
            )
            critique = critique.model_copy(
                update={"is_acceptable": expected}
            )

        log.info(
            "roadmap_titles_evaluation_completed",
            score=critique.score,
            is_acceptable=critique.is_acceptable,
            issue_count=len(critique.issues),
            suggestion_count=len(critique.suggestions),
        )
        return critique


# ============================================================
# Singleton
# ============================================================

roadmap_titles_critic = RoadmapTitlesCritic()


__all__ = ["RoadmapTitlesCritic", "roadmap_titles_critic"]

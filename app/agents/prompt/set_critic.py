"""
Teaching Prompt Set Critic (Phase 11).

Evaluates a whole batch of teaching prompts and returns ONE critique.

The critic is stateless and deterministic (low temperature).

Usage:
    from app.agents.prompt.set_critic import teaching_set_critic

    critique = await teaching_set_critic.evaluate(profile, roadmap, prompt_set)
    if critique.is_acceptable:
        proceed()
"""

from __future__ import annotations

import structlog

from app.config.constants import PROMPT_SET_APPROVAL_THRESHOLD
from app.core.exceptions import (
    LLMError,
    PromptAgentError,
)
from app.core.llm_client import llm_client
from app.prompts.teaching_set_evaluation import (
    TEACHING_SET_EVALUATION_SYSTEM,
    build_teaching_set_evaluation_prompt,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles
from app.schemas.teaching import (
    TeachingPromptSet,
    TeachingPromptSetCritique,
)

logger = structlog.get_logger(__name__)


class TeachingPromptSetCritic:
    """Stateless batch critic for TeachingPromptSet."""

    async def evaluate(
        self,
        profile: UserProfile,
        roadmap: RoadmapTitles,
        prompt_set: TeachingPromptSet,
    ) -> TeachingPromptSetCritique:
        """
        Evaluate a batch of teaching prompts.

        Args:
            profile: The user's learning profile.
            roadmap: The roadmap skeleton (context).
            prompt_set: The batch to evaluate.

        Returns:
            A `TeachingPromptSetCritique`.

        Raises:
            PromptAgentError: If the LLM call fails.
        """
        log = logger.bind(
            agent="TeachingPromptSetCritic",
            step="evaluate",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
            prompt_count=len(prompt_set.prompts),
        )
        log.info("teaching_set_evaluation_started")

        # Flatten the prompt set to the (part_id, title, prompt) tuples
        # expected by the prompt builder.
        flat = [
            (p.part_id, p.title, p.prompt)
            for p in prompt_set.prompts
        ]

        user_prompt = build_teaching_set_evaluation_prompt(
            profile=profile,
            roadmap=roadmap,
            prompts=flat,
        )

        try:
            critique = await llm_client.generate_structured(
                prompt=user_prompt,
                schema=TeachingPromptSetCritique,
                instructions=TEACHING_SET_EVALUATION_SYSTEM,
                temperature=0.1,
                max_tokens=2048,
                metadata={
                    "agent": "TeachingPromptSetCritic",
                    "step": "evaluate",
                },
            )
        except LLMError as exc:
            log.error(
                "teaching_set_evaluation_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise PromptAgentError(
                "Failed to evaluate the teaching prompt set.",
                details={
                    "topic": profile.topic,
                    "prompt_count": len(prompt_set.prompts),
                    "cause": str(exc),
                },
            ) from exc

        # Enforce threshold consistency.
        expected = critique.score >= PROMPT_SET_APPROVAL_THRESHOLD
        if critique.is_acceptable != expected:
            log.warning(
                "teaching_set_critic_acceptance_mismatch",
                score=critique.score,
                llm_acceptable=critique.is_acceptable,
                threshold=PROMPT_SET_APPROVAL_THRESHOLD,
            )
            critique = critique.model_copy(
                update={"is_acceptable": expected}
            )

        log.info(
            "teaching_set_evaluation_completed",
            score=critique.score,
            is_acceptable=critique.is_acceptable,
            issue_count=len(critique.issues),
            suggestion_count=len(critique.suggestions),
        )
        return critique


# ============================================================
# Singleton
# ============================================================

teaching_set_critic = TeachingPromptSetCritic()


__all__ = ["TeachingPromptSetCritic", "teaching_set_critic"]

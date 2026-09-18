"""
Teaching Prompt Set Refiner (Phase 11).

Refines a whole batch of teaching prompts in ONE call, based on a
critique. The refiner is stateless.

Usage:
    from app.agents.prompt.set_refiner import teaching_set_refiner

    refined = await teaching_set_refiner.refine(
        profile, roadmap, prompt_set, critique
    )
"""

from __future__ import annotations

import structlog

from app.core.exceptions import (
    LLMError,
    PromptAgentError,
)
from app.core.llm_client import llm_client
from app.prompts.teaching_set import (
    TEACHING_SET_REFINEMENT_SYSTEM,
    build_teaching_set_refinement_prompt,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles
from app.schemas.teaching import (
    TeachingPromptItem,
    TeachingPromptSet,
    TeachingPromptSetCritique,
)

logger = structlog.get_logger(__name__)


# Minimum acceptable length for a refined prompt.
_MIN_PROMPT_LENGTH = 100


# ============================================================
# Refiner
# ============================================================

class TeachingPromptSetRefiner:
    """Stateless batch refiner for TeachingPromptSet."""

    async def refine(
        self,
        profile: UserProfile,
        roadmap: RoadmapTitles,
        prompt_set: TeachingPromptSet,
        critique: TeachingPromptSetCritique,
    ) -> TeachingPromptSet:
        """
        Refine a batch of teaching prompts based on the critic's feedback.

        Args:
            profile: The user's learning profile.
            roadmap: The roadmap skeleton.
            prompt_set: The current batch.
            critique: The critic's evaluation.

        Returns:
            A refined `TeachingPromptSet`.

        Raises:
            PromptAgentError: If the LLM call fails or returns
                invalid data.
        """
        log = logger.bind(
            agent="TeachingPromptSetRefiner",
            step="refine",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
            prompt_count=len(prompt_set.prompts),
            critique_score=critique.score,
            issue_count=len(critique.issues),
            suggestion_count=len(critique.suggestions),
        )
        log.info("teaching_set_refinement_started")

        # Flatten the current prompt set.
        current_flat = [
            (p.part_id, p.title, p.prompt)
            for p in prompt_set.prompts
        ]

        user_prompt = build_teaching_set_refinement_prompt(
            profile=profile,
            roadmap=roadmap,
            current_briefs=current_flat,
            critique_score=critique.score,
            issues=critique.issues,
            suggestions=critique.suggestions,
            reasoning=critique.reasoning,
        )

        try:
            result = await llm_client.generate_structured(
                prompt=user_prompt,
                schema=TeachingPromptSet,
                instructions=TEACHING_SET_REFINEMENT_SYSTEM,
                temperature=0.4,
                max_tokens=8192,
                metadata={
                    "agent": "TeachingPromptSetRefiner",
                    "step": "refine",
                },
            )
        except LLMError as exc:
            log.error(
                "teaching_set_refinement_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise PromptAgentError(
                "Failed to refine the teaching prompt set.",
                details={
                    "topic": profile.topic,
                    "prompt_count": len(prompt_set.prompts),
                    "cause": str(exc),
                },
            ) from exc

        # Normalize the output with the same rules as the generator.
        normalized = self._normalize(
            result=result,
            original=prompt_set,
            log=log,
        )

        log.info(
            "teaching_set_refinement_completed",
            prompt_count=len(normalized.prompts),
        )
        return normalized

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------

    def _normalize(
        self,
        *,
        result: TeachingPromptSet,
        original: TeachingPromptSet,
        log: structlog.stdlib.BoundLogger,
    ) -> TeachingPromptSet:
        """
        Align the refined output to the original positions.

        We trust our own (part_id, title) mapping, not the LLM's.
        """
        expected_count = len(original.prompts)
        received = result.prompts

        if len(received) > expected_count:
            log.warning(
                "refined_set_too_many_prompts",
                received=len(received),
                expected=expected_count,
            )
            received = received[:expected_count]

        if len(received) < expected_count:
            log.error(
                "refined_set_too_few_prompts",
                received=len(received),
                expected=expected_count,
            )
            raise PromptAgentError(
                "Refiner returned fewer teaching prompts than expected.",
                details={
                    "expected": expected_count,
                    "received": len(received),
                },
            )

        normalized_items: list[TeachingPromptItem] = []
        for original_item, item in zip(original.prompts, received):
            prompt_text = item.prompt.strip()

            if len(prompt_text) < _MIN_PROMPT_LENGTH:
                log.error(
                    "refined_prompt_too_short",
                    part_id=original_item.part_id,
                    length=len(prompt_text),
                )
                raise PromptAgentError(
                    "A refined teaching prompt is too short.",
                    details={
                        "part_id": original_item.part_id,
                        "length": len(prompt_text),
                    },
                )

            normalized_items.append(
                TeachingPromptItem(
                    part_id=original_item.part_id,
                    title=original_item.title,
                    prompt=prompt_text,
                )
            )

        return TeachingPromptSet(prompts=normalized_items)


# ============================================================
# Singleton
# ============================================================

teaching_set_refiner = TeachingPromptSetRefiner()


__all__ = ["TeachingPromptSetRefiner", "teaching_set_refiner"]

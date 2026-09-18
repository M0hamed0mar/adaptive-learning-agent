"""
Teaching Prompt Set Workflow (Phase 11).

Orchestrates the batch pipeline:

    1. Generate a full set of teaching prompts (ONE call).
    2. Evaluate it with the batch critic (ONE call).
    3. If below threshold, refine ONCE and re-evaluate.

Design notes:
    - Only ONE refinement pass.
    - The workflow is the single entry point for downstream phases.

Usage:
    from app.agents.prompt.set_workflow import teaching_set_workflow

    result = await teaching_set_workflow.run(profile, roadmap)
    print(len(result.prompt_set.prompts))
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.agents.prompt.set_critic import teaching_set_critic
from app.agents.prompt.set_generator import teaching_set_generator
from app.agents.prompt.set_refiner import teaching_set_refiner
from app.config.constants import (
    PROMPT_SET_APPROVAL_THRESHOLD,
    PROMPT_SET_MAX_REFINEMENTS,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles
from app.schemas.teaching import (
    TeachingPromptSet,
    TeachingPromptSetCritique,
)

logger = structlog.get_logger(__name__)


# ============================================================
# Result
# ============================================================

@dataclass
class TeachingPromptSetResult:
    """
    Final output of the teaching prompt set workflow.

    Attributes:
        prompt_set: The best batch found.
        final_critique: The critique of the returned batch.
        iterations: Number of refinement iterations applied.
        history: All critiques, in order.
    """

    prompt_set: TeachingPromptSet
    final_critique: TeachingPromptSetCritique
    iterations: int
    history: list[TeachingPromptSetCritique]


# ============================================================
# Workflow
# ============================================================

class TeachingPromptSetWorkflow:
    """Stateless orchestrator of the batch prompt pipeline."""

    async def run(
        self,
        profile: UserProfile,
        roadmap: RoadmapTitles,
    ) -> TeachingPromptSetResult:
        """
        Run the full batch pipeline.

        Args:
            profile: The user's learning profile.
            roadmap: The roadmap skeleton.

        Returns:
            A TeachingPromptSetResult.

        Raises:
            PromptAgentError: If generation, evaluation, or refinement
                fails irrecoverably.
        """
        log = logger.bind(
            agent="TeachingPromptSetWorkflow",
            step="run",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
        )
        log.info("teaching_set_workflow_started")

        # --- Step 1: Generate ---
        prompt_set = await teaching_set_generator.generate(profile, roadmap)
        log.info(
            "teaching_set_workflow_generated",
            prompt_count=len(prompt_set.prompts),
        )

        # --- Step 2: Evaluate ---
        critique = await teaching_set_critic.evaluate(
            profile, roadmap, prompt_set
        )
        history: list[TeachingPromptSetCritique] = [critique]

        log.info(
            "teaching_set_workflow_evaluated",
            iteration=0,
            score=critique.score,
            is_acceptable=critique.is_acceptable,
        )

        if critique.is_acceptable:
            log.info(
                "teaching_set_workflow_completed",
                iterations=0,
                final_score=critique.score,
            )
            return TeachingPromptSetResult(
                prompt_set=prompt_set,
                final_critique=critique,
                iterations=0,
                history=history,
            )

        # --- Step 3: Refinement (max 1 iteration) ---
        best_set = prompt_set
        best_critique = critique
        iterations = 0

        for iteration in range(1, PROMPT_SET_MAX_REFINEMENTS + 1):
            log.info(
                "teaching_set_workflow_refining",
                iteration=iteration,
                current_score=best_critique.score,
            )

            refined = await teaching_set_refiner.refine(
                profile, roadmap, best_set, best_critique
            )
            new_critique = await teaching_set_critic.evaluate(
                profile, roadmap, refined
            )

            iterations = iteration
            history.append(new_critique)

            log.info(
                "teaching_set_workflow_iteration_completed",
                iteration=iteration,
                previous_score=best_critique.score,
                new_score=new_critique.score,
                improved=new_critique.score > best_critique.score,
            )

            if new_critique.score > best_critique.score:
                best_set = refined
                best_critique = new_critique

            if new_critique.is_acceptable:
                log.info(
                    "teaching_set_workflow_completed",
                    iterations=iterations,
                    final_score=new_critique.score,
                )
                return TeachingPromptSetResult(
                    prompt_set=best_set,
                    final_critique=best_critique,
                    iterations=iterations,
                    history=history,
                )

        # --- Best effort fallback ---
        log.warning(
            "teaching_set_workflow_best_effort",
            iterations=iterations,
            final_score=best_critique.score,
            threshold=PROMPT_SET_APPROVAL_THRESHOLD,
        )
        return TeachingPromptSetResult(
            prompt_set=best_set,
            final_critique=best_critique,
            iterations=iterations,
            history=history,
        )


# ============================================================
# Singleton
# ============================================================

teaching_set_workflow = TeachingPromptSetWorkflow()


__all__ = [
    "TeachingPromptSetWorkflow",
    "TeachingPromptSetResult",
    "teaching_set_workflow",
]

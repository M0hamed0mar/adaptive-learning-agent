"""
Roadmap Titles Workflow (Phase 11).

Orchestrates the roadmap titles pipeline:

    1. Generate a roadmap skeleton.
    2. Evaluate it with the critic.
    3. If the score is below the approval threshold, refine ONCE
       and re-evaluate.
    4. Return the best roadmap found (highest score).

Design notes:
    - Only ONE refinement pass — the new design aims for speed.
    - The workflow is the single entry point for downstream phases.

Usage:
    from app.agents.roadmap.titles_workflow import roadmap_titles_workflow

    result = await roadmap_titles_workflow.run(profile)
    print(result.roadmap.title)
    print(result.final_critique.score)
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.agents.roadmap.titles_agent import roadmap_titles_agent
from app.agents.roadmap.titles_critic import roadmap_titles_critic
from app.agents.roadmap.titles_refiner import roadmap_titles_refiner
from app.config.constants import (
    ROADMAP_APPROVAL_THRESHOLD,
    ROADMAP_MAX_REFINEMENTS,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles, RoadmapTitlesCritique

logger = structlog.get_logger(__name__)


# ============================================================
# Result
# ============================================================

@dataclass
class RoadmapTitlesResult:
    """
    Final output of the roadmap titles workflow.

    Attributes:
        roadmap: The best roadmap found.
        final_critique: The critique of the returned roadmap.
        iterations: Number of refinement iterations applied.
        history: All critiques, in order.
    """

    roadmap: RoadmapTitles
    final_critique: RoadmapTitlesCritique
    iterations: int
    history: list[RoadmapTitlesCritique]


# ============================================================
# Workflow
# ============================================================

class RoadmapTitlesWorkflow:
    """Stateless orchestrator of the roadmap titles pipeline."""

    async def run(self, profile: UserProfile) -> RoadmapTitlesResult:
        """
        Run the full roadmap titles pipeline for a profile.

        Args:
            profile: The user's learning profile.

        Returns:
            A RoadmapTitlesResult.

        Raises:
            RoadmapAgentError: If generation, evaluation, or refinement
                fails irrecoverably.
        """
        log = logger.bind(
            agent="RoadmapTitlesWorkflow",
            step="run",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
        )
        log.info("roadmap_titles_workflow_started")

        # --- Step 1: Generate ---
        roadmap = await roadmap_titles_agent.generate(profile)
        log.info(
            "roadmap_titles_workflow_generated",
            title=roadmap.title,
            total_modules=roadmap.total_modules,
        )

        # --- Step 2: Evaluate ---
        critique = await roadmap_titles_critic.evaluate(profile, roadmap)
        history: list[RoadmapTitlesCritique] = [critique]

        log.info(
            "roadmap_titles_workflow_evaluated",
            iteration=0,
            score=critique.score,
            is_acceptable=critique.is_acceptable,
        )

        if critique.is_acceptable:
            log.info(
                "roadmap_titles_workflow_completed",
                iterations=0,
                final_score=critique.score,
            )
            return RoadmapTitlesResult(
                roadmap=roadmap,
                final_critique=critique,
                iterations=0,
                history=history,
            )

        # --- Step 3: Refinement loop (max 1 iteration) ---
        best_roadmap = roadmap
        best_critique = critique
        iterations = 0

        for iteration in range(1, ROADMAP_MAX_REFINEMENTS + 1):
            log.info(
                "roadmap_titles_workflow_refining",
                iteration=iteration,
                current_score=best_critique.score,
            )

            refined = await roadmap_titles_refiner.refine(
                profile, best_roadmap, best_critique
            )
            new_critique = await roadmap_titles_critic.evaluate(
                profile, refined
            )

            iterations = iteration
            history.append(new_critique)

            log.info(
                "roadmap_titles_workflow_iteration_completed",
                iteration=iteration,
                previous_score=best_critique.score,
                new_score=new_critique.score,
                improved=new_critique.score > best_critique.score,
            )

            # Keep the best across iterations.
            if new_critique.score > best_critique.score:
                best_roadmap = refined
                best_critique = new_critique

            if new_critique.is_acceptable:
                log.info(
                    "roadmap_titles_workflow_completed",
                    iterations=iterations,
                    final_score=new_critique.score,
                )
                return RoadmapTitlesResult(
                    roadmap=best_roadmap,
                    final_critique=best_critique,
                    iterations=iterations,
                    history=history,
                )

        # --- Best effort fallback ---
        log.warning(
            "roadmap_titles_workflow_best_effort",
            iterations=iterations,
            final_score=best_critique.score,
            threshold=ROADMAP_APPROVAL_THRESHOLD,
        )
        return RoadmapTitlesResult(
            roadmap=best_roadmap,
            final_critique=best_critique,
            iterations=iterations,
            history=history,
        )


# ============================================================
# Singleton
# ============================================================

roadmap_titles_workflow = RoadmapTitlesWorkflow()


__all__ = [
    "RoadmapTitlesWorkflow",
    "RoadmapTitlesResult",
    "roadmap_titles_workflow",
]

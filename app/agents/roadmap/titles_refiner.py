"""
Roadmap Titles Refiner (Phase 11).

Takes a roadmap skeleton + a critique, and produces an improved
roadmap skeleton. The refiner is stateless.

Usage:
    from app.agents.roadmap.titles_refiner import roadmap_titles_refiner

    refined = await roadmap_titles_refiner.refine(profile, roadmap, critique)
"""

from __future__ import annotations

import structlog

from app.config.constants import (
    MAX_MODULE_PARTS,
    MAX_ROADMAP_MODULES,
)
from app.core.exceptions import (
    LLMError,
    RoadmapAgentError,
)
from app.core.llm_client import llm_client
from app.prompts.roadmap_titles import (
    ROADMAP_TITLES_SYSTEM,
    build_roadmap_titles_prompt,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import (
    ModuleTitle,
    RoadmapTitles,
    RoadmapTitlesCritique,
)

logger = structlog.get_logger(__name__)


# ============================================================
# Refiner
# ============================================================

class RoadmapTitlesRefiner:
    """Stateless refiner for RoadmapTitles."""

    async def refine(
        self,
        profile: UserProfile,
        roadmap: RoadmapTitles,
        critique: RoadmapTitlesCritique,
    ) -> RoadmapTitles:
        """
        Refine a roadmap skeleton based on the critic's feedback.

        Args:
            profile: The user's learning profile.
            roadmap: The current roadmap skeleton.
            critique: The critic's evaluation.

        Returns:
            A refined `RoadmapTitles`.

        Raises:
            RoadmapAgentError: If the LLM call fails or the response
                cannot be normalized.
        """
        log = logger.bind(
            agent="RoadmapTitlesRefiner",
            step="refine",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
            roadmap_title=roadmap.title,
            critique_score=critique.score,
            issue_count=len(critique.issues),
            suggestion_count=len(critique.suggestions),
        )
        log.info("roadmap_titles_refinement_started")

        # We reuse the generation prompt but append explicit refinement
        # instructions. This keeps the two prompts consistent and lets
        # us avoid duplicating the large "how to write titles" block.
        base_prompt = build_roadmap_titles_prompt(profile)
        refinement_prompt = self._build_refinement_prompt(
            base_prompt=base_prompt,
            roadmap=roadmap,
            critique=critique,
        )

        try:
            refined = await llm_client.generate_structured(
                prompt=refinement_prompt,
                schema=RoadmapTitles,
                instructions=ROADMAP_TITLES_SYSTEM,
                temperature=0.4,
                metadata={
                    "agent": "RoadmapTitlesRefiner",
                    "step": "refine",
                },
            )
        except LLMError as exc:
            log.error(
                "roadmap_titles_refinement_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise RoadmapAgentError(
                "Failed to refine roadmap titles.",
                details={
                    "topic": profile.topic,
                    "roadmap_title": roadmap.title,
                    "cause": str(exc),
                },
            ) from exc

        # Normalize the refined roadmap with the same rules as the agent.
        normalized = self._normalize(refined, log=log)

        log.info(
            "roadmap_titles_refinement_completed",
            new_title=normalized.title,
            total_modules=normalized.total_modules,
        )
        return normalized

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------

    def _build_refinement_prompt(
        self,
        *,
        base_prompt: str,
        roadmap: RoadmapTitles,
        critique: RoadmapTitlesCritique,
    ) -> str:
        """Build the user prompt for roadmap refinement."""
        lines: list[str] = []
        lines.append(
            "أنت الآن في مرحلة التحسين. حسّن هيكل الـroadmap التالي "
            "بناءً على ملاحظات الناقد."
        )
        lines.append("")
        lines.append("--- السياق الأصلي ---")
        lines.append(base_prompt)
        lines.append("")
        lines.append("--- الـroadmap الحالي ---")
        lines.append(f"Title:   {roadmap.title}")
        lines.append(f"Summary: {roadmap.summary}")
        for i, module in enumerate(roadmap.modules, start=1):
            lines.append(f"  [M{i}] {module.title}")
            for j, part in enumerate(module.parts, start=1):
                lines.append(f"      [{i}-{j}] {part.title}")
        lines.append("")
        lines.append("--- ملاحظات الناقد ---")
        lines.append(f"Score: {critique.score} / 10")
        lines.append("Issues:")
        for issue in critique.issues or ["(none)"]:
            lines.append(f"  - {issue}")
        lines.append("Suggestions:")
        for sug in critique.suggestions or ["(none)"]:
            lines.append(f"  - {sug}")
        lines.append(f"Reasoning: {critique.reasoning}")
        lines.append("")
        lines.append("--- المطلوب ---")
        lines.append("- عالج كل issue.")
        lines.append("- طبّق كل suggestion.")
        lines.append("- حافظ على ما هو جيد.")
        lines.append("- نفس القواعد الصارمة (تخصيص، حجم الـpart صغير، إلخ).")
        lines.append("- أعد JSON كاملًا.")
        return "\n".join(lines)

    def _normalize(
        self,
        roadmap: RoadmapTitles,
        *,
        log: structlog.stdlib.BoundLogger,
    ) -> RoadmapTitles:
        """Same normalization as the agent (shared behavior)."""
        modules = list(roadmap.modules)
        if len(modules) > MAX_ROADMAP_MODULES:
            log.warning(
                "refined_roadmap_too_many_modules",
                received=len(modules),
                max_allowed=MAX_ROADMAP_MODULES,
            )
            modules = modules[:MAX_ROADMAP_MODULES]

        if not modules:
            raise RoadmapAgentError(
                "Refined roadmap has no modules.",
                details={"title": roadmap.title},
            )

        normalized_modules: list[ModuleTitle] = []
        for module in modules:
            parts = list(module.parts)
            if len(parts) > MAX_MODULE_PARTS:
                log.warning(
                    "refined_module_too_many_parts",
                    module_title=module.title,
                    received=len(parts),
                    max_allowed=MAX_MODULE_PARTS,
                )
                parts = parts[:MAX_MODULE_PARTS]

            valid = [p for p in parts if len(p.title.strip()) >= 3]
            if len(valid) < 2:
                log.warning(
                    "refined_module_dropped",
                    module_title=module.title,
                    part_count=len(valid),
                )
                continue

            normalized_modules.append(
                module.model_copy(update={"parts": valid})
            )

        if not normalized_modules:
            raise RoadmapAgentError(
                "All modules were dropped during refinement.",
                details={"title": roadmap.title},
            )

        return roadmap.model_copy(
            update={
                "modules": normalized_modules,
                "total_modules": len(normalized_modules),
            }
        )


# ============================================================
# Singleton
# ============================================================

roadmap_titles_refiner = RoadmapTitlesRefiner()


__all__ = ["RoadmapTitlesRefiner", "roadmap_titles_refiner"]

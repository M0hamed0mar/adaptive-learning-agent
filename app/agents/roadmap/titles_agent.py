"""
Roadmap Titles Agent (Phase 11).

Generates a roadmap *skeleton* from a UserProfile:
    - module titles
    - part titles

No content, no objectives, no teaching plans. Just the structure.
The agent is stateless.

Usage:
    from app.agents.roadmap.titles_agent import roadmap_titles_agent

    titles = await roadmap_titles_agent.generate(profile)
    print(titles.title)
    for m in titles.modules:
        print(f"  [{m.title}]")
        for p in m.parts:
            print(f"    - {p.title}")
"""

from __future__ import annotations

import re

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
    PartTitle,
    RoadmapTitles,
)

logger = structlog.get_logger(__name__)


# ============================================================
# Constants
# ============================================================

# Minimum length of a reasonable title.
_MIN_TITLE_LEN = 3


# ============================================================
# Agent
# ============================================================

class RoadmapTitlesAgent:
    """
    Stateless agent that generates a roadmap skeleton from a profile.
    """

    async def generate(self, profile: UserProfile) -> RoadmapTitles:
        """
        Generate a roadmap skeleton for the given profile.

        Args:
            profile: The user's learning profile.

        Returns:
            A validated `RoadmapTitles`.

        Raises:
            RoadmapAgentError: If the LLM call fails or the response
                cannot be validated/normalized.
        """
        log = logger.bind(
            agent="RoadmapTitlesAgent",
            step="generate",
            topic=profile.topic,
            level=profile.level.value,
            goal=profile.goal.value,
            role=profile.role,
        )
        log.info("roadmap_titles_generation_started")

        prompt = build_roadmap_titles_prompt(profile)

        try:
            roadmap = await llm_client.generate_structured(
                prompt=prompt,
                schema=RoadmapTitles,
                instructions=ROADMAP_TITLES_SYSTEM,
                temperature=0.5,
                metadata={
                    "agent": "RoadmapTitlesAgent",
                    "step": "generate",
                },
            )
        except LLMError as exc:
            log.error(
                "roadmap_titles_generation_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise RoadmapAgentError(
                "Failed to generate roadmap titles.",
                details={
                    "topic": profile.topic,
                    "role": profile.role,
                    "cause": str(exc),
                },
            ) from exc

        # Normalize + validate the response.
        normalized = self._normalize(roadmap, log=log)

        log.info(
            "roadmap_titles_generation_completed",
            title=normalized.title,
            total_modules=normalized.total_modules,
            total_parts=sum(len(m.parts) for m in normalized.modules),
        )
        return normalized

    # --------------------------------------------------------
    # Normalization
    # --------------------------------------------------------

    def _normalize(
        self,
        roadmap: RoadmapTitles,
        *,
        log: structlog.stdlib.BoundLogger,
    ) -> RoadmapTitles:
        """
        Apply safe, deterministic fixes to a roadmap:

            - Truncate modules to MAX_ROADMAP_MODULES.
            - Truncate parts per module to MAX_MODULE_PARTS.
            - Drop parts with titles shorter than _MIN_TITLE_LEN.
            - Drop modules with fewer than 2 valid parts.
            - Sync total_modules.

        Raises RoadmapAgentError if we cannot produce a usable roadmap.
        """
        modules = list(roadmap.modules)

        # Truncate modules.
        if len(modules) > MAX_ROADMAP_MODULES:
            log.warning(
                "roadmap_titles_too_many_modules",
                received=len(modules),
                max_allowed=MAX_ROADMAP_MODULES,
            )
            modules = modules[:MAX_ROADMAP_MODULES]

        if not modules:
            raise RoadmapAgentError(
                "LLM returned a roadmap with no modules.",
                details={"title": roadmap.title},
            )

        normalized_modules: list[ModuleTitle] = []
        for module in modules:
            # Truncate parts.
            parts = list(module.parts)
            if len(parts) > MAX_MODULE_PARTS:
                log.warning(
                    "module_too_many_parts",
                    module_title=module.title,
                    received=len(parts),
                    max_allowed=MAX_MODULE_PARTS,
                )
                parts = parts[:MAX_MODULE_PARTS]

            # Drop parts with too-short titles.
            valid_parts = [
                p for p in parts
                if len(p.title.strip()) >= _MIN_TITLE_LEN
            ]
            if len(valid_parts) != len(parts):
                log.warning(
                    "module_parts_dropped_too_short",
                    module_title=module.title,
                    dropped=len(parts) - len(valid_parts),
                )

            if len(valid_parts) < 2:
                log.warning(
                    "module_dropped_too_few_parts",
                    module_title=module.title,
                    part_count=len(valid_parts),
                )
                continue

            normalized_modules.append(
                module.model_copy(update={"parts": valid_parts})
            )

        if not normalized_modules:
            raise RoadmapAgentError(
                "All modules were dropped during normalization.",
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

roadmap_titles_agent = RoadmapTitlesAgent()


__all__ = ["RoadmapTitlesAgent", "roadmap_titles_agent"]

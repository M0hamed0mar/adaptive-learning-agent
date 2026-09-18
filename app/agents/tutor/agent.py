"""
Tutor Agent (Phase 11 redesign).

Generates a lesson for a single part, guided by a TeachingPrompt.
The teaching prompt may come either from:
    - A full `TeachingPrompt` object (legacy), OR
    - A `TeachingPromptItem` (from the batch set).

Both paths lead to the same `teach` logic.
"""

from __future__ import annotations

import structlog

from app.core.exceptions import (
    LLMError,
    TutorAgentError,
)
from app.core.llm_client import llm_client
from app.prompts.tutor import (
    TUTOR_SYSTEM,
    build_lesson_metadata,
    build_tutor_user_prompt,
)
from app.schemas.lesson import Lesson, LessonMetadata
from app.schemas.profile import UserProfile
from app.schemas.roadmap import ModuleTitle, PartTitle
from app.schemas.teaching import TeachingPromptItem

logger = structlog.get_logger(__name__)


# Minimum acceptable lesson length.
_MIN_LESSON_LENGTH = 200


# ============================================================
# Tutor Agent
# ============================================================

class TutorAgent:
    """Stateless agent that generates a lesson for a part."""

    # --------------------------------------------------------
    # Public API — batch-item path
    # --------------------------------------------------------

    async def teach_from_prompt_item(
        self,
        *,
        profile: UserProfile,
        module: ModuleTitle,
        part: PartTitle,
        part_id: str,
        prompt_item: TeachingPromptItem,
    ) -> Lesson:
        """
        Generate a lesson using a `TeachingPromptItem`.

        This is the main path used by the lazy-generation endpoint.
        """
        return await self._teach(
            profile=profile,
            module=module,
            part=part,
            part_id=part_id,
            system_instructions=prompt_item.prompt,
        )

    # --------------------------------------------------------
    # Internal
    # --------------------------------------------------------

    async def _teach(
        self,
        *,
        profile: UserProfile,
        module: ModuleTitle,
        part: PartTitle,
        part_id: str,
        system_instructions: str,
    ) -> Lesson:
        log = logger.bind(
            agent="TutorAgent",
            step="teach",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
            part_id=part_id,
            part_title=part.title,
            prompt_length=len(system_instructions),
        )
        log.info("tutor_lesson_generation_started")

        # Fallback if the prompt is unusually short.
        if len(system_instructions) < 50:
            log.warning(
                "teaching_prompt_too_short_using_fallback",
                length=len(system_instructions),
            )
            system_instructions = TUTOR_SYSTEM
        else:
            # Combine the global rules with the per-part brief.
            system_instructions = (
                f"{TUTOR_SYSTEM}\n\n---\n\nBRIEF:\n{system_instructions}"
            )

        user_prompt = build_tutor_user_prompt(
            profile=profile,
            module=module,
            part=part,
            part_id=part_id,
        )

        try:
            raw_lesson = await llm_client.generate_text(
                prompt=user_prompt,
                instructions=system_instructions,
                temperature=0.6,
                max_tokens=4096,
                metadata={
                    "agent": "TutorAgent",
                    "step": "teach",
                    "part_id": part_id,
                },
            )
        except LLMError as exc:
            log.error(
                "tutor_lesson_generation_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise TutorAgentError(
                "Failed to generate the lesson.",
                details={
                    "part_id": part_id,
                    "part_title": part.title,
                    "cause": str(exc),
                },
            ) from exc

        cleaned = self._clean_lesson(raw_lesson)
        self._validate_lesson(cleaned, part_id=part_id, log=log)

        meta_dict = build_lesson_metadata(
            profile=profile,
            module=module,
            part=part,
            part_id=part_id,
        )
        metadata = LessonMetadata(**meta_dict)

        lesson = Lesson(content=cleaned, metadata=metadata)

        log.info(
            "tutor_lesson_generation_completed",
            lesson_length=len(cleaned),
        )
        return lesson

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _clean_lesson(self, raw: str) -> str:
        text = raw.strip()

        if text.startswith("```markdown") and text.endswith("```"):
            text = text[len("```markdown"):].strip()
            text = text[:-len("```")].strip()
        elif text.startswith("```") and text.endswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            text = text[:-len("```")].strip()

        return text.strip()

    def _validate_lesson(
        self,
        text: str,
        *,
        part_id: str,
        log: structlog.stdlib.BoundLogger,
    ) -> None:
        if len(text) < _MIN_LESSON_LENGTH:
            log.error(
                "tutor_lesson_too_short",
                length=len(text),
                minimum=_MIN_LESSON_LENGTH,
            )
            raise TutorAgentError(
                "Generated lesson is too short.",
                details={
                    "part_id": part_id,
                    "length": len(text),
                    "minimum_expected": _MIN_LESSON_LENGTH,
                },
            )


# ============================================================
# Singleton
# ============================================================

tutor_agent = TutorAgent()


__all__ = ["TutorAgent", "tutor_agent"]

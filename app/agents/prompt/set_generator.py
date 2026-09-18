"""
Teaching Brief Set Generator (Phase 11).

Generates SHORT briefs (200-400 chars each) in batches.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import structlog

from app.core.exceptions import PromptAgentError
from app.core.llm_client import llm_client
from app.prompts.teaching_set import (
    TEACHING_SET_GENERATION_SYSTEM,
    build_teaching_set_prompt,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles
from app.schemas.teaching import (
    TeachingPromptItem,
    TeachingPromptSet,
)

logger = structlog.get_logger(__name__)


# Briefs are 200-400 chars. We accept anything from 100 upward.
_MIN_BRIEF_LENGTH = 80

# Max chars per brief (to catch runaway outputs).
_MAX_BRIEF_LENGTH = 1200

# 4 briefs per LLM call.
_BATCH_SIZE = 4

# Throttle between batches.
_BATCH_DELAY_S = 2.0

# Max retries per batch.
_BATCH_MAX_RETRIES = 3


ProgressCallback = Callable[[int, int], Awaitable[None]]


class TeachingPromptSetGenerator:
    """Stateless batch generator of teaching briefs."""

    async def generate(
        self,
        profile: UserProfile,
        roadmap: RoadmapTitles,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> TeachingPromptSet:
        log = logger.bind(
            agent="TeachingPromptSetGenerator",
            step="generate",
            topic=profile.topic,
            role=profile.role,
            level=profile.level.value,
            total_modules=roadmap.total_modules,
            total_parts=self._count_parts(roadmap),
        )
        log.info("brief_set_generation_started")

        all_positions = self._enumerate_positions(roadmap)
        total = len(all_positions)

        batches = [
            all_positions[i:i + _BATCH_SIZE]
            for i in range(0, total, _BATCH_SIZE)
        ]

        log.info(
            "brief_set_batches_planned",
            total_parts=total,
            batch_count=len(batches),
            batch_size=_BATCH_SIZE,
        )

        all_items: list[TeachingPromptItem] = []

        for idx, batch in enumerate(batches, start=1):
            log.info(
                "brief_set_batch_started",
                batch_index=idx,
                batch_total=len(batches),
                batch_size=len(batch),
            )

            items = await self._generate_batch(
                profile=profile,
                roadmap=roadmap,
                batch=batch,
                log=log,
            )
            all_items.extend(items)

            log.info(
                "brief_set_batch_completed",
                batch_index=idx,
                items_so_far=len(all_items),
            )

            if on_progress is not None:
                try:
                    await on_progress(len(all_items), total)
                except Exception as cb_err:
                    log.warning(
                        "progress_callback_failed", error=str(cb_err)
                    )

            if idx < len(batches):
                await asyncio.sleep(_BATCH_DELAY_S)

        log.info(
            "brief_set_generation_completed",
            prompt_count=len(all_items),
        )
        return TeachingPromptSet(prompts=all_items)

    # --------------------------------------------------------

    async def _generate_batch(
        self,
        *,
        profile: UserProfile,
        roadmap: RoadmapTitles,
        batch: list[tuple[str, str]],
        log: structlog.stdlib.BoundLogger,
    ) -> list[TeachingPromptItem]:
        """Generate one batch with retries."""
        last_error: Exception | None = None

        for attempt in range(1, _BATCH_MAX_RETRIES + 1):
            try:
                user_prompt = build_teaching_set_prompt(
                    profile=profile, roadmap=roadmap, batch=batch
                )

                result = await llm_client.generate_structured(
                    prompt=user_prompt,
                    schema=TeachingPromptSet,
                    instructions=TEACHING_SET_GENERATION_SYSTEM,
                    temperature=0.5,
                    max_tokens=1024,
                    metadata={
                        "agent": "TeachingPromptSetGenerator",
                        "step": "generate_batch",
                        "batch_size": len(batch),
                    },
                )
                return self._normalize_batch(result=result, batch=batch)

            except Exception as exc:
                last_error = exc
                log.warning(
                    "brief_set_batch_attempt_failed",
                    attempt=attempt,
                    max_attempts=_BATCH_MAX_RETRIES,
                    error_type=type(exc).__name__,
                    error_message=str(exc)[:200],
                )
                if attempt < _BATCH_MAX_RETRIES:
                    await asyncio.sleep(3.0 * attempt)

        raise PromptAgentError(
            f"Brief generation failed after {_BATCH_MAX_RETRIES} attempts.",
            details={
                "batch_size": len(batch),
                "cause": str(last_error)[:300] if last_error else "unknown",
            },
        )

    # --------------------------------------------------------

    def _normalize_batch(
        self,
        *,
        result: TeachingPromptSet,
        batch: list[tuple[str, str]],
    ) -> list[TeachingPromptItem]:
        expected = len(batch)
        received = result.prompts

        if len(received) != expected:
            raise PromptAgentError(
                f"LLM returned {len(received)} briefs for a batch of "
                f"{expected}.",
                details={"expected": expected, "received": len(received)},
            )

        items: list[TeachingPromptItem] = []
        for (part_id, title), item in zip(batch, received):
            text = item.prompt.strip()
            if len(text) < _MIN_BRIEF_LENGTH:
                raise PromptAgentError(
                    f"Brief for {part_id} is too short.",
                    details={"part_id": part_id, "length": len(text)},
                )
            if len(text) > _MAX_BRIEF_LENGTH:
                # Truncate gracefully instead of failing.
                text = text[:_MAX_BRIEF_LENGTH].rsplit(" ", 1)[0] + "…"

            items.append(
                TeachingPromptItem(
                    part_id=part_id, title=title, prompt=text
                )
            )
        return items

    # --------------------------------------------------------

    @staticmethod
    def _count_parts(roadmap: RoadmapTitles) -> int:
        return sum(len(m.parts) for m in roadmap.modules)

    @staticmethod
    def _enumerate_positions(
        roadmap: RoadmapTitles,
    ) -> list[tuple[str, str]]:
        positions: list[tuple[str, str]] = []
        for i, module in enumerate(roadmap.modules, start=1):
            for j, part in enumerate(module.parts, start=1):
                positions.append((f"M{i}-P{j}", part.title))
        return positions


teaching_set_generator = TeachingPromptSetGenerator()


__all__ = ["TeachingPromptSetGenerator", "teaching_set_generator"]

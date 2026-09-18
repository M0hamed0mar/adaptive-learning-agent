"""
Pydantic schemas for the Roadmap layer.

New design (Phase 11):
    - The roadmap is a *skeleton* of titles only.
    - No objectives, difficulty, requires_code, or teaching_plan
      at this stage. Those are decided later, by the prompt set
      generator, based on the titles + the user's profile.
    - This keeps the roadmap generation fast and lets us refine
      titles in a single, small refinement loop.

Structure:
    RoadmapTitles
    └── modules: list[ModuleTitle]
        └── parts: list[PartTitle]

Critic / refinement schemas are also here.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# ============================================================
# Shared configuration
# ============================================================

class _StrictBase(BaseModel):
    """Base model with strict-mode configuration."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


ShortText = Annotated[
    str,
    StringConstraints(min_length=2, strip_whitespace=True),
]

LongText = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]


# ============================================================
# Part / Module / Roadmap — titles only
# ============================================================

class PartTitle(_StrictBase):
    """
    A single part, identified only by its title.

    The part's `id` (e.g. 'M1-P1') is derived deterministically from
    the module and part positions, so it is not part of the LLM output.
    """

    title: ShortText = Field(
        description=(
            "A specific, action-oriented title for one lesson. "
            "Must be small enough to be taught in a single lesson."
        ),
    )


class ModuleTitle(_StrictBase):
    """A single module: a group of related parts."""

    title: ShortText = Field(
        description=(
            "A short, descriptive module title. "
            "e.g. 'Docker Fundamentals', 'Building Images'."
        ),
    )
    parts: list[PartTitle] = Field(
        min_length=2,
        max_length=8,
        description="Ordered list of parts in this module.",
    )


class RoadmapTitles(_StrictBase):
    """
    A roadmap as a skeleton of titles, ready for prompt generation.

    There is NO content at this stage — only the structural skeleton.
    """

    title: ShortText = Field(
        description="Roadmap title, e.g. 'Docker for AI Engineers'.",
    )
    summary: LongText = Field(
        description="One-paragraph summary of what the learner will achieve.",
    )
    total_modules: int = Field(
        ge=1,
        le=8,
        description="Must equal len(modules).",
    )
    estimated_hours: float = Field(
        ge=1.0,
        le=100.0,
        description="Rough total time estimate in hours.",
    )
    modules: list[ModuleTitle] = Field(
        min_length=1,
        max_length=8,
        description="Ordered list of modules.",
    )


# ============================================================
# Critic — Roadmap titles evaluation
# ============================================================

class RoadmapTitlesCritique(_StrictBase):
    """Result of evaluating a RoadmapTitles instance."""

    score: float = Field(
        ge=0.0,
        le=10.0,
        description="Overall quality score (0-10).",
    )
    is_acceptable: bool = Field(
        description="True when the roadmap is good enough to proceed.",
    )
    issues: list[str] = Field(
        description="Concrete problems found. Empty list if none.",
    )
    suggestions: list[str] = Field(
        description="Actionable suggestions. Empty list if none.",
    )
    reasoning: LongText = Field(
        description="Brief justification for the score.",
    )


__all__ = [
    "PartTitle",
    "ModuleTitle",
    "RoadmapTitles",
    "RoadmapTitlesCritique",
    "ShortText",
    "LongText",
]
"""
Pydantic schemas for the teaching-prompt batch layer.

New design (Phase 11):
    - Instead of generating one teaching prompt per part (which
      required 3-5 LLM calls per part), we generate ALL prompts in
      ONE batch call.
    - The output is a `TeachingPromptSet` — a simple list of
      `TeachingPromptItem` objects.
    - Then ONE batch critic + ONE batch refiner improve them all at
      once.

Structure:
    TeachingPromptSet
    └── prompts: list[TeachingPromptItem]

    TeachingPromptItem
        - part_id    (M1-P1, etc. — derived, not from LLM)
        - title      (from the roadmap)
        - prompt     (the teaching prompt itself)
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


PromptText = Annotated[
    str,
    StringConstraints(min_length=50, strip_whitespace=True),
]

ShortText = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]

LongText = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]


# ============================================================
# Teaching Prompt Item
# ============================================================

class TeachingPromptItem(_StrictBase):
    """
    A single teaching prompt, ready to be sent to the tutor.

    The `part_id` and `title` are provided by the caller (from the
    roadmap), NOT by the LLM. The LLM only fills in the `prompt`.
    """

    part_id: ShortText = Field(
        description="The part ID (e.g. 'M1-P1'). Provided by the caller.",
    )
    title: ShortText = Field(
        description="The part title. Provided by the caller.",
    )
    prompt: PromptText = Field(
        description=(
            "The complete teaching prompt for this part. "
            "Must be self-contained and ready to send to the tutor LLM."
        ),
    )


class TeachingPromptSet(_StrictBase):
    """A batch of teaching prompts for a whole roadmap."""

    prompts: list[TeachingPromptItem] = Field(
        min_length=1,
        description="One prompt per part, in roadmap order.",
    )


# ============================================================
# Critic — Batch Evaluation
# ============================================================

class TeachingPromptSetCritique(_StrictBase):
    """
    Result of evaluating a whole batch of teaching prompts.

    The critic returns ONE score for the batch, plus per-prompt
    issues (keyed by part_id) so the refiner can target them.
    """

    score: float = Field(
        ge=0.0,
        le=10.0,
        description="Overall quality score for the batch (0-10).",
    )
    is_acceptable: bool = Field(
        description="True when the batch is good enough to proceed.",
    )
    issues: list[str] = Field(
        description=(
            "Concrete problems found across the batch. "
            "Empty list if none."
        ),
    )
    suggestions: list[str] = Field(
        description=(
            "Actionable suggestions, applied to the whole batch. "
            "Empty list if none."
        ),
    )
    reasoning: LongText = Field(
        description="Brief justification for the score.",
    )


__all__ = [
    "TeachingPromptItem",
    "TeachingPromptSet",
    "TeachingPromptSetCritique",
    "PromptText",
]
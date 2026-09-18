"""
Pydantic schemas for the Profile layer.

New design (Phase 11):
    - The profile is much simpler: 4 fields + raw_input.
    - The `raw_input` is the user's free-text description of what
      they want to learn. The LLM uses it to infer subtle details.
    - `focus` was removed — it's inferred from raw_input when relevant.

Fields:
    - level           (enum)
    - goal            (enum)
    - role            (free text)
    - learning_style  (enum)
    - raw_input       (free text — the user's original description)
    - language        (ISO code, default 'ar')
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.config.constants import (
    LearningGoal,
    LearningStyle,
    UserLevel,
)


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
    StringConstraints(min_length=1, strip_whitespace=True),
]

LongText = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]


# ============================================================
# Analysis — deciding what's missing
# ============================================================

class ProfileAnalysis(_StrictBase):
    """
    Result of analyzing the raw user input.

    Kept minimal: we only need to know if the 4 required fields
    are already inferable from the raw input.
    """

    topic: ShortText = Field(
        description="Normalized topic name (e.g. 'Docker').",
    )
    needs_more_info: bool = Field(
        description="True if we still need to ask the user for fields.",
    )
    missing_fields: list[
        Literal["level", "goal", "role", "learning_style"]
    ] = Field(
        description=(
            "Fields to collect. Empty list if nothing is missing."
        ),
    )
    reasoning: LongText = Field(
        description="Brief justification for the analysis.",
    )


# ============================================================
# Final Profile
# ============================================================

class UserProfile(_StrictBase):
    """
    The finalized learning profile for a study session.

    Only 4 fields + the raw input. Everything else (focus, subtle
    preferences, etc.) is inferred from `raw_input` by the LLM when
    needed.
    """

    topic: ShortText = Field(
        description="Topic the user wants to learn.",
    )
    level: UserLevel = Field(
        description="User's self-reported proficiency level.",
    )
    goal: LearningGoal = Field(
        description="User's primary learning objective.",
    )
    role: ShortText = Field(
        description="Professional context (e.g. 'AI Engineer').",
    )
    learning_style: LearningStyle = Field(
        description="Preferred style of explanations.",
    )
    raw_input: str = Field(
        description=(
            "The user's original free-text description. "
            "Used as context for generating titles and prompts."
        ),
    )
    language: str = Field(
        min_length=2,
        max_length=5,
        description="Output language for lessons (e.g. 'ar', 'en').",
    )


# ============================================================
# Critic
# ============================================================

class ProfileCritique(_StrictBase):
    """Result of evaluating a UserProfile."""

    score: float = Field(
        ge=0.0,
        le=10.0,
        description="Overall quality score (0-10).",
    )
    is_acceptable: bool = Field(
        description="True when the profile is good enough to proceed.",
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
    "ProfileAnalysis",
    "UserProfile",
    "ProfileCritique",
]
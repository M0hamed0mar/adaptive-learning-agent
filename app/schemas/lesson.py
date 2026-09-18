"""
Pydantic schemas for the Tutor Agent (Phase 12).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class _StrictBase(BaseModel):
    """Base model with strict-mode configuration."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


MarkdownText = Annotated[
    str,
    StringConstraints(min_length=100, strip_whitespace=True),
]

ShortText = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]


class LessonMetadata(_StrictBase):
    """Descriptive metadata about a generated lesson."""

    part_id: ShortText = Field(description="Part identifier.")
    module_title: ShortText = Field(description="Title of the parent module.")
    part_title: ShortText = Field(description="Title of the part.")
    topic: ShortText = Field(description="The user's topic.")
    role: ShortText = Field(description="The user's professional role.")
    level: ShortText = Field(description="The user's level.")
    difficulty: int | None = Field(
        default=None,
        description="Optional difficulty (1-5). Null if unknown.",
    )
    language: ShortText = Field(description="ISO 639-1 language code.")


class Lesson(_StrictBase):
    """A generated lesson for a single RoadmapPart."""

    content: MarkdownText = Field(
        description="The Markdown-formatted lesson content.",
    )
    metadata: LessonMetadata = Field(
        description="The context used to generate this lesson.",
    )


__all__ = [
    "Lesson",
    "LessonMetadata",
    "MarkdownText",
]

"""
Lesson ORM model (Phase 11 redesign).

Lessons are now generated LAZILY — when the user opens a part.
The `content` column is nullable to support parts whose lesson has
not been generated yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.roadmap import RoadmapPart


class Lesson(Base, TimestampMixin):
    """A generated lesson for one roadmap part."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    roadmap_part_id: Mapped[int] = mapped_column(
        ForeignKey("roadmap_parts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # The lesson content, in Markdown. Nullable until generated.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Descriptive metadata (part_id, module_title, topic, level, ...).
    # Stored as a JSON dict to avoid schema churn for metadata fields.
    lesson_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    # Relationship
    part: Mapped["RoadmapPart"] = relationship(back_populates="lesson")

    def __repr__(self) -> str:
        has_content = bool(self.content)
        return (
            f"<Lesson id={self.id} roadmap_part_id={self.roadmap_part_id} "
            f"content={'yes' if has_content else 'none'}>"
        )


__all__ = ["Lesson"]

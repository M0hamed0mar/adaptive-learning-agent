"""
LearningProfile ORM model (Phase 11 redesign).

Removed:
    - `focus` (now inferred from raw_input when needed).

Kept:
    - `raw_input` (the user's free-text description).
    - All 4 enum fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.session import StudySession


class LearningProfile(Base, TimestampMixin):
    """The user's learning profile for one study session."""

    __tablename__ = "learning_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Required fields
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    goal: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    learning_style: Mapped[str] = mapped_column(String(50), nullable=False)

    # The user's free-text description of what they want to learn.
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)

    # Output language (ISO 639-1).
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="ar"
    )

    # Relationship
    session: Mapped["StudySession"] = relationship(back_populates="profile")

    def __repr__(self) -> str:
        return (
            f"<LearningProfile session_id={self.session_id} "
            f"topic={self.topic!r} level={self.level!r}>"
        )


__all__ = ["LearningProfile"]

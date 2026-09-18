"""
Progress ORM model.

Tracks the learner's current position and completion state within
a study session's roadmap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.session import StudySession


class Progress(Base, TimestampMixin):
    """
    Progress state for one study session.
    """

    __tablename__ = "progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one progress per session
        index=True,
    )

    current_module_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    current_part_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # List of part IDs (semantic, e.g. "M1-P1") that are completed
    completed_parts: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )

    total_parts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    percentage: Mapped[float] = mapped_column(
        Numeric(precision=5, scale=2), nullable=False, default=0.0
    )

    # Relationship
    session: Mapped["StudySession"] = relationship(back_populates="progress")

    def __repr__(self) -> str:
        return (
            f"<Progress session_id={self.session_id} "
            f"{self.percentage}% ({len(self.completed_parts)}/{self.total_parts})>"
        )


__all__ = ["Progress"]
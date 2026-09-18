"""
StudySession ORM model.

A StudySession represents one learning journey for one topic.
Phase 12 additions:
    - `pipeline_stage`: current stage of the generation pipeline
      (e.g. "profile", "roadmap", "prompts", "done").
    - `pipeline_progress`: 0-100 progress percentage.
    - `pipeline_message`: human-readable status message for the UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import SessionStatus
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.profile import LearningProfile
    from app.models.progress import Progress
    from app.models.roadmap import Roadmap
    from app.models.user import User


class StudySession(Base, TimestampMixin):
    """A single learning journey for one topic."""

    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default=SessionStatus.DRAFT.value,
        nullable=False,
        index=True,
    )

    # --- Pipeline progress tracking (Phase 12) ---------------------
    pipeline_stage: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    pipeline_progress: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    pipeline_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")

    profile: Mapped["LearningProfile | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    roadmap: Mapped["Roadmap | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    progress: Mapped["Progress | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<StudySession id={self.id} topic={self.topic!r} "
            f"status={self.status!r}>"
        )


__all__ = ["StudySession"]

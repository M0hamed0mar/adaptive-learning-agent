"""
Message ORM model.

Stores user↔assistant interactions related to a study session.
Used for:
    - persisting the chat history,
    - the "ask about this part" feature,
    - audit and debugging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.session import StudySession


class Message(Base, TimestampMixin):
    """
    A single message in a study session.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "user" or "assistant"
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional: which part this message relates to
    roadmap_part_id: Mapped[int | None] = mapped_column(
        ForeignKey("roadmap_parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationship
    session: Mapped["StudySession"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        preview = self.content[:40].replace("\n", " ")
        return f"<Message role={self.role!r} preview={preview!r}>"


__all__ = ["Message"]
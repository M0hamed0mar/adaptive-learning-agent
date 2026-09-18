"""
User ORM model.

For now, users are implicit: the MVP does not require authentication.
This model exists so that:
    - Sessions can be linked to a user.
    - Multi-user support can be added later without a schema change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.session import StudySession


class User(Base, TimestampMixin):
    """
    A user of the platform.

    In the MVP, a single default user is created on first use. The
    `external_id` field is a placeholder for a future auth provider ID.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(
        String(200),
        unique=True,
        nullable=True,
        index=True,
    )

    # Relationship: one user → many sessions
    sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} external_id={self.external_id!r}>"


__all__ = ["User"]
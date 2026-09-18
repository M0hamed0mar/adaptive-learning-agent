"""
SQLAlchemy declarative base and shared mixins.

All ORM models in this project inherit from `Base` and, when applicable,
from `TimestampMixin`.

Design notes:
    - SQLAlchemy 2.0 style: `Mapped[...]` annotations + `mapped_column`.
    - `Base.metadata` is the single source of truth for Alembic.
    - Timestamps are stored as UTC, timezone-aware.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ============================================================
# Declarative base
# ============================================================

class Base(DeclarativeBase):
    """
    Project-wide declarative base.

    Every ORM model must inherit from this class so that Alembic
    can discover the full metadata.
    """

    def to_dict(self) -> dict[str, Any]:
        """
        Return a plain-dict representation of the model.

        Useful for logging and quick serialization. Not a replacement
        for Pydantic schemas.
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


# ============================================================
# Mixins
# ============================================================

def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    """
    Adds `created_at` and `updated_at` columns.

    `created_at` is set on insert; `updated_at` is set on every insert
    and update.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


__all__ = ["Base", "TimestampMixin", "utcnow"]
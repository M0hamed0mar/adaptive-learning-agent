"""
Base service helpers.

Provides shared utilities for service classes:
    - A common base class with a repr.
    - Async CRUD helpers that operate on a session passed in by the caller.

Design notes:
    - Services do NOT open their own sessions. The caller controls the
      transaction boundary (via `get_session()` or a FastAPI dependency).
    - Services use `flush()` (not `commit()`) so the caller can batch
      multiple operations in one transaction.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

T = TypeVar("T", bound=Base)


# ============================================================
# Base Service
# ============================================================

class BaseService(Generic[T]):
    """
    Minimal generic service base.

    Subclasses set `model` to the ORM class they manage and get basic
    `get`, `list`, and `delete` helpers for free.
    """

    model: type[T]

    # --------------------------------------------------------
    # Basic CRUD
    # --------------------------------------------------------

    async def get(
        self,
        db: AsyncSession,
        obj_id: int,
    ) -> T | None:
        """Return the object with the given primary key, or None."""
        return await db.get(self.model, obj_id)

    async def list_all(
        self,
        db: AsyncSession,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]:
        """Return all rows (optionally paginated)."""
        stmt = select(self.model)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete(
        self,
        db: AsyncSession,
        obj: T,
    ) -> None:
        """Delete the given object."""
        await db.delete(obj)

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    async def _flush_and_refresh(
        self,
        db: AsyncSession,
        obj: T,
    ) -> T:
        """Flush pending changes and refresh the object from the DB."""
        await db.flush()
        await db.refresh(obj)
        return obj

    def __repr__(self) -> str:
        return f"<{type(self).__name__} model={self.model.__name__}>"


__all__ = ["BaseService"]
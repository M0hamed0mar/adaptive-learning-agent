"""
Async session management for FastAPI dependency injection.

Provides:
    - `get_session()`: an async context manager for use outside FastAPI.
    - `get_db_session()`: a FastAPI dependency.

Both yield an `AsyncSession` and ensure it is closed afterwards.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_sessionmaker


# ============================================================
# Context manager (for scripts, tests, etc.)
# ============================================================

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession as a context manager.

    The session is committed on success and rolled back on exception.

    Usage:
        async with get_session() as session:
            session.add(obj)
            await session.flush()
    """
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ============================================================
# FastAPI dependency (used in Phase 7)
# ============================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.

    Usage:
        @router.get("/items")
        async def list_items(
            session: AsyncSession = Depends(get_db_session),
        ):
            ...
    """
    SessionLocal = get_sessionmaker()
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


__all__ = [
    "get_session",
    "get_db_session",
]
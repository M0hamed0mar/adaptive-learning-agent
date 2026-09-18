"""
FastAPI dependency injection helpers.

Exposes:
    - `get_db()`: yields an AsyncSession per request.
    - `get_settings()`: returns the application settings.
    - `SessionDep`, `SettingsDep`: typed aliases for use in routes.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings as _get_settings
from app.database.session import get_db_session


# ============================================================
# Database
# ============================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: yields an AsyncSession.

    Delegates to `get_db_session`, which handles commit/rollback.
    """
    async for session in get_db_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]


# ============================================================
# Settings
# ============================================================

def get_settings() -> Settings:
    """Return the application settings (cached)."""
    return _get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]


__all__ = [
    "get_db",
    "get_settings",
    "SessionDep",
    "SettingsDep",
]
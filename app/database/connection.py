"""
Database connection and session factory.

Creates an async SQLAlchemy engine and a sessionmaker bound to it.

For SQLite, we enable WAL mode to allow concurrent readers + one writer.
This avoids the "database is locked" error when the API polls while the
background task is writing.

Usage:
    from app.database.connection import get_engine, get_sessionmaker

    engine = get_engine()
    SessionLocal = get_sessionmaker()

    async with SessionLocal() as session:
        ...
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings


# ============================================================
# SQLite PRAGMA setup
# ============================================================

def _register_sqlite_pragmas(engine: AsyncEngine) -> None:
    """
    Register PRAGMA statements for SQLite connections.

    Enables:
        - WAL journal mode (concurrent readers + one writer).
        - Foreign key enforcement.
        - A generous busy timeout.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        # `dbapi_connection` here is an aiosqlite connection wrapper.
        # We need to access the underlying sqlite3 connection to run
        # PRAGMA statements. aiosqlite exposes `_conn`.
        raw = getattr(dbapi_connection, "_conn", None)
        cursor_target = raw if raw is not None else dbapi_connection

        try:
            cursor = cursor_target.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
            cursor.close()
        except Exception:
            # If the underlying driver does not support this, ignore.
            pass


# ============================================================
# Engine
# ============================================================

@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """
    Return the async SQLAlchemy engine (cached).

    The engine is created once per process. It manages a connection
    pool internally.

    For SQLite, we set a busy timeout and enable WAL mode to avoid
    "database is locked" errors under concurrent access.
    """
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")

    connect_args: dict = {}
    if is_sqlite:
        connect_args["timeout"] = 30  # seconds

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.is_development,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    if is_sqlite:
        _register_sqlite_pragmas(engine)

    return engine


# ============================================================
# Session factory
# ============================================================

@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """
    Return the async session factory (cached).

    The factory is bound to the engine returned by `get_engine()`.
    """
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# ============================================================
# Lifecycle helpers
# ============================================================

async def dispose_engine() -> None:
    """
    Dispose of the engine and its connection pool.

    Call this on application shutdown to release all DB resources.
    """
    engine = get_engine()
    await engine.dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


__all__ = [
    "get_engine",
    "get_sessionmaker",
    "dispose_engine",
]
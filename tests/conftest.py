"""
Pytest fixtures for the Adaptive Learning Agent test suite.

Provides:
    - `event_loop`             : asyncio event loop policy for the session.
    - `db_engine`              : fresh SQLite DB (temp file) per test.
    - `db_session`             : AsyncSession bound to the test engine.
    - `db_session_factory`     : sessionmaker bound to the test engine.
    - `app`                    : FastAPI app with test settings.
    - `client`                 : httpx AsyncClient speaking to the app.

Design notes:
    - Each test gets a FRESH SQLite DATABASE FILE, created in a temp
      directory and cleaned up afterwards. This keeps tests isolated
      and works reliably with async SQLAlchemy on Windows + Python 3.14.
    - We use a temp FILE (not `:memory:`) because `StaticPool` does not
      reliably share an in-memory database across async connections in
      this environment. A temp file gives us the same isolation with
      predictable behavior.
    - We do NOT call the LLM in unit tests. Integration tests that
      need the LLM should mark themselves with `@pytest.mark.llm`.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database.base import Base
from app.models import *  # noqa: F401, F403  — register all models


# ============================================================
# Event loop
# ============================================================

@pytest.fixture(scope="session")
def event_loop():
    """Session-wide asyncio event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Database
# ============================================================

@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Provide a fresh SQLite database (temp file) with all tables created.

    The database file is created in a per-test temp directory and
    removed after the test finishes.
    """
    # Create a unique temp directory per test.
    tmpdir = tempfile.mkdtemp(prefix="ala_test_")
    db_path = Path(tmpdir) / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    engine = create_async_engine(db_url, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()

    # Clean up the temp dir.
    try:
        db_path.unlink(missing_ok=True)
        Path(tmpdir).rmdir()
    except OSError:
        pass


@pytest_asyncio.fixture
async def db_session(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an AsyncSession bound to the test engine.

    Data does NOT leak between tests because each test gets a fresh
    `db_engine` (and thus a fresh database file).
    """
    SessionLocal = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture
async def db_session_factory(db_engine: AsyncEngine):
    """
    Provide an `async_sessionmaker` bound to the test engine.

    Use this in API tests where you need to create data in one
    session and read it from another (e.g. via the HTTP client).
    """
    return async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# ============================================================
# FastAPI app & client
# ============================================================

@pytest_asyncio.fixture
async def app():
    """
    Provide a FastAPI app instance.

    Note: the app uses the production DB URL by default. Tests that
    need an isolated DB should override the `get_db_session`
    dependency locally.
    """
    from app.main import create_app

    return create_app()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an httpx AsyncClient that talks to the app via ASGITransport.

    Note: background tasks launched via `asyncio.create_task` may not
    progress between requests under ASGITransport. For end-to-end
    tests of the pipeline, use the `scripts/demo_api.py` script
    instead (it runs a real uvicorn server).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# Markers
# ============================================================

def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "llm: tests that call the real LLM (excluded from default runs)",
    )
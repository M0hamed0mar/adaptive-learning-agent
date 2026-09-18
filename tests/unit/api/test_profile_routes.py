"""
Unit tests for the profile routes.

Focus:
    - `GET /sessions/{id}/profile` returns the persisted profile.
    - 404 when the session does not exist.
    - 404 when the profile has not been submitted yet.

Uses a temp-file SQLite DB (via `db_session_factory`) with the
`get_db` dependency (from `app.api.dependencies`) overridden to
point to it.

IMPORTANT: We override `get_db` (not `get_db_session`), because the
routes depend on `get_db` via the `SessionDep` alias. Overriding
`get_db_session` would have no effect.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_db
from app.main import create_app
from app.schemas.profile import UserProfile
from app.services import profile_service, session_service, user_service


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def client(db_session_factory):
    """
    httpx client with the app's `get_db` dependency overridden to
    use the test sessionmaker.
    """
    app = create_app()

    async def _override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ============================================================
# Helpers
# ============================================================

async def _create_session(sessionmaker, topic: str = "Test") -> int:
    async with sessionmaker() as db:
        user = await user_service.get_or_create_default(db)
        session = await session_service.create(db, user_id=user.id, topic=topic)
        await db.commit()
        return session.id


async def _create_profile(
    sessionmaker, session_id: int, topic: str = "Test"
) -> None:
    async with sessionmaker() as db:
        profile = UserProfile(
            topic=topic,
            level="beginner",
            goal="understand_fundamentals",
            role="Engineer",
            learning_style="balanced",
            focus=None,
            raw_input=f"{topic} for engineers",
            language="en",
        )
        await profile_service.create_from_pydantic(
            db, session_id=session_id, profile=profile
        )
        await db.commit()


# ============================================================
# Tests
# ============================================================

@pytest.mark.asyncio
async def test_get_profile_returns_persisted_profile(
    client, db_session_factory
):
    """`GET /sessions/{id}/profile` returns the profile data."""
    session_id = await _create_session(db_session_factory, topic="Docker")
    await _create_profile(db_session_factory, session_id, topic="Docker")

    r = await client.get(f"/api/v1/sessions/{session_id}/profile")
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["session_id"] == session_id
    assert body["topic"] == "Docker"
    assert body["level"] == "beginner"
    assert body["goal"] == "understand_fundamentals"
    assert body["role"] == "Engineer"
    assert body["learning_style"] == "balanced"
    assert body["focus"] is None
    assert body["language"] == "en"


@pytest.mark.asyncio
async def test_get_profile_404_for_unknown_session(client):
    """Unknown session → 404."""
    r = await client.get("/api/v1/sessions/9999/profile")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "http_error"
    assert "9999" in body["error"]["message"]


@pytest.mark.asyncio
async def test_get_profile_404_when_not_submitted(client, db_session_factory):
    """Session exists but profile not submitted → 404."""
    session_id = await _create_session(db_session_factory, topic="Docker")

    r = await client.get(f"/api/v1/sessions/{session_id}/profile")
    assert r.status_code == 404
    body = r.json()
    assert "not been submitted" in body["error"]["message"]
"""
Unit tests for the roadmap routes.

Focus:
    - `GET /sessions/{id}/roadmap` returns the full roadmap tree.
    - 404 when the session does not exist.
    - 404 when the roadmap has not been generated yet.

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
from app.schemas.roadmap import (
    Roadmap as PydanticRoadmap,
    RoadmapModule as PydanticRoadmapModule,
    RoadmapPart as PydanticRoadmapPart,
    TeachingPlan,
)
from app.services import roadmap_service, session_service, user_service


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def client(db_session_factory):
    """httpx client with `get_db` overridden to the test DB."""
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

def _make_part(part_id: str, title: str) -> PydanticRoadmapPart:
    return PydanticRoadmapPart(
        id=part_id,
        title=title,
        objective=f"Understand {title}.",
        difficulty=2,
        requires_code=False,
        teaching_plan=TeachingPlan(
            explanation=True,
            analogy=False,
            examples=True,
            code=False,
            practical_example=False,
            common_mistakes=False,
            best_practices=False,
            recap=True,
        ),
    )


def _make_roadmap() -> PydanticRoadmap:
    return PydanticRoadmap(
        title="Docker for Engineers",
        summary="A test roadmap.",
        total_modules=1,
        estimated_hours=2.0,
        prerequisites=["Linux basics"],
        learning_outcomes=["Write a Dockerfile."],
        modules=[
            PydanticRoadmapModule(
                id="M1",
                title="Foundations",
                description="The basics.",
                parts=[
                    _make_part("M1-P1", "Intro"),
                    _make_part("M1-P2", "Details"),
                ],
            ),
        ],
    )


async def _create_session(sessionmaker, topic: str = "Test") -> int:
    async with sessionmaker() as db:
        user = await user_service.get_or_create_default(db)
        session = await session_service.create(db, user_id=user.id, topic=topic)
        await db.commit()
        return session.id


async def _create_roadmap(sessionmaker, session_id: int) -> None:
    async with sessionmaker() as db:
        await roadmap_service.create_from_pydantic(
            db, session_id=session_id, roadmap=_make_roadmap()
        )
        await db.commit()


# ============================================================
# Tests
# ============================================================

@pytest.mark.asyncio
async def test_get_roadmap_returns_full_tree(client, db_session_factory):
    """`GET /sessions/{id}/roadmap` returns the full roadmap."""
    session_id = await _create_session(db_session_factory, topic="Docker")
    await _create_roadmap(db_session_factory, session_id)

    r = await client.get(f"/api/v1/sessions/{session_id}/roadmap")
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["session_id"] == session_id
    assert body["title"] == "Docker for Engineers"
    assert body["total_modules"] == 1
    assert body["prerequisites"] == ["Linux basics"]
    assert len(body["modules"]) == 1

    module = body["modules"][0]
    assert module["id"] == "M1"
    assert module["title"] == "Foundations"
    assert len(module["parts"]) == 2

    part = module["parts"][0]
    assert part["id"] == "M1-P1"
    assert part["title"] == "Intro"
    assert part["difficulty"] == 2
    assert part["requires_code"] is False
    assert part["teaching_plan"]["explanation"] is True
    assert part["teaching_plan"]["code"] is False


@pytest.mark.asyncio
async def test_get_roadmap_404_for_unknown_session(client):
    """Unknown session → 404."""
    r = await client.get("/api/v1/sessions/9999/roadmap")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "http_error"
    assert "9999" in body["error"]["message"]


@pytest.mark.asyncio
async def test_get_roadmap_404_when_not_generated(client, db_session_factory):
    """Session exists but roadmap not generated → 404."""
    session_id = await _create_session(db_session_factory, topic="Docker")

    r = await client.get(f"/api/v1/sessions/{session_id}/roadmap")
    assert r.status_code == 404
    body = r.json()
    assert "not been generated" in body["error"]["message"]
"""
Sessions routes (Phase 11 redesign).

`POST /sessions` now takes a single `raw_input` (free-text description).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import SessionDep
from app.config.constants import SessionStatus
from app.schemas.session_api import (
    SessionCreateRequest,
    SessionCreated,
    SessionDetail,
    SessionSummary,
)
from app.services import (
    profile_service,
    progress_service,
    roadmap_service,
    session_service,
    user_service,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
log = structlog.get_logger(__name__)


@router.post(
    "",
    response_model=SessionCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new study session",
)
async def create_session(
    payload: SessionCreateRequest,
    db: SessionDep,
) -> SessionCreated:
    """
    Create a new study session from a free-text description.

    The `raw_input` is stored as the session title, and the session
    topic is set to a short placeholder that the profile agent will
    fill in later. The actual topic is inferred by the LLM.
    """
    user = await user_service.get_or_create_default(db)

    # Use the first ~80 chars as a "topic" placeholder — the profile
    # agent replaces it with the real inferred topic later.
    placeholder_topic = payload.raw_input.strip()[:80] or "New session"

    session = await session_service.create(
        db,
        user_id=user.id,
        topic=placeholder_topic,
        title=payload.raw_input.strip(),
        status=SessionStatus.DRAFT,
    )

    log.info(
        "api_session_created",
        session_id=session.id,
        raw_input_len=len(payload.raw_input),
    )
    return SessionCreated(
        id=session.id,
        topic=session.topic,
        status=session.status,
        created_at=session.created_at,
    )


@router.get(
    "",
    response_model=list[SessionSummary],
    summary="List study sessions",
)
async def list_sessions(
    db: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SessionSummary]:
    user = await user_service.get_or_create_default(db)
    sessions = await session_service.list_for_user(
        db, user_id=user.id, limit=limit, offset=offset
    )
    return [
        SessionSummary(
            id=s.id,
            user_id=s.user_id,
            topic=s.topic,
            title=s.title,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get(
    "/{session_id}",
    response_model=SessionDetail,
    summary="Get a session by id",
)
async def get_session(
    session_id: int,
    db: SessionDep,
) -> SessionDetail:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = await profile_service.get_by_session(db, session_id)
    roadmap = await roadmap_service.get_by_session(db, session_id)
    progress = await progress_service.get_by_session(db, session_id)

    total_modules: int | None = None
    total_parts: int | None = None
    if roadmap is not None:
        total_modules = roadmap.total_modules
        _, parts_per_module = await progress_service.get_roadmap_shape(
            db, session_id
        )
        total_parts = sum(parts_per_module)

    return SessionDetail(
        id=session.id,
        user_id=session.user_id,
        topic=session.topic,
        title=session.title,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        has_profile=profile is not None,
        has_roadmap=roadmap is not None,
        total_modules=total_modules,
        total_parts=total_parts,
        progress_percentage=float(progress.percentage) if progress else None,
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
)
async def delete_session(session_id: int, db: SessionDep) -> None:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await session_service.delete(db, session)
    log.info("api_session_deleted", session_id=session_id)


__all__ = ["router"]

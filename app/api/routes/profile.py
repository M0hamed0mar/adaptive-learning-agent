"""
Profile routes (Phase 11 redesign).

Endpoints:
    - POST /sessions/{id}/profile    submit profile answers (triggers pipeline)
    - GET  /sessions/{id}/profile    read the current profile
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import SessionDep
from app.config.constants import SessionStatus
from app.database import get_session as get_db_session
from app.graph import get_learning_graph
from app.schemas.session_api import (
    ProfileResponse,
    SessionProfileAccepted,
    SessionProfileRequest,
)
from app.services import profile_service, session_service

router = APIRouter(prefix="/sessions", tags=["profile"])
log = structlog.get_logger(__name__)


# ============================================================
# Background task registry
# ============================================================

_running_tasks: set[asyncio.Task] = set()


def _spawn_background_task(coro) -> None:
    """Schedule a coroutine in the background with a strong reference."""
    task = asyncio.create_task(coro)
    _running_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _running_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            log.error(
                "background_task_unhandled_exception",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    task.add_done_callback(_on_done)


# ============================================================
# Background runner
# ============================================================

async def _run_graph_for_session(
    session_id: int,
    raw_input: str,
    profile_answers: dict,
) -> None:
    """Background task: run the learning graph and update status."""
    log_ctx = structlog.get_logger(__name__).bind(
        background_task="run_graph", session_id=session_id
    )
    log_ctx.info("background_graph_started")

    try:
        graph = get_learning_graph()
        initial_state = {
            "session_id": session_id,
            "raw_input": raw_input,
            "profile_answers": profile_answers,
        }
        final_state = await graph.ainvoke(initial_state)

        final_status = final_state.get("status", SessionStatus.READY.value)
        log_ctx.info(
            "background_graph_completed", final_status=final_status
        )

        async with get_db_session() as db:
            session = await session_service.get(db, session_id)
            if session is not None:
                await session_service.update_status(
                    db, session, SessionStatus.READY
                )

    except Exception as exc:
        log_ctx.error(
            "background_graph_failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        try:
            async with get_db_session() as db:
                session = await session_service.get(db, session_id)
                if session is not None:
                    await session_service.update_status(
                        db, session, SessionStatus.FAILED
                    )
        except Exception as inner:
            log_ctx.error(
                "background_status_update_failed", error=str(inner)
            )


# ============================================================
# POST — Submit profile answers
# ============================================================

@router.post(
    "/{session_id}/profile",
    response_model=SessionProfileAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit profile answers and start the pipeline",
)
async def submit_profile(
    session_id: int,
    payload: SessionProfileRequest,
    db: SessionDep,
) -> SessionProfileAccepted:
    """Submit the 4 answers. Starts the pipeline in the background."""
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in (
        SessionStatus.DRAFT.value,
        SessionStatus.FAILED.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session {session_id} is in status {session.status!r} "
                f"and cannot accept a new profile submission."
            ),
        )

    await session_service.update_status(db, session, SessionStatus.PLANNING)

    answers = {
        "level": payload.level.value,
        "goal": payload.goal.value,
        "role": payload.role,
        "learning_style": payload.learning_style.value,
    }

    # raw_input comes from the session's title (set by create_session).
    raw_input = session.title or session.topic

    _spawn_background_task(
        _run_graph_for_session(
            session_id=session.id,
            raw_input=raw_input,
            profile_answers=answers,
        )
    )

    log.info(
        "api_profile_submitted",
        session_id=session.id,
        status=SessionStatus.PLANNING.value,
    )
    return SessionProfileAccepted(
        id=session.id,
        status=SessionStatus.PLANNING.value,
        message=(
            "Profile received. The learning pipeline is running in the "
            "background. Poll GET /sessions/{id} for status."
        ),
    )


# ============================================================
# GET — Read the current profile
# ============================================================

@router.get(
    "/{session_id}/profile",
    response_model=ProfileResponse,
    summary="Get the current profile for a session",
)
async def get_profile(
    session_id: int,
    db: SessionDep,
) -> ProfileResponse:
    """Return the persisted profile. 404 if not submitted yet."""
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = await profile_service.get_by_session_as_pydantic(
        db, session_id
    )
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Profile for session {session_id} has not been submitted yet.",
        )

    return ProfileResponse(
        session_id=session_id,
        topic=profile.topic,
        level=profile.level.value,
        goal=profile.goal.value,
        role=profile.role,
        learning_style=profile.learning_style.value,
        raw_input=profile.raw_input,
        language=profile.language,
    )


__all__ = ["router"]

"""
Progress routes.

Endpoints:
    - GET  /sessions/{id}/progress              get current progress
    - POST /sessions/{id}/progress/complete     mark a part completed
    - POST /sessions/{id}/progress/advance      advance to the next part
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

import structlog

from app.api.dependencies import SessionDep
from app.schemas.session_api import (
    MarkPartCompletedRequest,
    ProgressResponse,
)
from app.services import progress_service, session_service

router = APIRouter(prefix="/sessions", tags=["progress"])
log = structlog.get_logger(__name__)


# ============================================================
# Helpers
# ============================================================

def _to_response(session_id: int, progress) -> ProgressResponse:
    """Convert an ORM Progress to a ProgressResponse."""
    return ProgressResponse(
        session_id=session_id,
        current_module_index=progress.current_module_index,
        current_part_index=progress.current_part_index,
        completed_parts=list(progress.completed_parts or []),
        total_parts=progress.total_parts,
        percentage=float(progress.percentage),
    )


async def _get_progress_or_404(db, session_id: int):
    """Fetch progress for a session, raising 404 if missing."""
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    progress = await progress_service.get_by_session(db, session_id)
    if progress is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Progress for session {session_id} not initialized. "
                "Wait for the pipeline to complete."
            ),
        )
    return progress


# ============================================================
# Get progress
# ============================================================

@router.get(
    "/{session_id}/progress",
    response_model=ProgressResponse,
    summary="Get the current progress for a session",
)
async def get_progress(
    session_id: int,
    db: SessionDep,
) -> ProgressResponse:
    """
    Return the current progress state for the session.

    Returns 404 if the session has no progress yet (e.g. the pipeline
    has not created it).
    """
    progress = await _get_progress_or_404(db, session_id)
    return _to_response(session_id, progress)


# ============================================================
# Mark a part completed
# ============================================================

@router.post(
    "/{session_id}/progress/complete",
    response_model=ProgressResponse,
    summary="Mark a part as completed",
)
async def mark_part_completed(
    session_id: int,
    payload: MarkPartCompletedRequest,
    db: SessionDep,
) -> ProgressResponse:
    """
    Mark a part as completed.

    Idempotent: re-marking the same part is a no-op.
    """
    progress = await _get_progress_or_404(db, session_id)

    progress = await progress_service.mark_part_completed(
        db, progress, part_id=payload.part_id
    )

    log.info(
        "api_part_marked_completed",
        session_id=session_id,
        part_id=payload.part_id,
        percentage=float(progress.percentage),
    )

    return _to_response(session_id, progress)


# ============================================================
# Advance to next part
# ============================================================

@router.post(
    "/{session_id}/progress/advance",
    response_model=ProgressResponse,
    summary="Advance to the next part",
)
async def advance_progress(
    session_id: int,
    db: SessionDep,
) -> ProgressResponse:
    """
    Advance the current position pointer to the next part.

    The graph/roadmap shape is read from the DB to determine the next
    position.
    """
    progress = await _get_progress_or_404(db, session_id)

    # Fetch the roadmap shape.
    total_modules, parts_per_module = await progress_service.get_roadmap_shape(
        db, session_id
    )

    if total_modules == 0 or not parts_per_module:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot advance: the session has no roadmap parts.",
        )

    progress = await progress_service.advance_to_next_part(
        db,
        progress,
        total_modules=total_modules,
        parts_per_module=parts_per_module,
    )

    log.info(
        "api_progress_advanced",
        session_id=session_id,
        module=progress.current_module_index,
        part=progress.current_part_index,
    )

    return _to_response(session_id, progress)


__all__ = ["router"]
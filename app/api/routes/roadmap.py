"""
Roadmap routes (Phase 11 redesign).

Returns the roadmap TITLES only.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import SessionDep
from app.schemas.session_api import (
    RoadmapModuleResponse,
    RoadmapPartResponse,
    RoadmapResponse,
)
from app.services import roadmap_service, session_service

router = APIRouter(prefix="/sessions", tags=["roadmap"])
log = structlog.get_logger(__name__)


@router.get(
    "/{session_id}/roadmap",
    response_model=RoadmapResponse,
    summary="Get the roadmap for a session (titles only)",
)
async def get_roadmap(
    session_id: int,
    db: SessionDep,
) -> RoadmapResponse:
    """Return the roadmap titles for a session."""
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    orm = await roadmap_service.get_with_tree(db, session_id)
    if orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Roadmap for session {session_id} has not been "
                f"generated yet."
            ),
        )

    log.info(
        "api_roadmap_fetched",
        session_id=session_id,
        total_modules=orm.total_modules,
    )

    modules_response: list[RoadmapModuleResponse] = []
    for module in orm.modules:
        parts_response = [
            RoadmapPartResponse(
                part_id=part.part_id,
                title=part.title,
                order_index=part.order_index,
                has_prompt=bool(part.teaching_prompt),
            )
            for part in module.parts
        ]
        modules_response.append(
            RoadmapModuleResponse(
                module_id=module.module_id,
                title=module.title,
                order_index=module.order_index,
                parts=parts_response,
            )
        )

    return RoadmapResponse(
        session_id=session_id,
        title=orm.title,
        summary=orm.summary,
        total_modules=orm.total_modules,
        estimated_hours=orm.estimated_hours,
        modules=modules_response,
    )


__all__ = ["router"]

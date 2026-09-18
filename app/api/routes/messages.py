"""
Chat (messages) routes.

Endpoints:
    - POST /sessions/{id}/lessons/{part_id}/chat   ask a question
    - GET  /sessions/{id}/lessons/{part_id}/messages   list messages
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from app.agents.tutor.chat import tutor_chat
from app.api.dependencies import SessionDep
from app.schemas.session_api import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    MessagesListResponse,
)
from app.services import (
    lesson_service,
    message_service,
    profile_service,
    roadmap_service,
    session_service,
)

router = APIRouter(prefix="/sessions", tags=["chat"])
log = structlog.get_logger(__name__)


# ============================================================
# Helpers
# ============================================================

async def _load_context(db, session_id: int, part_id: str):
    """Load the session, part, module, profile, lesson needed for chat."""
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    part_orm = await roadmap_service.get_part_by_part_id(
        db, part_id, session_id=session_id
    )
    if part_orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id!r} not found in session {session_id}",
        )

    profile = await profile_service.get_by_session_as_pydantic(
        db, session_id
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile not submitted yet.",
        )

    lesson = await lesson_service.get_by_part_id_as_pydantic(
        db, part_id, session_id=session_id
    )

    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    parent_module = None
    if orm_roadmap is not None:
        for m in orm_roadmap.modules:
            if m.id == part_orm.module_id:
                parent_module = m
                break

    if parent_module is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parent module not found.",
        )

    return session, part_orm, parent_module, profile, lesson


def _to_response(orm) -> MessageResponse:
    return MessageResponse(
        id=orm.id,
        session_id=orm.session_id,
        roadmap_part_id=orm.roadmap_part_id,
        role=orm.role,
        content=orm.content,
        created_at=orm.created_at,
    )


# ============================================================
# POST: Ask a question
# ============================================================

@router.post(
    "/{session_id}/lessons/{part_id}/chat",
    response_model=ChatResponse,
    summary="Ask a question about a lesson",
)
async def ask_question(
    session_id: int,
    part_id: str,
    payload: ChatRequest,
    db: SessionDep,
) -> ChatResponse:
    """Ask the tutor a follow-up question about a specific lesson."""
    session, part_orm, parent_module, profile, lesson = await _load_context(
        db, session_id, part_id
    )

    # Build Pydantic models for the chat agent.
    from app.schemas.roadmap import ModuleTitle, PartTitle

    module_pyd = ModuleTitle(
        title=parent_module.title,
        parts=[PartTitle(title=p.title) for p in parent_module.parts],
    )
    part_pyd = PartTitle(title=part_orm.title)

    # Persist the user's message first.
    user_msg = await message_service.create(
        db,
        session_id=session_id,
        roadmap_part_id=part_orm.id,
        role="user",
        content=payload.question,
    )

    # Run the chat.
    try:
        answer = await tutor_chat.answer(
            question=payload.question,
            profile=profile,
            module=module_pyd,
            part=part_pyd,
            part_id=part_id,
            lesson=lesson,
            allow_web_search=payload.allow_web_search,
        )
    except Exception as exc:
        log.error(
            "chat_agent_failed",
            session_id=session_id,
            part_id=part_id,
            error_type=type(exc).__name__,
            error_message=str(exc)[:300],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chat failed: {type(exc).__name__}",
        )

    # Persist the assistant's message.
    assistant_msg = await message_service.create(
        db,
        session_id=session_id,
        roadmap_part_id=part_orm.id,
        role="assistant",
        content=answer.content,
    )

    await db.commit()

    log.info(
        "chat_completed",
        session_id=session_id,
        part_id=part_id,
        used_web_search=answer.used_web_search,
    )

    return ChatResponse(
        user_message=_to_response(user_msg),
        assistant_message=_to_response(assistant_msg),
        used_web_search=answer.used_web_search,
    )


# ============================================================
# GET: Messages history
# ============================================================

@router.get(
    "/{session_id}/lessons/{part_id}/messages",
    response_model=MessagesListResponse,
    summary="Get chat history for a lesson",
)
async def list_messages(
    session_id: int,
    part_id: str,
    db: SessionDep,
) -> MessagesListResponse:
    """Return all chat messages for a specific lesson."""
    session, part_orm, *_ = await _load_context(db, session_id, part_id)

    orms = await message_service.list_for_lesson(
        db, session_id, roadmap_part_id=part_orm.id
    )

    return MessagesListResponse(
        session_id=session_id,
        part_id=part_id,
        total=len(orms),
        messages=[_to_response(m) for m in orms],
    )


__all__ = ["router"]

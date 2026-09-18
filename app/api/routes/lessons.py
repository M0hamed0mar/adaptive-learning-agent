"""
Lessons routes (Phase 11 redesign).

New:
    - GET /sessions/{id}/lessons                   list (with `has_content`)
    - GET /sessions/{id}/lessons/{part_id}         get lesson (or 404)
    - POST /sessions/{id}/lessons/{part_id}/generate
                                                   lazy-generate the lesson

Lessons are generated on demand.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import SessionDep
from app.agents.tutor.agent import tutor_agent
from app.database import get_session as get_db_session
from app.schemas.session_api import (
    LessonDetail,
    SessionLessonsResponse,
)
from app.services import (
    lesson_service,
    profile_service,
    roadmap_service,
    session_service,
)

router = APIRouter(prefix="/sessions", tags=["lessons"])
log = structlog.get_logger(__name__)


# ============================================================
# List all lessons
# ============================================================

@router.get(
    "/{session_id}/lessons",
    response_model=SessionLessonsResponse,
    summary="List all lessons for a session",
)
async def list_lessons(
    session_id: int,
    db: SessionDep,
) -> SessionLessonsResponse:
    """Return all lessons (with content status) for the session."""
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    if orm_roadmap is None:
        return SessionLessonsResponse(
            session_id=session_id, total=0, lessons=[]
        )

    lessons_response: list[LessonDetail] = []
    for module in orm_roadmap.modules:
        for part in module.parts:
            lesson_orm = await lesson_service.get_by_roadmap_part_pk(
                db, part.id
            )
            has_content = bool(lesson_orm and lesson_orm.content)

            if has_content and lesson_orm.lesson_metadata:
                meta = lesson_orm.lesson_metadata
            else:
                meta = {
                    "part_id": part.part_id,
                    "module_title": module.title,
                    "part_title": part.title,
                    "topic": session.topic,
                    "role": "",
                    "level": "",
                    "difficulty": None,
                    "language": "ar",
                }

            lessons_response.append(
                LessonDetail(
                    part_id=part.part_id,
                    module_title=meta.get("module_title", module.title),
                    part_title=meta.get("part_title", part.title),
                    topic=meta.get("topic", session.topic),
                    role=meta.get("role", ""),
                    level=meta.get("level", ""),
                    difficulty=meta.get("difficulty"),
                    language=meta.get("language", "ar"),
                    content=lesson_orm.content if has_content else None,
                    is_generated=has_content,
                )
            )

    return SessionLessonsResponse(
        session_id=session_id,
        total=len(lessons_response),
        lessons=lessons_response,
    )


# ============================================================
# Get one lesson
# ============================================================

@router.get(
    "/{session_id}/lessons/{part_id}",
    response_model=LessonDetail,
    summary="Get a single lesson by part ID",
)
async def get_lesson(
    session_id: int,
    part_id: str,
    db: SessionDep,
) -> LessonDetail:
    """Return a single lesson. 404 if not yet generated."""
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

    lesson = await lesson_service.get_by_part_id_as_pydantic(
        db, part_id, session_id=session_id
    )
    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Lesson for part {part_id!r} not yet generated. "
                f"POST to .../generate to create it."
            ),
        )

    return LessonDetail(
        part_id=lesson.metadata.part_id,
        module_title=lesson.metadata.module_title,
        part_title=lesson.metadata.part_title,
        topic=lesson.metadata.topic,
        role=lesson.metadata.role,
        level=lesson.metadata.level,
        difficulty=lesson.metadata.difficulty,
        language=lesson.metadata.language,
        content=lesson.content,
        is_generated=True,
    )


# ============================================================
# Lazy generate lesson
# ============================================================

@router.post(
    "/{session_id}/lessons/{part_id}/generate",
    response_model=LessonDetail,
    summary="Generate a lesson on demand (lazy)",
)
async def generate_lesson(
    session_id: int,
    part_id: str,
    db: SessionDep,
) -> LessonDetail:
    """
    Generate a lesson for a part ON DEMAND.

    Idempotent: if the lesson already exists with content, it is
    returned immediately without calling the LLM.
    """
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    part_orm = await roadmap_service.get_part_by_part_id(
        db, part_id, session_id=session_id
    )
    if part_orm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Part {part_id!r} not found in session {session_id}",
        )

    if not part_orm.teaching_prompt:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Part {part_id!r} has no teaching prompt yet. "
                f"Wait for the pipeline to finish."
            ),
        )

    # If already generated, return it.
    existing = await lesson_service.get_by_part_id_as_pydantic(
        db, part_id, session_id=session_id
    )
    if existing is not None:
        return LessonDetail(
            part_id=existing.metadata.part_id,
            module_title=existing.metadata.module_title,
            part_title=existing.metadata.part_title,
            topic=existing.metadata.topic,
            role=existing.metadata.role,
            level=existing.metadata.level,
            difficulty=existing.metadata.difficulty,
            language=existing.metadata.language,
            content=existing.content,
            is_generated=True,
        )

    # Need profile + roadmap context for the tutor.
    profile = await profile_service.get_by_session_as_pydantic(
        db, session_id
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="Profile missing")

    # Find the parent module for the part.
    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    if orm_roadmap is None:
        raise HTTPException(status_code=409, detail="Roadmap missing")

    parent_module = None
    for module in orm_roadmap.modules:
        if module.id == part_orm.module_id:
            parent_module = module
            break

    if parent_module is None:
        raise HTTPException(status_code=409, detail="Module not found")

    # Rebuild Pydantic objects the tutor expects.
    from app.schemas.roadmap import ModuleTitle, PartTitle

    module_pyd = ModuleTitle(
        title=parent_module.title,
        parts=[PartTitle(title=p.title) for p in parent_module.parts],
    )
    part_pyd = PartTitle(title=part_orm.title)

    # Build a minimal TeachingPrompt (the tutor needs `.prompt`).
    from app.schemas.teaching import (
        TeachingPromptItem,
    )

    teaching_prompt_item = TeachingPromptItem(
        part_id=part_orm.part_id,
        title=part_orm.title,
        prompt=part_orm.teaching_prompt,
    )

    lesson = await tutor_agent.teach_from_prompt_item(
        profile=profile,
        module=module_pyd,
        part=part_pyd,
        part_id=part_orm.part_id,
        prompt_item=teaching_prompt_item,
    )

    # Persist (upsert).
    async with get_db_session() as write_db:
        existing_orm = await lesson_service.get_by_roadmap_part_pk(
            write_db, part_orm.id
        )
        if existing_orm is not None:
            await lesson_service.replace_content(
                write_db, existing_orm, lesson
            )
        else:
            await lesson_service.create_from_pydantic(
                write_db,
                roadmap_part_id=part_orm.id,
                lesson=lesson,
            )

    log.info(
        "api_lesson_generated",
        session_id=session_id,
        part_id=part_id,
        lesson_length=len(lesson.content),
    )

    return LessonDetail(
        part_id=lesson.metadata.part_id,
        module_title=lesson.metadata.module_title,
        part_title=lesson.metadata.part_title,
        topic=lesson.metadata.topic,
        role=lesson.metadata.role,
        level=lesson.metadata.level,
        difficulty=lesson.metadata.difficulty,
        language=lesson.metadata.language,
        content=lesson.content,
        is_generated=True,
    )


__all__ = ["router"]

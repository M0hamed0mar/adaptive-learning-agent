"""
Web (HTML) routes — Phase 12 (clean).

All routes return HTML, not JSON.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import SessionDep
from app.config.constants import (
    LearningGoal,
    LearningStyle,
    SessionStatus,
    UserLevel,
)
from app.services import (
    lesson_service,
    profile_service,
    progress_service,
    roadmap_service,
    session_service,
    user_service,
)
from app.web.helpers import (
    format_datetime,
    render_markdown,
    session_progress_text,
    shorten,
    status_label,
    time_ago,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["web"])

templates = Jinja2Templates(directory="app/web/templates")

templates.env.filters["markdown"] = render_markdown
templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["status_label"] = status_label
templates.env.filters["shorten"] = shorten
templates.env.filters["session_progress_text"] = session_progress_text
templates.env.filters["time_ago"] = time_ago


# ============================================================
# Shared helpers
# ============================================================

async def _sidebar_context(
    db,
    *,
    active_session_id: int | None = None,
) -> dict:
    user = await user_service.get_or_create_default(db)
    sessions = await session_service.list_for_user(
        db, user_id=user.id, limit=50
    )
    return {
        "sessions": sessions,
        "active_session_id": active_session_id,
    }


# ============================================================
# Landing
# ============================================================

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing(request: Request, db: SessionDep) -> HTMLResponse:
    ctx = await _sidebar_context(db)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "New session", **ctx},
    )


# ============================================================
# Sessions list
# ============================================================

@router.get("/sessions", response_class=HTMLResponse, include_in_schema=False)
async def sessions_list(request: Request, db: SessionDep) -> HTMLResponse:
    user = await user_service.get_or_create_default(db)
    sessions = await session_service.list_for_user(db, user_id=user.id)
    ctx = await _sidebar_context(db)
    return templates.TemplateResponse(
        request=request,
        name="sessions_list.html",
        context={"title": "My sessions", "sessions_all": sessions, **ctx},
    )


# ============================================================
# Create session
# ============================================================

@router.post("/sessions", include_in_schema=False)
async def create_session_web(
    db: SessionDep,
    raw_input: str = Form(...),
) -> RedirectResponse:
    raw = raw_input.strip()
    if len(raw) < 5:
        raise HTTPException(status_code=422, detail="Description too short.")

    user = await user_service.get_or_create_default(db)
    session = await session_service.create(
        db,
        user_id=user.id,
        topic=raw[:80],
        title=raw,
        status=SessionStatus.DRAFT,
    )
    await db.commit()
    logger.info("web_session_created", session_id=session.id)
    return RedirectResponse(
        url=f"/sessions/{session.id}/profile",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ============================================================
# Delete session (HTMX)
# ============================================================

@router.delete("/web/sessions/{session_id}", include_in_schema=False)
async def delete_session_web(
    session_id: int,
    db: SessionDep,
) -> HTMLResponse:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await session_service.delete(db, session)
    await db.commit()
    logger.info("web_session_deleted", session_id=session_id)
    return HTMLResponse("")


# ============================================================
# Sidebar partial
# ============================================================

@router.get(
    "/web/sessions/partial",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def sessions_sidebar_partial(
    request: Request, db: SessionDep
) -> HTMLResponse:
    ctx = await _sidebar_context(db)
    return templates.TemplateResponse(
        request=request,
        name="partials/sessions_sidebar.html",
        context=ctx,
    )


# ============================================================
# Dashboard
# ============================================================

@router.get(
    "/sessions/{session_id}/dashboard",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def session_dashboard(
    request: Request,
    session_id: int,
    db: SessionDep,
) -> HTMLResponse:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = await profile_service.get_by_session_as_pydantic(db, session_id)
    roadmap = await roadmap_service.get_by_session(db, session_id)
    progress = await progress_service.get_by_session(db, session_id)
    ctx = await _sidebar_context(db, active_session_id=session_id)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "title": session.title or session.topic,
            "session": session,
            "profile": profile,
            "roadmap": roadmap,
            "progress": progress,
            **ctx,
        },
    )


# ============================================================
# Status partial (HTMX polling)
# ============================================================

@router.get(
    "/web/sessions/{session_id}/status",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def session_status_partial(
    request: Request,
    session_id: int,
    db: SessionDep,
) -> HTMLResponse:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return templates.TemplateResponse(
        request=request,
        name="partials/session_status.html",
        context={"session": session},
    )


# ============================================================
# Profile form
# ============================================================

@router.get(
    "/sessions/{session_id}/profile",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def profile_form(
    request: Request,
    session_id: int,
    db: SessionDep,
) -> HTMLResponse:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = await profile_service.get_by_session(db, session_id)
    if existing is not None:
        return RedirectResponse(
            url=f"/sessions/{session_id}/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    ctx = await _sidebar_context(db, active_session_id=session_id)
    return templates.TemplateResponse(
        request=request,
        name="profile_form.html",
        context={
            "title": "Tell us about you",
            "session": session,
            "levels": list(UserLevel),
            "goals": list(LearningGoal),
            "styles": list(LearningStyle),
            **ctx,
        },
    )


@router.post("/sessions/{session_id}/profile", include_in_schema=False)
async def submit_profile_web(
    session_id: int,
    db: SessionDep,
    level: str = Form(...),
    goal: str = Form(...),
    role: str = Form(...),
    learning_style: str = Form(...),
) -> RedirectResponse:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in (
        SessionStatus.DRAFT.value,
        SessionStatus.FAILED.value,
    ):
        return RedirectResponse(
            url=f"/sessions/{session_id}/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    await session_service.update_status(db, session, SessionStatus.PLANNING)
    await db.commit()

    from app.web.background import spawn_pipeline_for_session

    spawn_pipeline_for_session(
        session_id=session.id,
        raw_input=session.title or session.topic,
        profile_answers={
            "level": level,
            "goal": goal,
            "role": role.strip() or "General Learner",
            "learning_style": learning_style,
        },
    )

    logger.info("web_profile_submitted", session_id=session.id)
    return RedirectResponse(
        url=f"/sessions/{session_id}/dashboard",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ============================================================
# Session view (course overview)
# ============================================================

@router.get(
    "/sessions/{session_id}/session",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def session_view(
    request: Request,
    session_id: int,
    db: SessionDep,
) -> HTMLResponse:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    progress = await progress_service.get_by_session(db, session_id)
    completed = set(progress.completed_parts) if progress else set()

    ctx = await _sidebar_context(db, active_session_id=session_id)
    return templates.TemplateResponse(
        request=request,
        name="session.html",
        context={
            "title": session.title or session.topic,
            "session": session,
            "roadmap": orm_roadmap,
            "progress": progress,
            "completed_parts": completed,
            **ctx,
        },
    )


# ============================================================
# Lesson view
# ============================================================

@router.get(
    "/sessions/{session_id}/lessons/{part_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def lesson_view(
    request: Request,
    session_id: int,
    part_id: str,
    db: SessionDep,
) -> HTMLResponse:
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    if orm_roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap missing")

    current_part = None
    parent_module = None
    for module in orm_roadmap.modules:
        for part in module.parts:
            if part.part_id == part_id:
                current_part = part
                parent_module = module
                break
        if current_part:
            break

    if current_part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    flat = [(m, p) for m in orm_roadmap.modules for p in m.parts]
    current_idx = next(
        i for i, (_, p) in enumerate(flat) if p.part_id == part_id
    )
    prev_part_id = flat[current_idx - 1][1].part_id if current_idx > 0 else None
    next_part_id = (
        flat[current_idx + 1][1].part_id
        if current_idx + 1 < len(flat) else None
    )

    progress = await progress_service.get_by_session(db, session_id)
    completed = set(progress.completed_parts) if progress else set()

    lesson = await lesson_service.get_by_part_id_as_pydantic(
        db, part_id, session_id=session_id
    )

    ctx = await _sidebar_context(db, active_session_id=session_id)
    return templates.TemplateResponse(
        request=request,
        name="lesson.html",
        context={
            "title": current_part.title,
            "session": session,
            "roadmap": orm_roadmap,
            "progress": progress,
            "module": parent_module,
            "part": current_part,
            "lesson": lesson,
            "is_completed": part_id in completed,
            "prev_part_id": prev_part_id,
            "next_part_id": next_part_id,
            "completed_parts": completed,
            **ctx,
        },
    )


# ============================================================
# Lazy lesson generation (HTMX)
# ============================================================

@router.post(
    "/sessions/{session_id}/lessons/{part_id}/generate",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def generate_lesson_htmx(
    request: Request,
    session_id: int,
    part_id: str,
    db: SessionDep,
) -> HTMLResponse:
    from app.agents.tutor.agent import tutor_agent
    from app.schemas.roadmap import ModuleTitle, PartTitle
    from app.schemas.teaching import TeachingPromptItem

    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    part = await roadmap_service.get_part_by_part_id(
        db, part_id, session_id=session_id
    )
    if part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    if not part.teaching_prompt:
        raise HTTPException(
            status_code=409,
            detail="Teaching brief not ready yet.",
        )

    existing = await lesson_service.get_by_part_id_as_pydantic(
        db, part_id, session_id=session_id
    )
    if existing is not None:
        return templates.TemplateResponse(
            request=request,
            name="partials/lesson_content.html",
            context={
                "lesson": existing,
                "is_completed": False,
                "session": session,
            },
        )

    profile = await profile_service.get_by_session_as_pydantic(db, session_id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Profile missing.")

    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    parent_module = None
    for m in orm_roadmap.modules:
        if m.id == part.module_id:
            parent_module = m
            break
    if parent_module is None:
        raise HTTPException(status_code=409, detail="Module missing.")

    module_pyd = ModuleTitle(
        title=parent_module.title,
        parts=[PartTitle(title=p.title) for p in parent_module.parts],
    )
    part_pyd = PartTitle(title=part.title)
    prompt_item = TeachingPromptItem(
        part_id=part.part_id,
        title=part.title,
        prompt=part.teaching_prompt,
    )

    lesson = await tutor_agent.teach_from_prompt_item(
        profile=profile,
        module=module_pyd,
        part=part_pyd,
        part_id=part.part_id,
        prompt_item=prompt_item,
    )

    existing_orm = await lesson_service.get_by_roadmap_part_pk(db, part.id)
    if existing_orm is not None:
        await lesson_service.replace_content(db, existing_orm, lesson)
    else:
        await lesson_service.create_from_pydantic(
            db, roadmap_part_id=part.id, lesson=lesson
        )
    await db.commit()

    logger.info(
        "web_lesson_generated",
        session_id=session_id,
        part_id=part_id,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/lesson_content.html",
        context={
            "lesson": lesson,
            "is_completed": False,
            "session": session,
        },
    )


# ============================================================
# Mark part completed (HTMX)
# ============================================================

@router.post(
    "/web/sessions/{session_id}/progress/complete",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def mark_completed_htmx(
    session_id: int,
    db: SessionDep,
    part_id: str = Form(...),
) -> HTMLResponse:
    """HTMX: mark a part as completed."""
    progress = await progress_service.get_by_session(db, session_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Progress not found")

    progress = await progress_service.mark_part_completed(
        db, progress, part_id=part_id
    )
    await db.commit()

    return HTMLResponse(
        '<span class="inline-flex items-center gap-2 '
        'bg-emerald-50 text-emerald-700 text-sm font-medium '
        'py-2 px-4 rounded-lg border border-emerald-200">'
        '<i class="fa-solid fa-check"></i>'
        '<span>Completed</span></span>'
    )


# ============================================================
# Module tree partial (HTMX)
# ============================================================

@router.get(
    "/web/sessions/{session_id}/module-tree",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def module_tree_partial(
    request: Request,
    session_id: int,
    db: SessionDep,
    current: str | None = None,
) -> HTMLResponse:
    """HTMX: return the module tree sidebar."""
    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    progress = await progress_service.get_by_session(db, session_id)
    completed = set(progress.completed_parts) if progress else set()

    return templates.TemplateResponse(
        request=request,
        name="partials/module_tree.html",
        context={
            "session": session,
            "roadmap": orm_roadmap,
            "progress": progress,
            "completed_parts": completed,
            "current_part_id": current,
        },
    )




# ============================================================
# Chat panel (HTMX)
# ============================================================

@router.get(
    "/web/sessions/{session_id}/lessons/{part_id}/chat",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def chat_panel_partial(
    request: Request,
    session_id: int,
    part_id: str,
    db: SessionDep,
) -> HTMLResponse:
    """Render the chat panel with existing messages."""
    from app.services import message_service

    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    part = await roadmap_service.get_part_by_part_id(
        db, part_id, session_id=session_id
    )
    if part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    orm_messages = await message_service.list_for_lesson(
        db, session_id, roadmap_part_id=part.id
    )
    messages_pyd = [
        message_service.to_pydantic(m) for m in orm_messages
    ]

    return templates.TemplateResponse(
        request=request,
        name="partials/chat_panel.html",
        context={
            "session": session,
            "part": part,
            "messages": messages_pyd,
        },
    )


# ============================================================
# Chat message (HTMX)
# ============================================================

@router.post(
    "/web/sessions/{session_id}/lessons/{part_id}/chat",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def post_chat_message(
    request: Request,
    session_id: int,
    part_id: str,
    db: SessionDep,
    question: str = Form(...),
    allow_web_search: str = Form("false"),
) -> HTMLResponse:
    """Handle a chat question and return the two new messages as HTML."""
    from app.agents.tutor.chat import tutor_chat
    from app.schemas.roadmap import ModuleTitle, PartTitle
    from app.services import message_service

    session = await session_service.get(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    part = await roadmap_service.get_part_by_part_id(
        db, part_id, session_id=session_id
    )
    if part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    profile = await profile_service.get_by_session_as_pydantic(
        db, session_id
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="Profile missing")

    orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
    parent_module = None
    for m in orm_roadmap.modules:
        if m.id == part.module_id:
            parent_module = m
            break
    if parent_module is None:
        raise HTTPException(status_code=409, detail="Module missing")

    lesson = await lesson_service.get_by_part_id_as_pydantic(
        db, part_id, session_id=session_id
    )

    # Persist user message
    user_orm = await message_service.create(
        db,
        session_id=session_id,
        roadmap_part_id=part.id,
        role="user",
        content=question.strip(),
    )

    # Run the chat
    module_pyd = ModuleTitle(
        title=parent_module.title,
        parts=[PartTitle(title=p.title) for p in parent_module.parts],
    )
    part_pyd = PartTitle(title=part.title)

    try:
        answer = await tutor_chat.answer(
            question=question.strip(),
            profile=profile,
            module=module_pyd,
            part=part_pyd,
            part_id=part_id,
            lesson=lesson,
            allow_web_search=(allow_web_search == "true"),
        )
    except Exception as exc:
        logger.error(
            "web_chat_agent_failed",
            session_id=session_id,
            part_id=part_id,
            error=str(exc)[:300],
        )
        # Return an error message in the chat
        error_orm = await message_service.create(
            db,
            session_id=session_id,
            roadmap_part_id=part.id,
            role="assistant",
            content=(
                "**عذرًا** — حدث خطأ أثناء معالجة السؤال. "
                "حاول مرة أخرى."
            ),
        )
        await db.commit()

        user_pyd = message_service.to_pydantic(user_orm)
        error_pyd = message_service.to_pydantic(error_orm)

        return templates.TemplateResponse(
            request=request,
            name="partials/message_item.html",
            context={"m": user_pyd},
        )

    # Persist assistant message
    assistant_orm = await message_service.create(
        db,
        session_id=session_id,
        roadmap_part_id=part.id,
        role="assistant",
        content=answer.content,
    )
    await db.commit()

    user_pyd = message_service.to_pydantic(user_orm)
    assistant_pyd = message_service.to_pydantic(assistant_orm)

    # Return both messages concatenated (HTMX appends both).
    html_parts = []
    for msg in (user_pyd, assistant_pyd):
        tmpl = templates.get_template("partials/message_item.html")
        html_parts.append(
            tmpl.render(m=msg, request=request)
        )
    return HTMLResponse("".join(html_parts))


__all__ = ["router"]

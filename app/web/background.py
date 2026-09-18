"""
Background task helpers for the web layer.

Runs the learning pipeline and updates the session's progress fields
as it advances through the stages.

Design notes:
    - Uses `asyncio.create_task` (not FastAPI BackgroundTasks).
    - Keeps strong references to in-flight tasks to avoid GC.
    - Progress is written to the session row (pipeline_stage,
      pipeline_progress, pipeline_message) so the dashboard can
      display it while polling.
"""

from __future__ import annotations

import asyncio

import structlog

from app.config.constants import SessionStatus
from app.database import get_session as get_db_session
from app.graph import get_learning_graph
from app.services import session_service

logger = structlog.get_logger(__name__)


_running_tasks: set[asyncio.Task] = set()


# ============================================================
# Progress map (stage → percentage + default message)
# ============================================================

_STAGE_PROGRESS: dict[str, tuple[int, str]] = {
    "starting":           (5,   "Preparing..."),
    "building_profile":   (15,  "Analyzing your goals..."),
    "generating_roadmap": (35,  "Designing your roadmap..."),
    "evaluating_roadmap": (50,  "Refining roadmap quality..."),
    "saving_roadmap":     (60,  "Saving roadmap..."),
    "generating_prompts": (75,  "Preparing teaching prompts..."),
    "evaluating_prompts": (85,  "Refining prompts..."),
    "saving_prompts":     (95,  "Finalizing..."),
    "done":               (100, "Ready!"),
}


# ============================================================
# Progress updater
# ============================================================

async def _update_progress(
    session_id: int,
    *,
    stage: str,
    message: str | None = None,
) -> None:
    """Update the session's pipeline progress in the DB."""
    pct, default_msg = _STAGE_PROGRESS.get(stage, (0, "Working..."))
    final_msg = message or default_msg

    try:
        async with get_db_session() as db:
            session = await session_service.get(db, session_id)
            if session is None:
                return
            session.pipeline_stage = stage
            session.pipeline_progress = pct
            session.pipeline_message = final_msg
            await db.commit()
    except Exception as e:
        logger.error(
            "progress_update_failed",
            session_id=session_id,
            error=str(e),
        )


# ============================================================
# Pipeline runner
# ============================================================

async def _run_pipeline(
    *,
    session_id: int,
    raw_input: str,
    profile_answers: dict[str, str],
) -> None:
    """
    Run the learning pipeline graph and update the session status.
    """
    log = logger.bind(
        background_task="web_run_pipeline",
        session_id=session_id,
    )
    log.info("web_pipeline_started")

    try:
        # --- Stage: starting ---
        await _update_progress(session_id, stage="starting")

        # --- Stage: building profile ---
        await _update_progress(session_id, stage="building_profile")

        # --- Run the graph as a whole ---
        # We can't easily hook into individual graph nodes without
        # changing the graph itself, so we update progress before and
        # after the graph call.
        await _update_progress(session_id, stage="generating_roadmap")

        graph = get_learning_graph()
        final_state = await graph.ainvoke(
            {
                "session_id": session_id,
                "raw_input": raw_input,
                "profile_answers": profile_answers,
            }
        )

        # --- Stage: done ---
        await _update_progress(session_id, stage="done")

        final_status = final_state.get("status", SessionStatus.READY.value)
        log.info(
            "web_pipeline_completed",
            final_status=final_status,
        )

        async with get_db_session() as db:
            session = await session_service.get(db, session_id)
            if session is not None:
                await session_service.update_status(
                    db, session, SessionStatus.READY
                )

    except Exception as exc:
        log.error(
            "web_pipeline_failed",
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
                    session.pipeline_message = f"Failed: {exc}"
                    await db.commit()
        except Exception as inner:
            log.error(
                "web_pipeline_status_update_failed",
                error=str(inner),
            )


# ============================================================
# Public entry point
# ============================================================

def spawn_pipeline_for_session(
    *,
    session_id: int,
    raw_input: str,
    profile_answers: dict[str, str],
) -> None:
    """
    Public entry point: spawn the pipeline for a session.

    Safe to call from inside an async route handler.

    Args:
        session_id: The session to run the pipeline for.
        raw_input: The user's original free-text description.
        profile_answers: The 4 answers from the profile form
            (level, goal, role, learning_style).
    """
    task = asyncio.create_task(
        _run_pipeline(
            session_id=session_id,
            raw_input=raw_input,
            profile_answers=profile_answers,
        )
    )
    _running_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _running_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error(
                "web_background_task_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    task.add_done_callback(_on_done)


__all__ = ["spawn_pipeline_for_session"]

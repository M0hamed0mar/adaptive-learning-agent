"""
Content nodes (Phase 12).

Simplified pipeline: generate briefs → save to roadmap parts.
The critic and refiner for briefs have been removed — the generator
produces briefs good enough on the first pass.
"""

from __future__ import annotations

import structlog

from app.agents.prompt.set_generator import teaching_set_generator
from app.database import get_session
from app.graph.state import LearningState
from app.services import roadmap_service, session_service

logger = structlog.get_logger(__name__)


# ============================================================
# Progress callback factory
# ============================================================

async def _make_progress_callback(session_id: int):
    """Return an async callback that updates session progress."""

    async def _cb(done: int, total: int) -> None:
        if total <= 0:
            return
        start_pct = 40
        end_pct = 95
        pct = start_pct + int((done / total) * (end_pct - start_pct))

        try:
            async with get_session() as db:
                s = await session_service.get(db, session_id)
                if s is not None:
                    s.pipeline_progress = pct
                    s.pipeline_message = (
                        f"Writing lessons... ({done}/{total})"
                    )
                    await db.commit()
        except Exception as e:
            logger.warning(
                "progress_update_failed",
                session_id=session_id,
                error=str(e),
            )

    return _cb


# ============================================================
# Generate briefs and save (single node)
# ============================================================

async def generate_prompts_node(state: LearningState) -> dict:
    """
    Generate briefs for all parts and attach them to the roadmap.

    This node replaces the old three-step pipeline
    (generate → evaluate → refine → save). The critic and refiner
    were removed because the brief generator produces acceptable
    output on the first pass.
    """
    session_id = state["session_id"]
    log = logger.bind(node="generate_prompts", session_id=session_id)
    log.info("generate_prompts_started")

    profile = state["profile"]
    roadmap = state["roadmap"]

    # --- Set progress to "generating" ---
    async with get_session() as db:
        s = await session_service.get(db, session_id)
        if s is not None:
            s.pipeline_stage = "generating_prompts"
            s.pipeline_progress = 40
            s.pipeline_message = "Writing lessons..."
            await db.commit()

    # --- Generate briefs (with progress callback) ---
    cb = await _make_progress_callback(session_id)
    prompt_set = await teaching_set_generator.generate(
        profile=profile,
        roadmap=roadmap,
        on_progress=cb,
    )
    log.info(
        "briefs_generated",
        prompt_count=len(prompt_set.prompts),
    )

    # --- Save briefs to roadmap parts ---
    from app.services import progress_service

    async with get_session() as db:
        attached = await roadmap_service.attach_prompts(
            db, session_id=session_id, prompt_set=prompt_set
        )

        # Create the progress record if it does not exist yet.
        existing_progress = await progress_service.get_by_session(
            db, session_id
        )
        if existing_progress is None:
            # Count total parts from the roadmap.
            orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
            total_parts = 0
            if orm_roadmap is not None:
                total_parts = sum(
                    len(m.parts) for m in orm_roadmap.modules
                )
            await progress_service.create_for_session(
                db,
                session_id=session_id,
                total_parts=total_parts,
            )
            log.info("progress_created", total_parts=total_parts)

        s = await session_service.get(db, session_id)
        if s is not None:
            s.pipeline_stage = "done"
            s.pipeline_progress = 100
            s.pipeline_message = "Ready!"
            await db.commit()

    log.info(
        "generate_prompts_completed",
        attached=attached,
        status="ready",
    )
    return {
        "prompt_set": prompt_set,
        "status": "ready",
    }


__all__ = ["generate_prompts_node"]

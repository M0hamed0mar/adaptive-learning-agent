"""
Test 03: Web background task.

Simulates what happens when the user submits a profile via the
web form:
    1. Create a session (like the landing page does).
    2. Call `spawn_pipeline_for_session` (like the route handler does).
    3. Poll the session until it's ready or failed.
    4. Report progress and final state.

Writes results to tests/manual/_report_03_web.txt
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config.constants import SessionStatus
from app.core.logging import configure_logging
from app.database import get_session
from app.services import roadmap_service, session_service, user_service
from app.web.background import spawn_pipeline_for_session


REPORT_PATH = Path(__file__).resolve().parent / "_report_03_web.txt"

MAX_WAIT_S = 300  # 5 minutes max


def log(msg: str) -> None:
    print(msg)
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


async def main() -> bool:
    REPORT_PATH.write_text("", encoding="utf-8")
    configure_logging()

    log("=" * 70)
    log("TEST 03: Web Background Task")
    log("=" * 70)
    log("")

    ok = True

    # --- Setup ---
    log("[Setup] Creating session...")
    async with get_session() as db:
        user = await user_service.get_or_create_default(db)
        session = await session_service.create(
            db,
            user_id=user.id,
            topic="Docker",
            title=(
                "I am a beginner AI Engineer. I want to learn Docker "
                "for my ML projects. I prefer practical examples."
            ),
            status=SessionStatus.DRAFT,
        )
        session_id = session.id
        # Mark as planning (like the route does)
        await session_service.update_status(
            db, session, SessionStatus.PLANNING
        )
    log(f"  OK    session_id={session_id}")
    log("")

    # --- Spawn the background pipeline ---
    log("[Run] Calling spawn_pipeline_for_session()...")
    spawn_pipeline_for_session(
        session_id=session_id,
        raw_input=(
            "I am a beginner AI Engineer. I want to learn Docker "
            "for my ML projects. I prefer practical examples."
        ),
        profile_answers={
            "level": "beginner",
            "goal": "build_projects",
            "role": "AI Engineer",
            "learning_style": "practical",
        },
    )
    log("  OK    task spawned")
    log("")

    # --- Poll the session ---
    log("[Watch] Polling session status (every 2s, max 5min)...")
    started = time.perf_counter()
    last = None
    final_status = None

    while True:
        await asyncio.sleep(2.0)
        elapsed = time.perf_counter() - started

        if elapsed > MAX_WAIT_S:
            ok = False
            log(f"  FAIL  timeout after {MAX_WAIT_S}s")
            break

        async with get_session() as db:
            s = await session_service.get(db, session_id)

        if s is None:
            ok = False
            log("  FAIL  session disappeared")
            break

        current = (s.status, s.pipeline_stage, s.pipeline_progress)
        if current != last:
            log(
                f"  [{elapsed:6.1f}s] "
                f"status={s.status!r:12s} "
                f"stage={s.pipeline_stage!s:25s} "
                f"pct={s.pipeline_progress:3d}% "
                f"msg={s.pipeline_message!r}"
            )
            last = current

        if s.status in (
            SessionStatus.READY.value,
            SessionStatus.FAILED.value,
        ):
            final_status = s.status
            break

    log("")
    log(f"[Result] Final status: {final_status!r} after {time.perf_counter() - started:.1f}s")
    log("")

    if final_status != SessionStatus.READY.value:
        ok = False
        log(f"  FAIL: expected 'ready', got {final_status!r}")
    log("")

    # --- DB verification ---
    log("[Verify] DB state:")
    async with get_session() as db:
        s = await session_service.get(db, session_id)
        log(f"  session.status:  {s.status!r}")
        log(f"  pipeline_stage:  {s.pipeline_stage!r}")
        log(f"  pipeline_pct:    {s.pipeline_progress}%")
        log(f"  pipeline_msg:    {s.pipeline_message!r}")

        orm_roadmap = await roadmap_service.get_with_tree(db, session_id)
        if orm_roadmap:
            total_parts = sum(len(m.parts) for m in orm_roadmap.modules)
            with_prompts = sum(
                1 for m in orm_roadmap.modules
                for p in m.parts if p.teaching_prompt
            )
            log(f"  roadmap:         {orm_roadmap.total_modules} modules, "
                f"{total_parts} parts")
            log(f"  parts w/prompt:  {with_prompts}/{total_parts}")
        else:
            log("  roadmap:         MISSING")
    log("")

    log("=" * 70)
    log(f"RESULT: {'PASS' if ok else 'FAIL'}")
    log("=" * 70)

    return ok


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)

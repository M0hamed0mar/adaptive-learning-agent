"""
Test 02: Learning graph.

Invokes the full graph (build_profile → roadmap titles → prompts)
with a small profile, and monitors the session's progress fields.

Writes results to tests/manual/_report_02_graph.txt
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
from app.graph import get_learning_graph
from app.services import roadmap_service, session_service, user_service


REPORT_PATH = Path(__file__).resolve().parent / "_report_02_graph.txt"


def log(msg: str) -> None:
    print(msg)
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


async def main() -> bool:
    REPORT_PATH.write_text("", encoding="utf-8")
    configure_logging()

    log("=" * 70)
    log("TEST 02: Learning Graph")
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
    log(f"  OK    session_id={session_id}")
    log("")

    initial_state = {
        "session_id": session_id,
        "raw_input": (
            "I am a beginner AI Engineer. I want to learn Docker "
            "for my ML projects. I prefer practical examples."
        ),
        "profile_answers": {
            "level": "beginner",
            "goal": "build_projects",
            "role": "AI Engineer",
            "learning_style": "practical",
        },
    }

    # --- Run the graph ---
    log("[Run] Invoking the graph...")
    graph = get_learning_graph()
    started = time.perf_counter()

    task = asyncio.create_task(graph.ainvoke(initial_state))

    # Poll progress
    last = None
    while not task.done():
        await asyncio.sleep(2.0)
        async with get_session() as db:
            s = await session_service.get(db, session_id)
            if s is not None:
                current = (s.pipeline_stage, s.pipeline_progress)
                if current != last:
                    elapsed = time.perf_counter() - started
                    log(
                        f"  [{elapsed:6.1f}s] "
                        f"stage={s.pipeline_stage!s:25s} "
                        f"pct={s.pipeline_progress:3d}% "
                        f"msg={s.pipeline_message!r}"
                    )
                    last = current

    try:
        final = await task
    except Exception as e:
        ok = False
        log(f"  FAIL  graph failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout)
        return False

    elapsed = time.perf_counter() - started
    log(f"  OK    graph finished in {elapsed:.1f}s")
    log("")

    # --- Final state ---
    log("[Result] Final state summary:")
    log(f"  status:          {final.get('status')!r}")
    profile = final.get("profile")
    if profile:
        log(f"  profile.topic:   {profile.topic!r}")
        log(f"  profile.level:   {profile.level.value!r}")
    roadmap = final.get("roadmap")
    if roadmap:
        log(f"  roadmap.title:   {roadmap.title!r}")
        log(f"  roadmap.modules: {roadmap.total_modules}")
        for m in roadmap.modules:
            log(f"    - {m.title!r} ({len(m.parts)} parts)")
    critique = final.get("roadmap_critique")
    if critique:
        log(f"  roadmap.score:   {critique.score} ({critique.is_acceptable=})")
    prompt_set = final.get("prompt_set")
    if prompt_set:
        log(f"  prompt_set:      {len(prompt_set.prompts)} prompts")
    errors = final.get("errors")
    if errors:
        ok = False
        log(f"  errors:          {errors}")
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
            if with_prompts == 0:
                ok = False
                log("  FAIL: no teaching prompts attached!")
        else:
            ok = False
            log("  FAIL: roadmap missing in DB!")
    log("")

    log("=" * 70)
    log(f"RESULT: {'PASS' if ok else 'FAIL'}")
    log("=" * 70)

    return ok


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)

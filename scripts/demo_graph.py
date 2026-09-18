"""
Full end-to-end integration test for the learning graph.

This script:
    1. Creates a User + Session in the database.
    2. Invokes the learning graph with the initial state.
    3. Verifies everything was persisted correctly.

The graph runs the FULL pipeline:
    build_profile → generate_roadmap → evaluate_roadmap
        → (refine if needed) → save_roadmap → generate_content

Run:
    python scripts/demo_graph.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import structlog  # noqa: E402

from app.config.constants import (  # noqa: E402
    LearningGoal,
    LearningStyle,
    UserLevel,
)
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.database import get_session  # noqa: E402
from app.graph import get_learning_graph  # noqa: E402
from app.services import (  # noqa: E402
    lesson_service,
    progress_service,
    roadmap_service,
    session_service,
    user_service,
)


async def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    log.info("demo_graph_started")

    # ============================================================
    # Step 1 — Setup: create User + Session
    # ============================================================
    async with get_session() as db:
        user = await user_service.get_or_create_default(db)
        session = await session_service.create(
            db,
            user_id=user.id,
            topic="Docker",
            title="Docker for AI Engineers (graph demo)",
        )
        session_id = session.id

    print(f"\n✅ Session created: id={session_id}\n")

    # ============================================================
    # Step 2 — Build initial state
    # ============================================================
    initial_state = {
        "session_id": session_id,
        "topic": "Docker",
        "raw_input": "Docker for AI Engineers",
        "profile_answers": {
            "level": UserLevel.BEGINNER.value,
            "goal": LearningGoal.BUILD_PROJECTS.value,
            "role": "AI Engineer",
            "learning_style": LearningStyle.PRACTICAL.value,
            "focus": "Dockerizing FastAPI applications",
        },
    }

    # ============================================================
    # Step 3 — Invoke the graph
    # ============================================================
    print("⏳ Invoking graph (this takes 3-5 minutes)...")
    print("   Nodes: build_profile → generate_roadmap → evaluate_roadmap")
    print("          → (refine loop) → save_roadmap → generate_content")
    print()

    graph = get_learning_graph()
    started_at = time.perf_counter()

    final_state = await graph.ainvoke(initial_state)

    elapsed = time.perf_counter() - started_at
    print(f"\n✅ Graph finished in {elapsed:.1f}s\n")

    # ============================================================
    # Step 4 — Print summary
    # ============================================================
    print("=" * 78)
    print("📊 GRAPH EXECUTION SUMMARY")
    print("=" * 78)

    profile = final_state.get("profile")
    roadmap = final_state.get("roadmap")
    roadmap_critique = final_state.get("roadmap_critique")

    print(f"   Session ID:            {session_id}")
    print(f"   Status:                {final_state.get('status')!r}")
    print()
    print(f"   Profile topic:         {profile.topic!r}" if profile else "   Profile: (missing)")
    print(f"   Profile level:         {profile.level.value!r}" if profile else "")
    print()
    if roadmap:
        print(f"   Roadmap title:         {roadmap.title!r}")
        print(f"   Roadmap modules:       {roadmap.total_modules}")
        print(f"   Roadmap parts:         {final_state.get('total_parts')}")
    if roadmap_critique:
        print(f"   Roadmap score:         {roadmap_critique.score}")
        print(f"   Roadmap acceptable:    {roadmap_critique.is_acceptable}")
    print(f"   Refinement iterations: {final_state.get('roadmap_iterations')}")
    print()
    print(f"   Lessons generated:     {final_state.get('lessons_generated')}")
    print(f"   Total parts:           {final_state.get('total_parts')}")

    errors = final_state.get("errors")
    if errors:
        print(f"\n⚠️  Errors ({len(errors)}):")
        for err in errors:
            print(f"     - {err}")

    # ============================================================
    # Step 5 — Verify DB persistence
    # ============================================================
    print()
    print("=" * 78)
    print("🔍 DB VERIFICATION")
    print("=" * 78)

    verify_errors: list[str] = []

    async with get_session() as db:
        # Profile
        from app.services import profile_service
        profile_pyd = await profile_service.get_by_session_as_pydantic(
            db, session_id
        )
        if profile_pyd is None:
            verify_errors.append("Profile not found in DB")
        else:
            print(f"   ✅ Profile persisted: topic={profile_pyd.topic!r}")

        # Roadmap
        roadmap_pyd = await roadmap_service.get_with_tree_as_pydantic(
            db, session_id
        )
        if roadmap_pyd is None:
            verify_errors.append("Roadmap not found in DB")
        else:
            total_parts = sum(len(m.parts) for m in roadmap_pyd.modules)
            print(f"   ✅ Roadmap persisted: {roadmap_pyd.title!r} "
                  f"({len(roadmap_pyd.modules)} modules, {total_parts} parts)")

            # Count lessons
            lessons_count = 0
            for m in roadmap_pyd.modules:
                for p in m.parts:
                    lesson = await lesson_service.get_by_part_id_as_pydantic(
                        db, p.id
                    )
                    if lesson:
                        lessons_count += 1
                    else:
                        verify_errors.append(f"Missing lesson for {p.id}")

            print(f"   ✅ Lessons persisted: {lessons_count}/{total_parts}")

        # Progress
        progress = await progress_service.get_by_session(db, session_id)
        if progress is None:
            verify_errors.append("Progress not found in DB")
        else:
            print(
                f"   ✅ Progress persisted: {progress.percentage}% "
                f"({len(progress.completed_parts)}/{progress.total_parts})"
            )

    # ============================================================
    # Final report
    # ============================================================
    print()
    print("=" * 78)
    if verify_errors:
        print(f"❌ VERIFICATION FAILED ({len(verify_errors)} error(s)):")
        for err in verify_errors:
            print(f"   - {err}")
        sys.exit(1)
    else:
        print("🎉 GRAPH DEMO PASSED — everything persisted correctly!")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
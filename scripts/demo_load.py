"""
End-to-end persistence demo — Load phase.

Reads a session from the database and prints its full contents WITHOUT
regenerating anything.

The session ID is read from the `SESSION_ID` environment variable.
If not set, the most recent session is used.

Run:
    SESSION_ID=3 python scripts/demo_load.py
    # or
    python scripts/demo_load.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import structlog  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.database import get_session  # noqa: E402
from app.models.session import StudySession  # noqa: E402
from app.services import (  # noqa: E402
    lesson_service,
    profile_service,
    progress_service,
    roadmap_service,
    session_service,
)


async def _resolve_session_id(db) -> int | None:
    """
    Resolve the target session ID.

    Priority:
        1. `SESSION_ID` environment variable, if set and valid.
        2. The most recently created session in the DB.
    """
    raw = os.environ.get("SESSION_ID")
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            print(f"⚠️  SESSION_ID={raw!r} is not a valid integer; ignoring.")

    stmt = (
        select(StudySession)
        .order_by(StudySession.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    return session.id if session else None


async def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    log.info("demo_load_started")

    async with get_session() as db:
        session_id = await _resolve_session_id(db)
        if session_id is None:
            print("❌ No sessions found. Run demo_setup.py first.")
            return

        session = await session_service.get_with_relations(db, session_id)
        if session is None:
            print(
                f"❌ Session {session_id} not found. "
                f"Run demo_setup.py first."
            )
            return

        profile = await profile_service.get_by_session_as_pydantic(
            db, session_id
        )
        roadmap = await roadmap_service.get_with_tree_as_pydantic(
            db, session_id
        )
        progress = await progress_service.get_by_session(db, session_id)

    # ============================================================
    # Print everything
    # ============================================================
    print("\n" + "=" * 78)
    print(f"📚 SESSION #{session_id}: {session.title!r}")
    print("=" * 78)
    print(f"   Topic:    {session.topic!r}")
    print(f"   Status:   {session.status!r}")
    print(f"   Created:  {session.created_at}")

    # Profile
    if profile:
        print(f"\n📋 PROFILE")
        print(f"   Topic:          {profile.topic!r}")
        print(f"   Level:          {profile.level.value!r}")
        print(f"   Goal:           {profile.goal.value!r}")
        print(f"   Role:           {profile.role!r}")
        print(f"   Learning style: {profile.learning_style.value!r}")
        print(f"   Focus:          {profile.focus!r}")
        print(f"   Language:       {profile.language!r}")

    # Roadmap
    if roadmap:
        print(f"\n🗺️  ROADMAP: {roadmap.title!r}")
        print(f"   Summary:  {roadmap.summary[:120]}...")
        print(f"   Modules:  {roadmap.total_modules}")
        print(f"   Hours:    {roadmap.estimated_hours}")
        print(f"   Prereqs:  {roadmap.prerequisites}")
        print(f"   Outcomes: {len(roadmap.learning_outcomes)}")

        for module in roadmap.modules:
            print(f"\n   [{module.id}] {module.title}")
            for part in module.parts:
                code_marker = "💻" if part.requires_code else "📖"
                print(
                    f"      {code_marker} [{part.id}] {part.title} "
                    f"(difficulty={part.difficulty})"
                )

    # Lessons
    async with get_session() as db:
        print(f"\n📖 LESSONS")
        total_lessons = 0
        for module in roadmap.modules if roadmap else []:
            for part in module.parts:
                lesson = await lesson_service.get_by_part_id_as_pydantic(
                    db, part.id, session_id=session_id
                )
                if lesson:
                    total_lessons += 1
                    print(
                        f"   ✅ [{part.id}] {len(lesson.content)} chars, "
                        f"part_title={lesson.metadata.part_title!r}"
                    )
                else:
                    print(f"   ❌ [{part.id}] missing")
        print(f"\n   Total lessons: {total_lessons}")

    # Progress
    if progress:
        print(f"\n📊 PROGRESS")
        print(f"   Current position:  module {progress.current_module_index} / "
              f"part {progress.current_part_index}")
        print(f"   Completed parts:   {progress.completed_parts}")
        print(f"   Total parts:       {progress.total_parts}")
        print(f"   Percentage:        {progress.percentage}%")

    print("\n" + "=" * 78)
    print("✅ Load complete")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
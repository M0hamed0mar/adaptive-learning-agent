"""
End-to-end persistence demo — Verify phase.

Verifies that a session's data persisted correctly.

The session ID is read from the `SESSION_ID` environment variable.
If not set, the most recent session is used.

Run:
    SESSION_ID=3 python scripts/demo_verify.py
    # or
    python scripts/demo_verify.py
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
    log.info("demo_verify_started")

    errors: list[str] = []
    parts_expected = 0

    async with get_session() as db:
        session_id = await _resolve_session_id(db)
        if session_id is None:
            print("❌ No sessions found. Run demo_setup.py first.")
            sys.exit(1)

        print(f"🔎 Verifying session #{session_id}\n")

        # 1. Session exists
        session = await session_service.get_with_relations(db, session_id)
        if session is None:
            errors.append(f"Session {session_id} not found")
            _report(errors)
            return
        print(f"✅ Session exists: {session.title!r}")

        # 2. Profile exists
        profile = await profile_service.get_by_session_as_pydantic(
            db, session_id
        )
        if profile is None:
            errors.append("Profile missing")
        else:
            print(
                f"✅ Profile: topic={profile.topic!r} "
                f"level={profile.level.value!r}"
            )
            if profile.role != "AI Engineer":
                errors.append(f"Profile role mismatch: {profile.role!r}")

        # 3. Roadmap exists with correct structure
        roadmap = await roadmap_service.get_with_tree_as_pydantic(
            db, session_id
        )
        if roadmap is None:
            errors.append("Roadmap missing")
        else:
            print(
                f"✅ Roadmap: {roadmap.title!r} "
                f"({roadmap.total_modules} modules)"
            )
            if len(roadmap.modules) != roadmap.total_modules:
                errors.append(
                    f"Roadmap total_modules mismatch: "
                    f"{roadmap.total_modules} != {len(roadmap.modules)}"
                )
            for m in roadmap.modules:
                if len(m.parts) < 2:
                    errors.append(f"Module {m.id} has < 2 parts")

        # 4. Every part has a lesson
        if roadmap:
            lessons_found = 0
            for m in roadmap.modules:
                for p in m.parts:
                    parts_expected += 1
                    lesson = await lesson_service.get_by_part_id_as_pydantic(
                        db, p.id, session_id=session_id
                    )
                    if lesson:
                        lessons_found += 1
                    else:
                        errors.append(f"Missing lesson for {p.id}")
            print(f"✅ Lessons: {lessons_found}/{parts_expected}")

        # 5. Progress exists and has correct shape
        progress = await progress_service.get_by_session(db, session_id)
        if progress is None:
            errors.append("Progress missing")
        else:
            print(
                f"✅ Progress: {progress.percentage}% "
                f"({len(progress.completed_parts)}/{progress.total_parts})"
            )
            if progress.total_parts != parts_expected:
                errors.append(
                    f"Progress total_parts mismatch: "
                    f"{progress.total_parts} != {parts_expected}"
                )
            if len(progress.completed_parts) < 1:
                errors.append("Progress has no completed parts")

    _report(errors)


def _report(errors: list[str]) -> None:
    print("\n" + "=" * 78)
    if errors:
        print(f"❌ VERIFICATION FAILED ({len(errors)} error(s))")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("🎉 VERIFICATION PASSED — everything persisted correctly!")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
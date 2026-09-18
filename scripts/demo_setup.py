"""
End-to-end persistence demo — Setup phase.

Builds a complete learning session from scratch:
    1. Creates a user and a study session.
    2. Generates a UserProfile (via ProfileAgent).
    3. Generates a Roadmap (via RoadmapWorkflow).
    4. Generates Teaching Prompts (via TeachingPromptWorkflow).
    5. Generates Lessons (via TutorAgent).
    6. Creates a Progress record.
    7. Marks the first part as completed.

Everything is persisted to the database.

The session ID is printed at the end so downstream demos
(`demo_load.py`, `demo_verify.py`) can target the right session.

Run:
    python scripts/demo_setup.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the project root is on sys.path when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import structlog  # noqa: E402

from app.agents.profile.agent import profile_agent  # noqa: E402
from app.agents.prompt.workflow import teaching_prompt_workflow  # noqa: E402
from app.agents.roadmap.workflow import roadmap_workflow  # noqa: E402
from app.agents.tutor.agent import tutor_agent  # noqa: E402
from app.config.constants import LearningGoal, LearningStyle, UserLevel  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.database import get_session  # noqa: E402
from app.services import (  # noqa: E402
    lesson_service,
    profile_service,
    progress_service,
    roadmap_service,
    session_service,
    user_service,
)

logger = structlog.get_logger(__name__)


async def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    log.info("demo_setup_started")

    # ============================================================
    # 1. User + Session
    # ============================================================
    async with get_session() as db:
        user = await user_service.get_or_create_default(db)
        session = await session_service.create(
            db,
            user_id=user.id,
            topic="Docker",
            title="Docker for AI Engineers",
        )
        session_id = session.id
        user_id = user.id
        print(f"✅ Session created: id={session_id}")

    # ============================================================
    # 2. Profile (Phase 1)
    # ============================================================
    profile_pydantic = await profile_agent.build_profile(
        topic="Docker",
        raw_input="Docker for AI Engineers",
        answers={
            "level": UserLevel.BEGINNER.value,
            "goal": LearningGoal.BUILD_PROJECTS.value,
            "role": "AI Engineer",
            "learning_style": LearningStyle.PRACTICAL.value,
            "focus": "Dockerizing FastAPI applications",
        },
    )
    print(f"✅ Profile generated: topic={profile_pydantic.topic!r}")

    async with get_session() as db:
        await profile_service.create_from_pydantic(
            db, session_id=session_id, profile=profile_pydantic
        )
        print(f"✅ Profile persisted")

    # ============================================================
    # 3. Roadmap (Phase 2)
    # ============================================================
    print("\n⏳ Generating roadmap (this takes 30-60s)...")
    roadmap_result = await roadmap_workflow.run(profile_pydantic)
    roadmap_pydantic = roadmap_result.roadmap
    print(
        f"✅ Roadmap generated: title={roadmap_pydantic.title!r} "
        f"modules={roadmap_pydantic.total_modules} "
        f"score={roadmap_result.final_critique.score}"
    )

    async with get_session() as db:
        await roadmap_service.create_from_pydantic(
            db, session_id=session_id, roadmap=roadmap_pydantic
        )
        print(f"✅ Roadmap persisted")

        # Update session title with the generated title
        session_orm = await session_service.get(db, session_id)
        if session_orm:
            await session_service.update_title(db, session_orm, roadmap_pydantic.title)

    # ============================================================
    # 4. Teaching Prompts + Lessons (Phases 3 + 4)
    # ============================================================
    total_parts = sum(len(m.parts) for m in roadmap_pydantic.modules)
    print(f"\n⏳ Generating {total_parts} teaching prompts + lessons...")

    completed_parts_count = 0
    for module in roadmap_pydantic.modules:
        for part in module.parts:
            print(f"\n   → [{part.id}] {part.title}")

            # Teaching prompt (Phase 3)
            tp_result = await teaching_prompt_workflow.run(
                profile=profile_pydantic,
                module=module,
                part=part,
            )
            print(
                f"      ✅ Teaching prompt ready "
                f"(score={tp_result.final_critique.score})"
            )

            # Lesson (Phase 4)
            lesson = await tutor_agent.teach(
                profile=profile_pydantic,
                module=module,
                part=part,
                teaching_prompt=tp_result.teaching_prompt,
            )
            print(f"      ✅ Lesson generated ({len(lesson.content)} chars)")

            # Persist lesson
            async with get_session() as db:
                part_orm = await roadmap_service.get_part_by_part_id(
                    db, part.id, session_id=session_id
                )
                if part_orm is None:
                    raise RuntimeError(
                        f"Part {part.id!r} not found in DB "
                        f"for session {session_id}"
                    )

                await lesson_service.create_from_pydantic(
                    db,
                    roadmap_part_id=part_orm.id,
                    lesson=lesson,
                )

                # After the first lesson, create progress and mark the
                # first part as completed (to have a non-trivial state).
                if completed_parts_count == 0:
                    total_modules, parts_per_module = (
                        await progress_service.get_roadmap_shape(
                            db, session_id=session_id
                        )
                    )
                    progress = await progress_service.create_for_session(
                        db,
                        session_id=session_id,
                        total_parts=sum(parts_per_module),
                    )
                    await progress_service.mark_part_completed(
                        db, progress, part_id=part.id
                    )
                    completed_parts_count += 1

            print(f"      ✅ Lesson persisted")

    # ============================================================
    # Summary
    # ============================================================
    async with get_session() as db:
        session_full = await session_service.get_with_relations(db, session_id)
        progress = await progress_service.get_by_session(db, session_id)

    print("\n" + "=" * 70)
    print("📊 SETUP COMPLETE")
    print("=" * 70)
    print(f"   User ID:              {user_id}")
    print(f"   Session ID:           {session_id}")
    print(f"   Session topic:        {session_full.topic!r}")
    print(f"   Session title:        {session_full.title!r}")
    print(f"   Session status:       {session_full.status!r}")
    print(f"   Profile topic:        {session_full.profile.topic!r}")
    print(f"   Roadmap title:        {session_full.roadmap.title!r}")
    print(f"   Roadmap modules:      {session_full.roadmap.total_modules}")
    if progress:
        print(f"   Progress:             {progress.percentage}% "
              f"({len(progress.completed_parts)}/{progress.total_parts})")
    print()
    print(f"👉 Now run: SESSION_ID={session_id} python scripts/demo_load.py")
    print(f"           SESSION_ID={session_id} python scripts/demo_verify.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())
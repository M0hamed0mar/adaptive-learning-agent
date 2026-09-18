"""
Lesson service (Phase 11 redesign).

Lessons are now generated LAZILY. This service supports:
    - Creating a lesson placeholder (no content yet).
    - Updating a lesson's content (when the LLM returns).
    - Reading lessons (with optional lazy-load info).
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson import Lesson as LessonORM
from app.models.roadmap import Roadmap, RoadmapModule, RoadmapPart
from app.schemas.lesson import Lesson, LessonMetadata
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class LessonService(BaseService[LessonORM]):
    """CRUD for `Lesson` plus Pydantic↔ORM conversion."""

    model = LessonORM

    # --------------------------------------------------------
    # Create / attach
    # --------------------------------------------------------

    async def create_from_pydantic(
        self,
        db: AsyncSession,
        *,
        roadmap_part_id: int,
        lesson: Lesson,
    ) -> LessonORM:
        """Persist a Pydantic `Lesson` for a given roadmap part."""
        log = logger.bind(
            service="LessonService",
            method="create_from_pydantic",
            roadmap_part_id=roadmap_part_id,
            content_length=len(lesson.content),
        )
        orm = LessonORM(
            roadmap_part_id=roadmap_part_id,
            content=lesson.content,
            lesson_metadata=lesson.metadata.model_dump(),
        )
        db.add(orm)
        result = await self._flush_and_refresh(db, orm)
        log.info("lesson_created", lesson_id=result.id)
        return result

    async def create_placeholder(
        self,
        db: AsyncSession,
        *,
        roadmap_part_id: int,
    ) -> LessonORM:
        """Create an empty lesson row (content=None) for lazy generation."""
        orm = LessonORM(
            roadmap_part_id=roadmap_part_id,
            content=None,
            lesson_metadata=None,
        )
        db.add(orm)
        return await self._flush_and_refresh(db, orm)

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------

    async def get_by_part_id(
        self,
        db: AsyncSession,
        part_id: str,
        *,
        session_id: int,
    ) -> LessonORM | None:
        """Return the lesson for a semantic part ID, scoped by session."""
        stmt = (
            select(LessonORM)
            .join(RoadmapPart, LessonORM.roadmap_part_id == RoadmapPart.id)
            .join(RoadmapModule, RoadmapPart.module_id == RoadmapModule.id)
            .join(Roadmap, RoadmapModule.roadmap_id == Roadmap.id)
            .where(
                RoadmapPart.part_id == part_id,
                Roadmap.session_id == session_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_part_id_as_pydantic(
        self,
        db: AsyncSession,
        part_id: str,
        *,
        session_id: int,
    ) -> Lesson | None:
        """
        Return the lesson as Pydantic, or None if:
            - the row doesn't exist, OR
            - the row exists but content is None (not yet generated).
        """
        orm = await self.get_by_part_id(db, part_id, session_id=session_id)
        if orm is None or not orm.content:
            return None
        return self.to_pydantic(orm)

    async def get_by_roadmap_part_pk(
        self,
        db: AsyncSession,
        roadmap_part_pk: int,
    ) -> LessonORM | None:
        stmt = select(LessonORM).where(
            LessonORM.roadmap_part_id == roadmap_part_pk
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_roadmap(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> list[LessonORM]:
        stmt = (
            select(LessonORM)
            .join(RoadmapPart, LessonORM.roadmap_part_id == RoadmapPart.id)
            .join(RoadmapModule, RoadmapPart.module_id == RoadmapModule.id)
            .join(Roadmap, RoadmapModule.roadmap_id == Roadmap.id)
            .where(Roadmap.session_id == session_id)
            .order_by(
                RoadmapModule.order_index,
                RoadmapPart.order_index,
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_for_session_as_pydantic(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> list[Lesson]:
        orms = await self.list_for_roadmap(db, session_id)
        return [self.to_pydantic(orm) for orm in orms if orm.content]

    # --------------------------------------------------------
    # Update
    # --------------------------------------------------------

    async def replace_content(
        self,
        db: AsyncSession,
        orm: LessonORM,
        lesson: Lesson,
    ) -> LessonORM:
        orm.content = lesson.content
        orm.lesson_metadata = lesson.metadata.model_dump()
        return await self._flush_and_refresh(db, orm)

    # --------------------------------------------------------
    # Conversion
    # --------------------------------------------------------

    def to_pydantic(self, orm: LessonORM) -> Lesson:
        if not orm.content or not orm.lesson_metadata:
            raise ValueError("Cannot convert an empty lesson to Pydantic.")
        metadata = LessonMetadata(**orm.lesson_metadata)
        return Lesson(content=orm.content, metadata=metadata)


# ============================================================
# Singleton
# ============================================================

lesson_service = LessonService()


__all__ = ["LessonService", "lesson_service"]

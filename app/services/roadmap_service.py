"""
Roadmap service (Phase 11 redesign).

Handles the roadmap tree with the new simplified schema:
    - Roadmap        → title + summary + totals
    - RoadmapModule  → title only
    - RoadmapPart    → title + optional teaching_prompt

Semantic part IDs (e.g. "M1-P1") are NOT globally unique; every
lookup by semantic `part_id` MUST be scoped by `session_id`.
"""

from __future__ import annotations

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.roadmap import Roadmap, RoadmapModule, RoadmapPart
from app.schemas.roadmap import (
    ModuleTitle,
    PartTitle,
    RoadmapTitles,
)
from app.schemas.teaching import TeachingPromptSet
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class RoadmapService(BaseService[Roadmap]):
    """CRUD for the roadmap tree with Pydantic conversion."""

    model = Roadmap

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    async def create_from_titles(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        roadmap: RoadmapTitles,
    ) -> Roadmap:
        """
        Persist a `RoadmapTitles` skeleton.

        Creates the full tree (modules + parts) with no teaching prompts
        yet. Prompts are attached later via `attach_prompts`.
        """
        log = logger.bind(
            service="RoadmapService",
            method="create_from_titles",
            session_id=session_id,
            title=roadmap.title,
            total_modules=roadmap.total_modules,
        )

        orm_roadmap = Roadmap(
            session_id=session_id,
            title=roadmap.title,
            summary=roadmap.summary,
            total_modules=roadmap.total_modules,
            estimated_hours=roadmap.estimated_hours,
        )
        db.add(orm_roadmap)
        await db.flush()

        for m_idx, module in enumerate(roadmap.modules, start=1):
            orm_module = RoadmapModule(
                roadmap_id=orm_roadmap.id,
                module_id=f"M{m_idx}",
                title=module.title,
                order_index=m_idx,
            )
            db.add(orm_module)
            await db.flush()

            for p_idx, part in enumerate(module.parts, start=1):
                orm_part = RoadmapPart(
                    module_id=orm_module.id,
                    part_id=f"M{m_idx}-P{p_idx}",
                    title=part.title,
                    order_index=p_idx,
                    teaching_prompt=None,
                )
                db.add(orm_part)

        await db.flush()
        await db.refresh(orm_roadmap)

        log.info(
            "roadmap_created",
            roadmap_id=orm_roadmap.id,
            module_count=len(roadmap.modules),
        )
        return orm_roadmap

    # --------------------------------------------------------
    # Attach prompts
    # --------------------------------------------------------

    async def attach_prompts(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        prompt_set: TeachingPromptSet,
    ) -> int:
        """
        Attach teaching prompts to the roadmap's parts.

        Matches parts by semantic `part_id` scoped to the session.
        Returns the number of prompts attached.
        """
        log = logger.bind(
            service="RoadmapService",
            method="attach_prompts",
            session_id=session_id,
            prompt_count=len(prompt_set.prompts),
        )

        attached = 0
        for item in prompt_set.prompts:
            part = await self.get_part_by_part_id(
                db, item.part_id, session_id=session_id
            )
            if part is None:
                log.warning(
                    "attach_prompts_part_not_found",
                    part_id=item.part_id,
                )
                continue
            part.teaching_prompt = item.prompt
            attached += 1

        await db.flush()
        log.info("prompts_attached", attached=attached)
        return attached

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------

    async def get_by_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> Roadmap | None:
        """Return the roadmap for a session, WITHOUT eager loading."""
        stmt = select(Roadmap).where(Roadmap.session_id == session_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_tree(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> Roadmap | None:
        """Return the roadmap with modules and parts eagerly loaded."""
        stmt = (
            select(Roadmap)
            .where(Roadmap.session_id == session_id)
            .options(
                selectinload(Roadmap.modules).selectinload(RoadmapModule.parts)
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_tree_as_pydantic(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> RoadmapTitles | None:
        """Return the roadmap as a `RoadmapTitles` (titles only)."""
        orm = await self.get_with_tree(db, session_id)
        if orm is None:
            return None
        return self.to_titles_pydantic(orm)

    # --------------------------------------------------------
    # Update
    # --------------------------------------------------------

    async def replace_from_titles(
        self,
        db: AsyncSession,
        orm: Roadmap,
        roadmap: RoadmapTitles,
    ) -> Roadmap:
        """
        Replace an existing roadmap with a new skeleton.

        Deletes all modules (cascade removes parts + lessons) and
        rebuilds them. Any previously attached prompts are LOST.
        """
        log = logger.bind(
            service="RoadmapService",
            method="replace_from_titles",
            roadmap_id=orm.id,
        )

        orm.title = roadmap.title
        orm.summary = roadmap.summary
        orm.total_modules = roadmap.total_modules
        orm.estimated_hours = roadmap.estimated_hours

        await db.execute(
            delete(RoadmapModule).where(RoadmapModule.roadmap_id == orm.id)
        )
        await db.flush()

        for m_idx, module in enumerate(roadmap.modules, start=1):
            orm_module = RoadmapModule(
                roadmap_id=orm.id,
                module_id=f"M{m_idx}",
                title=module.title,
                order_index=m_idx,
            )
            db.add(orm_module)
            await db.flush()

            for p_idx, part in enumerate(module.parts, start=1):
                orm_part = RoadmapPart(
                    module_id=orm_module.id,
                    part_id=f"M{m_idx}-P{p_idx}",
                    title=part.title,
                    order_index=p_idx,
                    teaching_prompt=None,
                )
                db.add(orm_part)

        await db.flush()
        await db.refresh(orm)

        log.info("roadmap_replaced")
        return orm

    # --------------------------------------------------------
    # Part-level lookups
    # --------------------------------------------------------

    async def get_part_by_part_id(
        self,
        db: AsyncSession,
        part_id: str,
        *,
        session_id: int,
    ) -> RoadmapPart | None:
        """
        Return a part by its semantic ID, scoped to a session.

        Semantic part IDs are NOT globally unique — every roadmap
        has its own "M1-P1".
        """
        stmt = (
            select(RoadmapPart)
            .join(RoadmapModule, RoadmapPart.module_id == RoadmapModule.id)
            .join(Roadmap, RoadmapModule.roadmap_id == Roadmap.id)
            .where(
                RoadmapPart.part_id == part_id,
                Roadmap.session_id == session_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_part_by_pk(
        self,
        db: AsyncSession,
        part_pk: int,
    ) -> RoadmapPart | None:
        """Return a part by its primary key."""
        return await db.get(RoadmapPart, part_pk)

    # --------------------------------------------------------
    # Conversion
    # --------------------------------------------------------

    def to_titles_pydantic(self, orm: Roadmap) -> RoadmapTitles:
        """Convert an ORM Roadmap (with tree loaded) to `RoadmapTitles`."""
        modules = [
            ModuleTitle(
                title=m.title,
                parts=[PartTitle(title=p.title) for p in m.parts],
            )
            for m in orm.modules
        ]
        return RoadmapTitles(
            title=orm.title,
            summary=orm.summary,
            total_modules=orm.total_modules,
            estimated_hours=orm.estimated_hours,
            modules=modules,
        )


# ============================================================
# Singleton
# ============================================================

roadmap_service = RoadmapService()


__all__ = ["RoadmapService", "roadmap_service"]

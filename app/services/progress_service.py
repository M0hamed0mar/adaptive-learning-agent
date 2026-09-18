"""
Progress service.

Tracks a learner's position and completion state within a study
session. Contains the business logic for:
    - creating progress for a new session,
    - marking parts as completed,
    - advancing to the next part,
    - recomputing the completion percentage.
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress import Progress
from app.models.roadmap import RoadmapModule, RoadmapPart
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class ProgressService(BaseService[Progress]):
    """CRUD + business logic for `Progress`."""

    model = Progress

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    async def create_for_session(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        total_parts: int,
    ) -> Progress:
        """Create a fresh progress record for a session."""
        log = logger.bind(
            service="ProgressService",
            method="create_for_session",
            session_id=session_id,
            total_parts=total_parts,
        )

        progress = Progress(
            session_id=session_id,
            current_module_index=0,
            current_part_index=0,
            completed_parts=[],
            total_parts=total_parts,
            percentage=0.0,
        )
        db.add(progress)
        result = await self._flush_and_refresh(db, progress)

        log.info("progress_created", progress_id=result.id)
        return result

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------

    async def get_by_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> Progress | None:
        """Return the progress for a given session, if any."""
        stmt = select(Progress).where(Progress.session_id == session_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # --------------------------------------------------------
    # Business logic
    # --------------------------------------------------------

    async def mark_part_completed(
        self,
        db: AsyncSession,
        progress: Progress,
        *,
        part_id: str,
    ) -> Progress:
        """
        Mark a part as completed.

        Idempotent: re-marking the same part is a no-op. Recomputes
        the percentage after updating.
        """
        log = logger.bind(
            service="ProgressService",
            method="mark_part_completed",
            progress_id=progress.id,
            part_id=part_id,
        )

        completed = list(progress.completed_parts or [])

        if part_id in completed:
            log.debug("part_already_completed")
            return progress

        completed.append(part_id)
        progress.completed_parts = completed
        self._recompute_percentage(progress)

        result = await self._flush_and_refresh(db, progress)
        log.info(
            "part_marked_completed",
            completed_count=len(completed),
            percentage=float(result.percentage),
        )
        return result

    async def advance_to_next_part(
        self,
        db: AsyncSession,
        progress: Progress,
        *,
        total_modules: int,
        parts_per_module: list[int],
    ) -> Progress:
        """
        Advance the "current position" pointer to the next part.

        The caller supplies the roadmap shape:
            - `total_modules`: number of modules in the roadmap.
            - `parts_per_module`: list of part counts, one per module.

        This method is pure: it does NOT verify the curriculum; it
        just moves the pointer forward (wrapping at the end).
        """
        log = logger.bind(
            service="ProgressService",
            method="advance_to_next_part",
            progress_id=progress.id,
            current_module=progress.current_module_index,
            current_part=progress.current_part_index,
        )

        m = progress.current_module_index
        p = progress.current_part_index

        # Advance within the current module.
        if p + 1 < parts_per_module[m]:
            p += 1
        else:
            # Move to the next module.
            if m + 1 < total_modules:
                m += 1
                p = 0
            # Else: we're at the very last part — do nothing.

        progress.current_module_index = m
        progress.current_part_index = p

        result = await self._flush_and_refresh(db, progress)
        log.info("progress_advanced", new_module=m, new_part=p)
        return result

    async def sync_total_parts(
        self,
        db: AsyncSession,
        progress: Progress,
        *,
        total_parts: int,
    ) -> Progress:
        """
        Update `total_parts` (e.g. after a roadmap is refined and its
        part count changes). Also recomputes the percentage.
        """
        progress.total_parts = total_parts
        self._recompute_percentage(progress)
        return await self._flush_and_refresh(db, progress)

    # --------------------------------------------------------
    # Shape helper
    # --------------------------------------------------------

    async def get_roadmap_shape(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> tuple[int, list[int]]:
        """
        Return (total_modules, parts_per_module) for the roadmap
        associated with the given session.

        Uses a single aggregated SQL query to avoid loading the
        parts themselves.
        """
        stmt = (
            select(
                RoadmapModule.id,
                func.count(RoadmapPart.id).label("part_count"),
            )
            .join(RoadmapModule.roadmap)
            .outerjoin(
                RoadmapPart,
                RoadmapPart.module_id == RoadmapModule.id,
            )
            .where(RoadmapModule.roadmap.has(session_id=session_id))
            .group_by(RoadmapModule.id)
            .order_by(RoadmapModule.order_index)
        )
        result = await db.execute(stmt)
        rows = result.all()

        parts_per_module = [int(count) for _module_id, count in rows]
        return len(parts_per_module), parts_per_module

    # --------------------------------------------------------
    # Internal
    # --------------------------------------------------------

    def _recompute_percentage(self, progress: Progress) -> None:
        """Recompute the completion percentage from `completed_parts`."""
        total = progress.total_parts or 0
        if total <= 0:
            progress.percentage = 0.0
            return

        completed = len(progress.completed_parts or [])
        pct = round((completed / total) * 100.0, 2)
        progress.percentage = min(pct, 100.0)


# ============================================================
# Singleton
# ============================================================

progress_service = ProgressService()


__all__ = ["ProgressService", "progress_service"]
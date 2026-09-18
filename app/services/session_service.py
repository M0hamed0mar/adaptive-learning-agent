"""
StudySession service.

Manages study sessions — the top-level container for a learning journey.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.constants import SessionStatus
from app.models.session import StudySession
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class SessionService(BaseService[StudySession]):
    """CRUD for `StudySession`."""

    model = StudySession

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        topic: str,
        title: str | None = None,
        status: SessionStatus = SessionStatus.DRAFT,
    ) -> StudySession:
        """Create a new study session."""
        log = logger.bind(
            service="SessionService",
            method="create",
            user_id=user_id,
            topic=topic,
        )

        session = StudySession(
            user_id=user_id,
            topic=topic,
            title=title,
            status=status.value,
        )
        db.add(session)
        result = await self._flush_and_refresh(db, session)

        log.info("session_created", session_id=result.id)
        return result

    async def get_with_relations(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> StudySession | None:
        """
        Return a session with profile, roadmap, progress, and messages
        eagerly loaded (via selectinload).

        Use this when you need the full session tree.
        """
        stmt = (
            select(StudySession)
            .where(StudySession.id == session_id)
            .options(
                selectinload(StudySession.profile),
                selectinload(StudySession.roadmap),
                selectinload(StudySession.progress),
                selectinload(StudySession.messages),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[StudySession]:
        """Return all sessions for a user, newest first."""
        stmt = (
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .order_by(StudySession.created_at.desc())
        )
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        db: AsyncSession,
        session: StudySession,
        status: SessionStatus,
    ) -> StudySession:
        """Update a session's status."""
        session.status = status.value
        await db.flush()
        await db.refresh(session)
        return session

    async def update_title(
        self,
        db: AsyncSession,
        session: StudySession,
        title: str,
    ) -> StudySession:
        """Update a session's title."""
        session.title = title
        await db.flush()
        await db.refresh(session)
        return session


# ============================================================
# Singleton
# ============================================================

session_service = SessionService()


__all__ = ["SessionService", "session_service"]
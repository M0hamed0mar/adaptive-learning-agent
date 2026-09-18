"""
Message service.

CRUD for chat messages, plus Pydantic conversion.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message as MessageORM
from app.schemas.message import Message, MessageRole
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class MessageService(BaseService[MessageORM]):
    """CRUD for `Message`."""

    model = MessageORM

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    async def create(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        role: MessageRole,
        content: str,
        roadmap_part_id: int | None = None,
    ) -> MessageORM:
        """Create a new message."""
        orm = MessageORM(
            session_id=session_id,
            roadmap_part_id=roadmap_part_id,
            role=role,
            content=content,
        )
        db.add(orm)
        return await self._flush_and_refresh(db, orm)

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------

    async def list_for_lesson(
        self,
        db: AsyncSession,
        session_id: int,
        *,
        roadmap_part_id: int,
    ) -> list[MessageORM]:
        """Return all messages for a specific lesson, ordered by time."""
        stmt = (
            select(MessageORM)
            .where(
                MessageORM.session_id == session_id,
                MessageORM.roadmap_part_id == roadmap_part_id,
            )
            .order_by(MessageORM.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_for_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> list[MessageORM]:
        """Return all messages for a session."""
        stmt = (
            select(MessageORM)
            .where(MessageORM.session_id == session_id)
            .order_by(MessageORM.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # --------------------------------------------------------
    # Conversion
    # --------------------------------------------------------

    def to_pydantic(self, orm: MessageORM) -> Message:
        return Message.model_validate(orm, from_attributes=True)


# ============================================================
# Singleton
# ============================================================

message_service = MessageService()


__all__ = ["MessageService", "message_service"]

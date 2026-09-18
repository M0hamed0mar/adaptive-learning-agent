"""
LearningProfile service (Phase 11 redesign).

Changes:
    - `focus` field removed from the schema.
    - `language` field added (default 'ar').
    - `to_pydantic` reflects the new shape.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import (
    LearningGoal,
    LearningStyle,
    UserLevel,
)
from app.models.profile import LearningProfile
from app.schemas.profile import UserProfile
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class ProfileService(BaseService[LearningProfile]):
    """CRUD for `LearningProfile` plus Pydantic↔ORM conversion."""

    model = LearningProfile

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    async def create_from_pydantic(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        profile: UserProfile,
    ) -> LearningProfile:
        """Persist a Pydantic `UserProfile` for a session."""
        log = logger.bind(
            service="ProfileService",
            method="create_from_pydantic",
            session_id=session_id,
            topic=profile.topic,
        )

        orm = LearningProfile(
            session_id=session_id,
            topic=profile.topic,
            level=profile.level.value,
            goal=profile.goal.value,
            role=profile.role,
            learning_style=profile.learning_style.value,
            raw_input=profile.raw_input,
            language=profile.language,
        )
        db.add(orm)
        result = await self._flush_and_refresh(db, orm)
        log.info("profile_created", profile_id=result.id)
        return result

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------

    async def get_by_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> LearningProfile | None:
        stmt = select(LearningProfile).where(
            LearningProfile.session_id == session_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_session_as_pydantic(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> UserProfile | None:
        orm = await self.get_by_session(db, session_id)
        if orm is None:
            return None
        return self.to_pydantic(orm)

    # --------------------------------------------------------
    # Update
    # --------------------------------------------------------

    async def update_from_pydantic(
        self,
        db: AsyncSession,
        orm: LearningProfile,
        profile: UserProfile,
    ) -> LearningProfile:
        orm.topic = profile.topic
        orm.level = profile.level.value
        orm.goal = profile.goal.value
        orm.role = profile.role
        orm.learning_style = profile.learning_style.value
        orm.raw_input = profile.raw_input
        orm.language = profile.language
        return await self._flush_and_refresh(db, orm)

    # --------------------------------------------------------
    # Conversion
    # --------------------------------------------------------

    def to_pydantic(self, orm: LearningProfile) -> UserProfile:
        return UserProfile(
            topic=orm.topic,
            level=UserLevel(orm.level),
            goal=LearningGoal(orm.goal),
            role=orm.role,
            learning_style=LearningStyle(orm.learning_style),
            raw_input=orm.raw_input,
            language=orm.language,
        )


# ============================================================
# Singleton
# ============================================================

profile_service = ProfileService()


__all__ = ["ProfileService", "profile_service"]

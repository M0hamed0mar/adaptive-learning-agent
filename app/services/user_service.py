"""
User service.

Manages users. In the MVP there is a single default user, but the API
supports multi-user later without schema changes.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class UserService(BaseService[User]):
    """CRUD for `User`."""

    model = User

    async def get_or_create_default(
        self,
        db: AsyncSession,
    ) -> User:
        """
        Return the default user, creating it if it does not exist.

        The default user has `external_id=None`. In future versions this
        method will be replaced by real authentication.
        """
        log = logger.bind(service="UserService", method="get_or_create_default")

        stmt = select(User).where(User.external_id.is_(None)).limit(1)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            log.debug("default_user_found", user_id=user.id)
            return user

        log.info("default_user_created")
        user = User(external_id=None)
        db.add(user)
        return await self._flush_and_refresh(db, user)

    async def get_by_external_id(
        self,
        db: AsyncSession,
        external_id: str,
    ) -> User | None:
        """Return the user with the given external id, if any."""
        stmt = select(User).where(User.external_id == external_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        external_id: str | None = None,
    ) -> User:
        """Create a new user."""
        user = User(external_id=external_id)
        db.add(user)
        return await self._flush_and_refresh(db, user)


# ============================================================
# Singleton
# ============================================================

user_service = UserService()


__all__ = ["UserService", "user_service"]
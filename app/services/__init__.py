"""
Services package.

Exposes service singletons. Each service provides high-level CRUD
operations on a given AsyncSession.
"""

from app.services.base import BaseService
from app.services.lesson_service import LessonService, lesson_service
from app.services.message_service import MessageService, message_service
from app.services.profile_service import ProfileService, profile_service
from app.services.progress_service import ProgressService, progress_service
from app.services.roadmap_service import RoadmapService, roadmap_service
from app.services.session_service import SessionService, session_service
from app.services.user_service import UserService, user_service

__all__ = [
    "BaseService",
    "UserService",
    "user_service",
    "SessionService",
    "session_service",
    "ProfileService",
    "profile_service",
    "RoadmapService",
    "roadmap_service",
    "LessonService",
    "lesson_service",
    "ProgressService",
    "progress_service",
    "MessageService",
    "message_service",
]

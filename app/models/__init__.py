"""
ORM models package.

Importing all models here ensures that:
    - SQLAlchemy's registry sees them all.
    - Alembic can autogenerate migrations from a single import.
"""

from app.models.base import Base, TimestampMixin, utcnow
from app.models.lesson import Lesson
from app.models.message import Message
from app.models.profile import LearningProfile
from app.models.progress import Progress
from app.models.roadmap import Roadmap, RoadmapModule, RoadmapPart
from app.models.session import StudySession
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "utcnow",
    # Core
    "User",
    "StudySession",
    "LearningProfile",
    # Content
    "Roadmap",
    "RoadmapModule",
    "RoadmapPart",
    "Lesson",
    "Message",
    "Progress",
]
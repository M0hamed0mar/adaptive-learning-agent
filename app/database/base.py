"""
Database base re-export.

The actual `Base` and mixins live in `app.models.base`. This module
exists so that Alembic and other tooling can import them from a
canonical location without knowing the models package layout.
"""

from app.models.base import Base, TimestampMixin, utcnow

__all__ = ["Base", "TimestampMixin", "utcnow"]
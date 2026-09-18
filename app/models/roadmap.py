"""
Roadmap ORM models (Phase 11 redesign).

New design:
    - `Roadmap`  → root, holds title + summary + hours.
    - `RoadmapModule` → module title.
    - `RoadmapPart` → part title + optional lesson link.

What was removed:
    - `objective`, `difficulty`, `requires_code`, `teaching_plan`
      (they are now optional and live inside the prompt / lesson).
    - The `learning_outcomes` and `prerequisites` JSON columns on
      the root (they are inferred from raw_input on the fly, if ever
      needed).

What was kept:
    - `module_id` (e.g. "M1") and `part_id` (e.g. "M1-P1") as
      semantic identifiers (unique per roadmap).
    - `order_index` for stable ordering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.lesson import Lesson
    from app.models.session import StudySession


# ============================================================
# Roadmap
# ============================================================

class Roadmap(Base, TimestampMixin):
    """A generated learning roadmap for one study session."""

    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    total_modules: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_hours: Mapped[float] = mapped_column(nullable=False)

    # Relationships
    session: Mapped["StudySession"] = relationship(back_populates="roadmap")

    modules: Mapped[list["RoadmapModule"]] = relationship(
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="RoadmapModule.order_index",
    )

    def __repr__(self) -> str:
        return (
            f"<Roadmap id={self.id} title={self.title!r} "
            f"modules={self.total_modules}>"
        )


# ============================================================
# Module
# ============================================================

class RoadmapModule(Base, TimestampMixin):
    """A single module inside a roadmap (title only)."""

    __tablename__ = "roadmap_modules"
    __table_args__ = (
        UniqueConstraint(
            "roadmap_id", "module_id", name="uq_roadmap_module"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    module_id: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    roadmap: Mapped["Roadmap"] = relationship(back_populates="modules")

    parts: Mapped[list["RoadmapPart"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="RoadmapPart.order_index",
    )

    def __repr__(self) -> str:
        return f"<RoadmapModule {self.module_id} {self.title!r}>"


# ============================================================
# Part
# ============================================================

class RoadmapPart(Base, TimestampMixin):
    """A single part inside a roadmap module (title + optional prompt)."""

    __tablename__ = "roadmap_parts"
    __table_args__ = (
        UniqueConstraint("module_id", "part_id", name="uq_module_part"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("roadmap_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    part_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # NEW: the teaching prompt for this part (set by the batch generator).
    # Nullable because a part may exist before its prompt is generated,
    # and the schema permits partial states during migration.
    teaching_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Relationships
    module: Mapped["RoadmapModule"] = relationship(back_populates="parts")

    lesson: Mapped["Lesson | None"] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<RoadmapPart {self.part_id} {self.title!r}>"


__all__ = ["Roadmap", "RoadmapModule", "RoadmapPart"]

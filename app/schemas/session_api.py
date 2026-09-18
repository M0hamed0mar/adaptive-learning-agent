"""
Pydantic schemas for the Sessions API (Phase 12).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.config.constants import (
    LearningGoal,
    LearningStyle,
    UserLevel,
)


class _APIModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        from_attributes=True,
    )


ShortText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=200, strip_whitespace=True),
]


# ============================================================
# Session: Create
# ============================================================

class SessionCreateRequest(_APIModel):
    raw_input: str = Field(min_length=3, max_length=2000)


# ============================================================
# Session: Profile
# ============================================================

class SessionProfileRequest(_APIModel):
    level: UserLevel = Field(default=UserLevel.BEGINNER)
    goal: LearningGoal = Field(default=LearningGoal.UNDERSTAND_FUNDAMENTALS)
    role: ShortText = Field(default="General Learner")
    learning_style: LearningStyle = Field(default=LearningStyle.BALANCED)


# ============================================================
# Session: Responses
# ============================================================

class SessionSummary(_APIModel):
    id: int
    user_id: int
    topic: str
    title: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class SessionDetail(_APIModel):
    id: int
    user_id: int
    topic: str
    title: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    has_profile: bool = False
    has_roadmap: bool = False
    total_modules: int | None = None
    total_parts: int | None = None
    progress_percentage: float | None = None


class SessionCreated(_APIModel):
    id: int
    topic: str
    status: str
    created_at: datetime


class SessionProfileAccepted(_APIModel):
    id: int
    status: str
    message: str


# ============================================================
# Profile
# ============================================================

class ProfileResponse(_APIModel):
    session_id: int
    topic: str
    level: str
    goal: str
    role: str
    learning_style: str
    raw_input: str
    language: str


# ============================================================
# Roadmap
# ============================================================

class RoadmapPartResponse(_APIModel):
    part_id: str
    title: str
    order_index: int
    has_prompt: bool


class RoadmapModuleResponse(_APIModel):
    module_id: str
    title: str
    order_index: int
    parts: list[RoadmapPartResponse]


class RoadmapResponse(_APIModel):
    session_id: int
    title: str
    summary: str
    total_modules: int
    estimated_hours: float
    modules: list[RoadmapModuleResponse]


# ============================================================
# Lesson
# ============================================================

class LessonDetail(_APIModel):
    part_id: str
    module_title: str
    part_title: str
    topic: str
    role: str
    level: str
    difficulty: int | None = None
    language: str
    content: str | None = None
    is_generated: bool


class SessionLessonsResponse(_APIModel):
    session_id: int
    total: int
    lessons: list[LessonDetail]


# ============================================================
# Progress
# ============================================================

class ProgressResponse(_APIModel):
    session_id: int
    current_module_index: int
    current_part_index: int
    completed_parts: list[str]
    total_parts: int
    percentage: float


class MarkPartCompletedRequest(_APIModel):
    part_id: ShortText


# ============================================================
# Chat
# ============================================================

class MessageResponse(_APIModel):
    id: int
    session_id: int
    roadmap_part_id: int | None = None
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ChatRequest(_APIModel):
    question: str = Field(min_length=1, max_length=2000)
    allow_web_search: bool = Field(default=False)


class ChatResponse(_APIModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    used_web_search: bool = Field(default=False)


class MessagesListResponse(_APIModel):
    session_id: int
    part_id: str
    total: int
    messages: list[MessageResponse]


__all__ = [
    "SessionCreateRequest",
    "SessionProfileRequest",
    "SessionSummary",
    "SessionDetail",
    "SessionCreated",
    "SessionProfileAccepted",
    "ProfileResponse",
    "RoadmapResponse",
    "RoadmapModuleResponse",
    "RoadmapPartResponse",
    "LessonDetail",
    "SessionLessonsResponse",
    "ProgressResponse",
    "MarkPartCompletedRequest",
    "MessageResponse",
    "ChatRequest",
    "ChatResponse",
    "MessagesListResponse",
]

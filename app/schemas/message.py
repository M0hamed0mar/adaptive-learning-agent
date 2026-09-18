"""
Pydantic schemas for chat messages.

Messages are persisted in the `messages` table and used for:
    - the "ask a question about this lesson" feature,
    - conversation history display,
    - audit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class _StrictBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


ShortText = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]

LongText = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]


# ============================================================
# Message
# ============================================================

MessageRole = Literal["user", "assistant"]


class Message(BaseModel):
    """A single message in a chat."""

    model_config = ConfigDict(
        extra="ignore",
        from_attributes=True,
    )

    id: int
    session_id: int
    roadmap_part_id: int | None = None
    role: MessageRole
    content: str
    created_at: datetime


class MessageCreate(_StrictBase):
    """Input for creating a message (internal use)."""

    role: MessageRole
    content: LongText


# ============================================================
# Chat request/response
# ============================================================

class ChatRequest(_StrictBase):
    """Input for asking a question about a lesson."""

    question: LongText = Field(
        description="The user's question.",
    )
    allow_web_search: bool = Field(
        default=False,
        description="Whether the LLM may use the web search tool.",
    )


class ChatResponse(BaseModel):
    """Response from the tutor chat."""

    model_config = ConfigDict(extra="ignore")

    user_message: Message
    assistant_message: Message
    used_web_search: bool = Field(
        default=False,
        description="True if the LLM invoked web search.",
    )


__all__ = [
    "Message",
    "MessageCreate",
    "MessageRole",
    "ChatRequest",
    "ChatResponse",
]

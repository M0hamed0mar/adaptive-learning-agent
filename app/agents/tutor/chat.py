"""
Tutor Chat Agent (Phase 12.5).

Answers follow-up questions about a specific lesson.

Capabilities:
    - Uses the lesson content + profile as context.
    - Optionally calls a web search tool (when allow_web_search=True).
    - Falls back gracefully when tool use is unavailable.

Uses OpenAI-compatible function calling (Groq supports it for
gpt-oss-120b, gpt-oss-20b, qwen, compound, and others).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import structlog
from openai import AsyncOpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.config.settings import settings
from app.core.exceptions import (
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    TutorAgentError,
)
from app.prompts.chat import (
    TUTOR_CHAT_SYSTEM,
    build_tutor_chat_user_prompt,
)
from app.schemas.lesson import Lesson
from app.schemas.profile import UserProfile
from app.schemas.roadmap import ModuleTitle, PartTitle
from app.tools.web_search import web_search_tool

logger = structlog.get_logger(__name__)


# ============================================================
# Tool definition (OpenAI function calling format)
# ============================================================

_WEB_SEARCH_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for up-to-date information. Use this tool "
            "when the question requires recent facts, version numbers, "
            "news, or data not in your training."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (in English for best results).",
                },
            },
            "required": ["query"],
        },
    },
}


# ============================================================
# Result type
# ============================================================

@dataclass
class ChatAnswer:
    """Result of a chat call."""

    content: str
    used_web_search: bool
    search_queries: list[str]


# ============================================================
# Tutor Chat
# ============================================================

class TutorChat:
    """Stateless chat agent for a specific lesson."""

    def __init__(
        self,
        *,
        model: str | None = None,
        temperature: float = 0.6,
        max_tokens: int = 2048,
        timeout: int | None = None,
    ) -> None:
        self._model = model or settings.GROQ_MODEL
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout or settings.GROQ_TIMEOUT

        self._client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY.get_secret_value(),
            base_url=settings.GROQ_BASE_URL,
            timeout=self._timeout,
            max_retries=0,
        )

    async def answer(
        self,
        *,
        question: str,
        profile: UserProfile,
        module: ModuleTitle,
        part: PartTitle,
        part_id: str,
        lesson: Lesson | None,
        allow_web_search: bool = False,
    ) -> ChatAnswer:
        """
        Answer a question about a lesson.

        Args:
            question: The user's question.
            profile: The user's profile (context).
            module: The parent module.
            part: The part the lesson belongs to.
            part_id: The semantic part ID (e.g. "M1-P1").
            lesson: The lesson object (may be None if not yet generated).
            allow_web_search: If True AND the tool is available, the
                LLM may call web_search.

        Returns:
            A ChatAnswer with the response text and metadata.
        """
        log = logger.bind(
            agent="TutorChat",
            part_id=part_id,
            question_len=len(question),
            allow_web_search=allow_web_search,
        )
        log.info("tutor_chat_started")

        # Determine if we should offer the tool
        use_tools = allow_web_search and web_search_tool.is_available
        tools = [_WEB_SEARCH_TOOL_SPEC] if use_tools else None

        user_prompt = build_tutor_chat_user_prompt(
            question=question,
            profile=profile,
            module=module,
            part=part,
            part_id=part_id,
            lesson=lesson,
        )

        messages = [
            {"role": "system", "content": TUTOR_CHAT_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]

        search_queries: list[str] = []

        # --- Call 1: ask the LLM (with optional tools) ---
        # Build kwargs dynamically so we only pass `tools` and
        # `tool_choice` when we actually want tool use.
        call_kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"

        try:
            first_response = await self._client.chat.completions.create(
                **call_kwargs,
            )
        except APITimeoutError as exc:
            raise LLMConnectionError("Chat request timed out.") from exc
        except APIConnectionError as exc:
            raise LLMConnectionError("Chat connection error.") from exc
        except APIStatusError as exc:
            if exc.status_code == 429:
                raise LLMRateLimitError("Chat rate limit.") from exc
            raise LLMResponseError(
                f"Chat HTTP {exc.status_code}",
                details={"provider": str(exc)[:200]},
            ) from exc
        except Exception as exc:
            raise LLMError(f"Chat unexpected error: {exc}") from exc

        choice = first_response.choices[0]
        message = choice.message

        # --- Handle tool calls ---
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                if tc.function.name != "web_search":
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": "(unknown tool)",
                        }
                    )
                    continue

                try:
                    args = json.loads(tc.function.arguments or "{}")
                    query = str(args.get("query", "")).strip()
                except Exception:
                    query = ""

                if not query:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": "(empty query)",
                        }
                    )
                    continue

                search_queries.append(query)
                log.info("tutor_chat_web_search", query=query[:80])

                results = await web_search_tool.search(query, max_results=4)
                formatted = web_search_tool.format_for_llm(results)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": formatted,
                    }
                )

            # --- Call 2: send tool results back to the LLM ---
            try:
                second_response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
            except APIStatusError as exc:
                if exc.status_code == 429:
                    raise LLMRateLimitError(
                        "Chat rate limit (after tools)."
                    ) from exc
                raise LLMResponseError(
                    f"Chat HTTP {exc.status_code} (after tools)",
                    details={"provider": str(exc)[:200]},
                ) from exc
            except Exception as exc:
                raise LLMError(f"Chat unexpected error: {exc}") from exc

            final_content = second_response.choices[0].message.content or ""
        else:
            final_content = message.content or ""

        final_content = final_content.strip()
        if not final_content:
            raise TutorAgentError(
                "Chat returned an empty response.",
                details={"part_id": part_id},
            )

        log.info(
            "tutor_chat_completed",
            answer_length=len(final_content),
            used_web_search=bool(search_queries),
        )

        return ChatAnswer(
            content=final_content,
            used_web_search=bool(search_queries),
            search_queries=search_queries,
        )


# ============================================================
# Singleton
# ============================================================

tutor_chat = TutorChat()


__all__ = ["TutorChat", "ChatAnswer", "tutor_chat"]

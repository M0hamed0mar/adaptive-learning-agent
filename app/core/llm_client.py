"""
Asynchronous LLM client wrapper.

Adds the following on top of the raw OpenAI-compatible client:

    1. **Client-side rate limiting.** A single global lock and a
       `last_request_time` timestamp enforce a minimum interval
       between consecutive requests (`GROQ_MIN_REQUEST_INTERVAL`).
       This keeps us under Groq's free-tier TPM limit.

    2. **Retry with exponential backoff** for transient errors:
       - connection / timeout errors
       - rate-limit errors (HTTP 429)
       - payload-too-large errors (HTTP 413)
       - validation errors (so the LLM can retry with fresh output)

    3. **Structured output support** via `generate_structured`, which
       wraps the request in a JSON-mode prompt and validates the
       result against a Pydantic schema.

    4. **Truncation detection.** When the LLM stops because it hit
       `max_tokens`, we surface a validation error (which is retryable).

Design notes:
    - The rate limiter is process-wide, not per-client. This is
      intentional: a single FastAPI process should never fire more
      than one request at a time to a TPM-limited provider.
    - The throttle is applied BEFORE every request (successful or
      failed). Failed requests still consume our "budget" of time.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, TypeVar

import openai
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError as PydanticValidationError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.settings import settings
from app.core.exceptions import (
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMValidationError,
)

logger = structlog.get_logger(__name__)


TModel = TypeVar("TModel", bound=BaseModel)


# ============================================================
# Retry policy
# ============================================================

# Exceptions that trigger a retry with exponential backoff.
#
# Note: we include `LLMResponseError` because HTTP 413 (payload too
# large / TPM exceeded) is mapped to it by `_map_openai_exception`.
# Retrying after a long backoff lets the TPM window drain.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    LLMConnectionError,
    LLMRateLimitError,
    LLMValidationError,
    LLMResponseError,
)


# ============================================================
# Client
# ============================================================

class LLMClient:
    """Async wrapper around the Groq (OpenAI-compatible) Chat Completions API."""

    # --------------------------------------------------------
    # Rate limiting (class-level, shared across instances)
    # --------------------------------------------------------
    _rate_lock: asyncio.Lock | None = None
    _last_request_ts: float = 0.0

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._api_key: str = (
            api_key if api_key is not None
            else settings.GROQ_API_KEY.get_secret_value()
        )
        self._base_url: str = base_url or settings.GROQ_BASE_URL
        self._model: str = model or settings.GROQ_MODEL
        self._timeout: int = timeout or settings.GROQ_TIMEOUT
        self._max_retries: int = (
            max_retries if max_retries is not None
            else settings.GROQ_MAX_RETRIES
        )

        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=0,
        )

    # --------------------------------------------------------
    # Rate limiter
    # --------------------------------------------------------

    @classmethod
    def _get_rate_lock(cls) -> asyncio.Lock:
        """Lazily create the process-wide rate-limit lock."""
        if cls._rate_lock is None:
            cls._rate_lock = asyncio.Lock()
        return cls._rate_lock

    @classmethod
    async def _throttle(cls) -> None:
        """
        Enforce `GROQ_MIN_REQUEST_INTERVAL` between consecutive requests.

        The lock serializes all callers; the sleep fills the gap since
        the previous request. This is a simple but effective way to stay
        under Groq's free-tier TPM limit without implementing a full
        token-bucket.
        """
        interval = settings.GROQ_MIN_REQUEST_INTERVAL
        if interval <= 0:
            return

        lock = cls._get_rate_lock()
        async with lock:
            now = time.monotonic()
            elapsed = now - cls._last_request_ts
            wait = interval - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            cls._last_request_ts = time.monotonic()

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------

    async def generate_text(
        self,
        *,
        prompt: str,
        instructions: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        call_model = model or self._model
        call_temperature = (
            temperature if temperature is not None
            else settings.GROQ_TEMPERATURE
        )
        call_max_tokens = max_tokens or settings.GROQ_MAX_TOKENS

        log = logger.bind(method="generate_text", model=call_model, **(metadata or {}))
        log.debug("llm_request_started", prompt_length=len(prompt))

        async def _invoke() -> str:
            await self._throttle()
            try:
                messages: list[dict] = []
                if instructions:
                    messages.append({"role": "system", "content": instructions})
                messages.append({"role": "user", "content": prompt})

                response = await self._client.chat.completions.create(
                    model=call_model,
                    messages=messages,
                    temperature=call_temperature,
                    max_tokens=call_max_tokens,
                )
            except Exception as exc:
                raise _map_openai_exception(exc) from exc

            text = response.choices[0].message.content
            if not text:
                raise LLMResponseError(
                    "LLM returned an empty text response.",
                    details={"model": call_model},
                )
            return text

        try:
            result = await self._run_with_retry(_invoke, log=log)
        except LLMError:
            raise
        except RetryError as exc:
            raise LLMResponseError(
                "LLM call failed after all retries.",
                details={"model": call_model},
            ) from exc

        log.debug("llm_request_completed", response_length=len(result))
        return result

    async def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[TModel],
        instructions: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TModel:
        call_model = model or self._model
        call_temperature = (
            temperature if temperature is not None
            else settings.GROQ_TEMPERATURE
        )
        call_max_tokens = max_tokens or settings.GROQ_MAX_TOKENS
        schema_name = schema.__name__

        log = logger.bind(
            method="generate_structured",
            model=call_model,
            schema=schema_name,
            **(metadata or {}),
        )
        log.debug("llm_request_started", prompt_length=len(prompt))

        async def _invoke() -> TModel:
            await self._throttle()
            try:
                json_instruction = (
                    "You MUST respond with a single, valid JSON object "
                    "and nothing else. Do NOT wrap the JSON in markdown "
                    "code fences. Do NOT add explanations before or after "
                    "the JSON. Fill EVERY field in the schema — do NOT omit "
                    "any field, even optional ones."
                )

                system_parts: list[str] = []
                if instructions:
                    system_parts.append(instructions)
                system_parts.append(json_instruction)
                system_parts.append(
                    "The JSON object MUST match this schema exactly:\n"
                    f"{schema.model_json_schema()}"
                )

                messages: list[dict] = [
                    {"role": "system", "content": "\n\n".join(system_parts)},
                    {"role": "user", "content": prompt},
                ]

                response = await self._client.chat.completions.create(
                    model=call_model,
                    messages=messages,
                    temperature=call_temperature,
                    max_tokens=call_max_tokens,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:
                raise _map_openai_exception(exc) from exc

            choice = response.choices[0]
            raw = choice.message.content
            finish_reason = getattr(choice, "finish_reason", None)

            if not raw:
                raise LLMResponseError(
                    "LLM returned an empty structured response.",
                    details={"model": call_model, "schema": schema_name},
                )

            # Detect truncation. Groq returns "length" when max_tokens was hit.
            if finish_reason == "length":
                raise LLMValidationError(
                    "LLM output was truncated (max_tokens reached).",
                    details={
                        "schema": schema_name,
                        "finish_reason": finish_reason,
                        "raw_length": len(raw),
                    },
                )

            cleaned = _strip_markdown_fences(raw)

            try:
                return schema.model_validate_json(cleaned)
            except PydanticValidationError as exc:
                raise LLMValidationError(
                    "LLM response failed schema validation.",
                    details={
                        "schema": schema_name,
                        "errors": exc.errors(include_url=False),
                        "raw": cleaned[:500],
                    },
                ) from exc

        try:
            result = await self._run_with_retry(_invoke, log=log)
        except LLMError:
            raise
        except RetryError as exc:
            raise LLMResponseError(
                "LLM structured call failed after all retries.",
                details={"model": call_model, "schema": schema_name},
            ) from exc

        log.debug("llm_request_completed", schema=schema_name)
        return result

    # --------------------------------------------------------
    # Retry helper
    # --------------------------------------------------------

    async def _run_with_retry(self, fn, *, log: structlog.stdlib.BoundLogger):
        """
        Run `fn` with exponential backoff on retryable errors.

        Backoff parameters come from settings so they can be tuned
        per-environment. On Groq's free tier, the max backoff should
        exceed 60s to let the TPM window drain after a 413.
        """
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(
                multiplier=settings.GROQ_RETRY_BACKOFF_MULTIPLIER,
                min=2,
                max=settings.GROQ_RETRY_BACKOFF_MAX,
            ),
            retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
            reraise=True,
        ):
            with attempt:
                if attempt.retry_state.attempt_number > 1:
                    log.warning(
                        "llm_request_retrying",
                        attempt=attempt.retry_state.attempt_number,
                        max_attempts=self._max_retries + 1,
                    )
                return await fn()

        raise LLMResponseError("Retry loop terminated unexpectedly.")


# ============================================================
# Helpers
# ============================================================

def _strip_markdown_fences(raw: str) -> str:
    text = raw.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].lstrip()
    elif text.startswith("```"):
        text = text[len("```"):].lstrip()

    if text.endswith("```"):
        text = text[:-len("```")].rstrip()

    return text.strip()


def _map_openai_exception(exc: Exception) -> LLMError:
    if isinstance(exc, LLMError):
        return exc

    if isinstance(exc, openai.APITimeoutError):
        return LLMConnectionError("LLM request timed out.")

    if isinstance(exc, openai.APIConnectionError):
        return LLMConnectionError("Failed to connect to the LLM provider.")

    if isinstance(exc, openai.RateLimitError):
        return LLMRateLimitError("LLM provider rate limit exceeded.")

    if isinstance(exc, openai.APIStatusError):
        status_code = exc.status_code

        # 413 = payload too large / TPM exceeded. Treat as retryable.
        if status_code == 413:
            return LLMResponseError(
                "LLM provider rejected the request as too large "
                "(likely TPM budget exceeded).",
                details={
                    "type": type(exc).__name__,
                    "status_code": status_code,
                    "provider_message": str(exc)[:500],
                },
            )

        # Other 4xx/5xx.
        return LLMResponseError(
            f"LLM provider returned HTTP {status_code}.",
            details={
                "type": type(exc).__name__,
                "status_code": status_code,
                "provider_message": str(exc)[:500],
            },
        )

    return LLMError(
        "Unexpected LLM error.",
        details={"type": type(exc).__name__, "message": str(exc)},
    )


# ============================================================
# Singleton
# ============================================================

llm_client = LLMClient()


__all__ = ["LLMClient", "llm_client"]
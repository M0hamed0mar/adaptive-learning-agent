"""
Structured logging configuration.

Uses `structlog` to emit logs as JSON in production and as
human-readable, colorized output in development.

Usage:
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("user_action", action="next", user_id=42)
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config.constants import LOG_TIMESTAMP_FORMAT, LOGGER_NAME
from app.config.settings import settings


def _build_shared_processors() -> list[Processor]:
    """
    Return processors shared by all environments.

    These processors run on every log event regardless of the target
    renderer (JSON or console).
    """
    return [
        # Merge contextvars into the event dict (e.g. request IDs).
        structlog.contextvars.merge_contextvars,

        # Add the logger name.
        structlog.stdlib.add_logger_name,

        # Add the log level (info, warning, ...).
        structlog.stdlib.add_log_level,

        # Add an ISO-8601 timestamp.
        structlog.processors.TimeStamper(fmt="iso", utc=True),

        # Attach stack info when requested.
        structlog.processors.StackInfoRenderer(),

        # Format exception tracebacks.
        structlog.processors.format_exc_info,

        # Decode byte strings for JSON-friendliness.
        structlog.processors.UnicodeDecoder(),
    ]


def _build_development_processors() -> list[Processor]:
    """Human-readable console output for local development."""
    return [
        structlog.dev.ConsoleRenderer(colors=True),
    ]


def _build_production_processors() -> list[Processor]:
    """JSON output for production (machine-parseable)."""
    return [
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
    ]


def configure_logging() -> None:
    """
    Configure structlog and the stdlib logging bridge.

    Called once at application startup. Safe to call multiple times;
    the most recent configuration wins.
    """
    shared = _build_shared_processors()

    if settings.is_production:
        renderer_processors = _build_production_processors()
        log_level = logging.INFO
    else:
        renderer_processors = _build_development_processors()
        log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    # Configure structlog
    structlog.configure(
        processors=[
            *shared,
            # Prepare the event dict for stdlib's ProcessorFormatter.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog for consistent output.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *renderer_processors,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Tame noisy third-party loggers.
    for noisy in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Return a bound structlog logger.

    Args:
        name: Optional logger name. Defaults to the project logger.

    Returns:
        A structlog BoundLogger ready for structured calls.
    """
    return structlog.get_logger(name or LOGGER_NAME)


def bind_request_context(**kwargs: Any) -> None:
    """
    Bind key-value pairs to the current async context.

    Every log emitted afterwards (within the same task) will include
    these fields automatically.

    Example:
        bind_request_context(session_id="abc-123")
        logger.info("lesson_started")  # includes session_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    """Clear all contextvars bound to the current task."""
    structlog.contextvars.clear_contextvars()
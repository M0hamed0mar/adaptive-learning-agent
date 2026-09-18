"""
Custom exception hierarchy for the Adaptive Learning Agent.

All application-specific exceptions inherit from `AppError`, which allows
callers to catch any project-level error with a single `except AppError`.

Exceptions carry a structured payload (`details`) that can be logged
and, when appropriate, surfaced to API clients.

Design notes:
    - Every `AppError` subclass declares a `status_code` and an
      `error_code` so the FastAPI error handlers can map exceptions to
      HTTP responses without a long if/else chain.
    - Unknown subclasses fall back to 500 / "internal_error".
"""

from typing import Any


# ============================================================
# Base
# ============================================================

class AppError(Exception):
    """
    Base class for all application-specific exceptions.

    Attributes:
        message: Human-readable error description.
        details: Optional structured context (e.g. field name, model ID).
        status_code: HTTP status code to use when surfaced via the API.
        error_code: Machine-readable code for client-side handling.
    """

    default_message: str = "An unexpected application error occurred."
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message: str = message or self.default_message
        self.details: dict[str, Any] = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message


# ============================================================
# Configuration
# ============================================================

class ConfigurationError(AppError):
    """Raised when the application is misconfigured (e.g. missing env var)."""

    default_message = "Application configuration is invalid."
    status_code = 500
    error_code = "configuration_error"


# ============================================================
# LLM
# ============================================================

class LLMError(AppError):
    """Base class for all LLM-related failures."""

    default_message = "An LLM operation failed."
    status_code = 502
    error_code = "llm_error"


class LLMConnectionError(LLMError):
    """Raised when the LLM provider is unreachable (network, DNS, timeout)."""

    default_message = "Failed to connect to the LLM provider."
    status_code = 503
    error_code = "llm_connection_error"


class LLMRateLimitError(LLMError):
    """Raised when the provider returns a rate-limit response."""

    default_message = "LLM provider rate limit exceeded."
    status_code = 429
    error_code = "llm_rate_limit"


class LLMValidationError(LLMError):
    """Raised when the LLM returns a response that fails schema validation."""

    default_message = "LLM response failed validation."
    status_code = 502
    error_code = "llm_validation_error"


class LLMResponseError(LLMError):
    """Raised when the LLM returns an unexpected or unusable response."""

    default_message = "LLM returned an unexpected response."
    status_code = 502
    error_code = "llm_response_error"


# ============================================================
# Agents
# ============================================================

class AgentError(AppError):
    """Base class for all agent-level failures."""

    default_message = "An agent operation failed."
    status_code = 500
    error_code = "agent_error"


class ProfileAgentError(AgentError):
    """Raised when the profile agent fails to produce a valid profile."""

    default_message = "Profile agent failed."
    error_code = "profile_agent_error"


class RoadmapAgentError(AgentError):
    """Raised when the roadmap agent fails to produce a valid roadmap."""

    default_message = "Roadmap agent failed."
    error_code = "roadmap_agent_error"


class PromptAgentError(AgentError):
    """Raised when the prompt agent fails to generate a teaching prompt."""

    default_message = "Prompt agent failed."
    error_code = "prompt_agent_error"


class TutorAgentError(AgentError):
    """Raised when the tutor agent fails to produce a lesson or answer."""

    default_message = "Tutor agent failed."
    error_code = "tutor_agent_error"


# ============================================================
# Roadmap-specific
# ============================================================

class RoadmapError(AppError):
    """Base class for roadmap-related failures."""

    default_message = "A roadmap operation failed."
    status_code = 500
    error_code = "roadmap_error"


class RoadmapGenerationError(RoadmapError):
    """Raised when the roadmap could not be generated at all."""

    default_message = "Failed to generate a roadmap."
    error_code = "roadmap_generation_error"


class RoadmapEvaluationError(RoadmapError):
    """Raised when the critic fails to evaluate a roadmap."""

    default_message = "Failed to evaluate the roadmap."
    error_code = "roadmap_evaluation_error"


class RoadmapRefinementError(RoadmapError):
    """Raised when the refinement loop exceeded the max iterations."""

    default_message = "Roadmap refinement did not converge."
    error_code = "roadmap_refinement_error"


# ============================================================
# Database
# ============================================================

class DatabaseError(AppError):
    """Base class for all database-related failures."""

    default_message = "A database operation failed."
    status_code = 500
    error_code = "database_error"


class RecordNotFoundError(DatabaseError):
    """Raised when a requested record does not exist."""

    default_message = "Requested record was not found."
    status_code = 404
    error_code = "record_not_found"


class DuplicateRecordError(DatabaseError):
    """Raised when attempting to insert a record that violates a unique constraint."""

    default_message = "A record with the same unique key already exists."
    status_code = 409
    error_code = "duplicate_record"


# ============================================================
# Validation
# ============================================================

class ValidationError(AppError):
    """Base class for input/schema validation failures."""

    default_message = "Input validation failed."
    status_code = 422
    error_code = "validation_error"


class InvalidInputError(ValidationError):
    """Raised when user input is semantically invalid."""

    default_message = "The provided input is invalid."
    error_code = "invalid_input"


class SchemaValidationError(ValidationError):
    """Raised when a payload does not conform to its expected schema."""

    default_message = "Payload does not match the expected schema."
    error_code = "schema_validation"


__all__ = [
    "AppError",
    "ConfigurationError",
    # LLM
    "LLMError",
    "LLMConnectionError",
    "LLMRateLimitError",
    "LLMValidationError",
    "LLMResponseError",
    # Agents
    "AgentError",
    "ProfileAgentError",
    "RoadmapAgentError",
    "PromptAgentError",
    "TutorAgentError",
    # Roadmap
    "RoadmapError",
    "RoadmapGenerationError",
    "RoadmapEvaluationError",
    "RoadmapRefinementError",
    # Database
    "DatabaseError",
    "RecordNotFoundError",
    "DuplicateRecordError",
    # Validation
    "ValidationError",
    "InvalidInputError",
    "SchemaValidationError",
]
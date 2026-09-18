"""
Application settings loaded from environment variables.

This module provides a centralized, type-safe configuration object
built on top of pydantic-settings. All environment variables are
validated at startup, failing fast on misconfiguration.

The project uses Groq as the LLM provider. Groq is OpenAI-compatible,
so we reuse the same SDK with a different base_url.

Usage:
    from app.config.settings import settings

    client = AsyncOpenAI(
        api_key=settings.GROQ_API_KEY.get_secret_value(),
        base_url=settings.GROQ_BASE_URL,
    )

Design notes:
    - Groq's free tier enforces a Tokens-Per-Minute (TPM) limit of
      ~8,000 on the `openai/gpt-oss-*` models. To stay under it, we
      throttle requests client-side via `GROQ_MIN_REQUEST_INTERVAL`
      (seconds between consecutive requests) and retry on HTTP 413
      with a long backoff.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# Paths
# ============================================================

# Project root directory (two levels up from this file)
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# Environment file location
ENV_FILE: Path = BASE_DIR / ".env"


# ============================================================
# Settings
# ============================================================

class Settings(BaseSettings):
    """
    Application settings.

    All values are loaded from environment variables (or `.env` file)
    and validated at instantiation time.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --------------------------------------------------------
    # LLM Provider
    # --------------------------------------------------------
    LLM_PROVIDER: Literal["groq", "openai"] = "groq"

    # Groq configuration (primary)
    GROQ_API_KEY: SecretStr = Field(
        ...,
        description="Groq API key. Required.",
    )
    GROQ_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq OpenAI-compatible base URL.",
    )
    GROQ_MODEL: str = Field(
        default="qwen/qwen3.8-27b",
        description="Groq model identifier.",
    )
    GROQ_TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for the LLM.",
    )
    GROQ_MAX_TOKENS: int = Field(
        default=4096,
        gt=0,
        description=(
            "Maximum tokens in the LLM response. Kept moderate to stay "
            "within Groq's free-tier TPM budget."
        ),
    )
    GROQ_TIMEOUT: int = Field(
        default=90,
        gt=0,
        description="Request timeout in seconds.",
    )
    GROQ_MAX_RETRIES: int = Field(
        default=5,
        ge=0,
        le=10,
        description="Maximum number of retries on transient failures.",
    )

    # --------------------------------------------------------
    # Groq rate-limit throttling
    # --------------------------------------------------------
    GROQ_MIN_REQUEST_INTERVAL: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Minimum seconds between two consecutive Groq requests. "
            "Groq's free tier TPM limit is ~8000 for the gpt-oss models; "
            "this throttle prevents us from bursting past it. Set to "
            "0.0 to disable (not recommended on the free tier)."
        ),
    )
    GROQ_RETRY_BACKOFF_MULTIPLIER: float = Field(
        default=4.0,
        ge=1.0,
        description=(
            "Multiplier for the exponential backoff applied between "
            "retries. Higher values = longer waits (safer on TPM-bound "
            "providers)."
        ),
    )
    GROQ_RETRY_BACKOFF_MAX: float = Field(
        default=90.0,
        gt=0.0,
        description=(
            "Maximum seconds to wait between retries. Should be at "
            "least 60s so a full TPM window can elapse."
        ),
    )

    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------
    APP_NAME: str = Field(
        default="Adaptive Learning Agent",
        description="Human-readable application name.",
    )
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = Field(
        default=True,
        description="Enable debug mode (verbose logging, detailed errors).",
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./adaptive_learning.db",
        description=(
            "SQLAlchemy async-compatible database URL. "
            "Development: sqlite+aiosqlite:///./adaptive_learning.db "
            "Production:  postgresql+asyncpg://user:pass@host:5432/db"
        ),
    )

    # --------------------------------------------------------
    # Web Search (used in Phase 8)
    # --------------------------------------------------------
    WEB_SEARCH_PROVIDER: Literal["tavily"] = "tavily"
    TAVILY_API_KEY: SecretStr | None = Field(
        default=None,
        description="Tavily API key. Optional until Phase 8.",
    )

    # --------------------------------------------------------
    # Validators
    # --------------------------------------------------------
    @field_validator("GROQ_API_KEY")
    @classmethod
    def validate_groq_api_key(cls, value: SecretStr) -> SecretStr:
        """Ensure the API key is not empty and looks plausible."""
        raw = value.get_secret_value().strip()

        if not raw:
            raise ValueError("GROQ_API_KEY must not be empty.")

        if not raw.startswith("gsk_"):
            raise ValueError(
                "GROQ_API_KEY appears invalid "
                "(expected it to start with 'gsk_')."
            )

        return value

    # --------------------------------------------------------
    # Convenience helpers
    # --------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """Return True when running in production."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Return True when running in development."""
        return self.APP_ENV == "development"


# ============================================================
# Singleton access
# ============================================================

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    The `lru_cache` decorator ensures the `.env` file is parsed only once
    per process, and that a single Settings object is shared everywhere.
    """
    return Settings()


# Module-level convenience alias.
# Import this directly: `from app.config.settings import settings`
settings: Settings = get_settings()


__all__ = ["Settings", "get_settings", "settings"]
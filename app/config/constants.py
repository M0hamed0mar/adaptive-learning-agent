"""
Project-wide constants.

Values defined here are immutable facts about the application's
domain model and workflow. They are NOT meant to be overridden
per-environment (use `settings.py` for that).
"""

from enum import StrEnum


# ============================================================
# API Metadata
# ============================================================

API_V1_PREFIX: str = "/api/v1"
API_TITLE: str = "Adaptive Learning Agent API"
API_DESCRIPTION: str = (
    "An AI-powered adaptive learning system that generates personalized "
    "roadmaps and delivers tailored lessons for technical topics."
)
API_VERSION: str = "0.1.0"


# ============================================================
# Session States
# ============================================================

class SessionStatus(StrEnum):
    """Lifecycle states of a study session."""

    DRAFT = "draft"               # Created, profile not yet submitted
    PROFILING = "profiling"       # Collecting user information (future)
    PLANNING = "planning"         # Generating roadmap + prompts (background)
    READY = "ready"               # Roadmap + prompts ready; lessons on demand
    LEARNING = "learning"         # User is actively studying
    COMPLETED = "completed"       # All modules finished
    FAILED = "failed"             # Pipeline failed with an error
    ARCHIVED = "archived"         # Manually archived by the user


# ============================================================
# User Actions
# ============================================================

class UserAction(StrEnum):
    """Actions a user can take during a learning session."""

    START = "start"
    ANSWER_PROFILE = "answer_profile"
    GENERATE_ROADMAP = "generate_roadmap"
    NEXT = "next"
    ASK = "ask"
    EXPLAIN_AGAIN = "explain_again"
    MORE_EXAMPLES = "more_examples"
    SIMPLIFY = "simplify"
    SUMMARIZE = "summarize"
    FINISH = "finish"


# ============================================================
# Learning Levels
# ============================================================

class UserLevel(StrEnum):
    """Self-reported user proficiency levels."""

    BEGINNER = "beginner"
    BEGINNER_WITH_KNOWLEDGE = "beginner_with_knowledge"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LearningGoal(StrEnum):
    """Primary motivation for studying a topic."""

    UNDERSTAND_FUNDAMENTALS = "understand_fundamentals"
    BUILD_PROJECTS = "build_projects"
    PROFESSIONAL_USAGE = "professional_usage"
    INTERVIEW_PREP = "interview_prep"


class LearningStyle(StrEnum):
    """Preferred delivery style for lessons."""

    THEORETICAL = "theoretical"
    PRACTICAL = "practical"
    BALANCED = "balanced"


# ============================================================
# Evaluation Thresholds & Limits
# ============================================================

# Minimum critic score (0-10) required for a roadmap to be approved.
ROADMAP_APPROVAL_THRESHOLD: float = 8.0

# Maximum number of refinement iterations for the roadmap.
# With the new design, we only need ONE refinement pass.
ROADMAP_MAX_REFINEMENTS: int = 1

# Minimum critic score for a teaching prompt set to be approved.
PROMPT_SET_APPROVAL_THRESHOLD: float = 8.0

# Maximum number of refinement iterations for the prompt set.
# With the new design, we only need ONE refinement pass.
PROMPT_SET_MAX_REFINEMENTS: int = 1

# Minimum critic score for a user profile to be approved.
PROFILE_APPROVAL_THRESHOLD: float = 8.0


# ============================================================
# Prompt / Agent Limits
# ============================================================

# Maximum number of modules per roadmap.
MAX_ROADMAP_MODULES: int = 6

# Maximum number of parts per module.
MAX_MODULE_PARTS: int = 6


# ============================================================
# Language
# ============================================================

# Default output language for lessons and prompts (ISO 639-1).
DEFAULT_LANGUAGE: str = "ar"


# ============================================================
# Database
# ============================================================

# Table name prefixes to avoid collisions.
TABLE_PREFIX: str = "ala_"


# ============================================================
# Logging
# ============================================================

# Timestamp format used in structured logs.
LOG_TIMESTAMP_FORMAT: str = "%Y-%m-%dT%H:%M:%S.%fZ"

# Name of the logger namespace for the project.
LOGGER_NAME: str = "adaptive_learning_agent"


__all__ = [
    # API
    "API_V1_PREFIX",
    "API_TITLE",
    "API_DESCRIPTION",
    "API_VERSION",
    # Enums
    "SessionStatus",
    "UserAction",
    "UserLevel",
    "LearningGoal",
    "LearningStyle",
    # Thresholds
    "ROADMAP_APPROVAL_THRESHOLD",
    "ROADMAP_MAX_REFINEMENTS",
    "PROMPT_SET_APPROVAL_THRESHOLD",
    "PROMPT_SET_MAX_REFINEMENTS",
    "PROFILE_APPROVAL_THRESHOLD",
    # Limits
    "MAX_ROADMAP_MODULES",
    "MAX_MODULE_PARTS",
    # Language
    "DEFAULT_LANGUAGE",
    # Misc
    "TABLE_PREFIX",
    "LOG_TIMESTAMP_FORMAT",
    "LOGGER_NAME",
]

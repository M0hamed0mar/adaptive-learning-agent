"""
Helpers for the web layer (Phase 12).
"""

from __future__ import annotations

from datetime import datetime, timezone

import markdown as md
from markupsafe import Markup


# ============================================================
# Markdown rendering
# ============================================================

_MD = md.Markdown(
    extensions=[
        "fenced_code",
        "codehilite",
        "tables",
        "sane_lists",
        "nl2br",
    ],
    extension_configs={
        "codehilite": {
            "css_class": "codehilite",
            "guess_lang": False,
            "linenums": False,
        },
    },
    output_format="html5",
)


def render_markdown(text: str | None) -> Markup:
    if not text:
        return Markup("")
    return Markup(_MD.reset().convert(text))


# ============================================================
# Filters
# ============================================================

def format_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%b %d, %H:%M")


def status_label(status: str) -> str:
    mapping = {
        "draft": "Draft",
        "profiling": "Profiling",
        "planning": "Generating",
        "ready": "Ready",
        "learning": "In progress",
        "completed": "Completed",
        "failed": "Failed",
        "archived": "Archived",
    }
    return mapping.get(status, status.title())


def shorten(text: str | None, max_len: int = 60) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def session_progress_text(completed: int, total: int) -> str:
    if total <= 0:
        return "Not started"
    return f"{completed}/{total} lessons"


def time_ago(dt: datetime | None) -> str:
    """Return a short 'time ago' string."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return dt.strftime("%b %d")


__all__ = [
    "render_markdown",
    "format_datetime",
    "status_label",
    "shorten",
    "session_progress_text",
    "time_ago",
]

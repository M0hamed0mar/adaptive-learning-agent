"""
Web search tool (Tavily).

Provides an async `search()` method that returns a compact list of
results suitable for feeding back to an LLM.

Design:
    - Uses the official `tavily-python` SDK.
    - Returns a small, LLM-friendly summary: title + url + snippet.
    - Gracefully no-ops when the API key is missing.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.config.settings import settings

logger = structlog.get_logger(__name__)


# ============================================================
# Result type
# ============================================================

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def to_llm_line(self) -> str:
        return f"- {self.title} ({self.url}): {self.snippet}"


# ============================================================
# Tool
# ============================================================

class WebSearchTool:
    """
    Async wrapper around Tavily.

    Usage:
        results = await web_search_tool.search("latest python 3.14 features", max_results=3)
        text = web_search_tool.format_for_llm(results)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_results: int = 5,
    ) -> None:
        self._api_key: str | None = (
            api_key
            if api_key is not None
            else (
                settings.TAVILY_API_KEY.get_secret_value()
                if settings.TAVILY_API_KEY is not None
                else None
            )
        )
        self._max_results = max_results

    @property
    def is_available(self) -> bool:
        """True if the tool is configured (API key present)."""
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
    ) -> list[SearchResult]:
        """
        Run a web search.

        Returns an empty list if the tool is not available.
        """
        if not self.is_available:
            logger.debug("web_search_skipped_no_api_key", query=query[:50])
            return []

        try:
            from tavily import AsyncTavilyClient
        except ImportError:
            logger.error(
                "web_search_sdk_not_installed",
                hint="pip install tavily-python",
            )
            return []

        log = logger.bind(tool="web_search", query=query[:60])
        log.info("web_search_started")

        try:
            client = AsyncTavilyClient(api_key=self._api_key)
            response = await client.search(
                query=query,
                max_results=max_results or self._max_results,
                search_depth="basic",
            )
        except Exception as exc:
            log.error(
                "web_search_failed",
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
            )
            return []

        raw_results = response.get("results", []) or []
        results: list[SearchResult] = []
        for r in raw_results:
            results.append(
                SearchResult(
                    title=str(r.get("title", "")).strip(),
                    url=str(r.get("url", "")).strip(),
                    snippet=str(r.get("content", "")).strip()[:500],
                )
            )

        log.info("web_search_completed", count=len(results))
        return results

    @staticmethod
    def format_for_llm(results: list[SearchResult]) -> str:
        """Format search results as a compact bulleted list for the LLM."""
        if not results:
            return "(no web search results)"
        return "\n".join(r.to_llm_line() for r in results)


# ============================================================
# Singleton
# ============================================================

web_search_tool = WebSearchTool()


__all__ = ["WebSearchTool", "web_search_tool", "SearchResult"]

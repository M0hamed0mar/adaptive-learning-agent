"""
Tools package.

Exposes external tools that agents can call (web search, etc.).
"""

from app.tools.web_search import WebSearchTool, web_search_tool

__all__ = ["WebSearchTool", "web_search_tool"]

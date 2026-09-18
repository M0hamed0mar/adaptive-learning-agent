"""
Web (HTML) layer.

Server-rendered UI built with FastAPI + Jinja2 + HTMX + Tailwind CSS.

Design:
    - Two-pane layout: sessions sidebar (always visible) + main area.
    - Inside a session, a second sidebar shows the modules tree.
    - Course page (Coursera-style) when a session is open.
    - All icons are inline SVG (no emoji).
    - Color palette: white, black, violet/indigo.
"""

from app.web.routes import router as web_router

__all__ = ["web_router"]

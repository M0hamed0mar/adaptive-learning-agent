"""
FastAPI application entry point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.routes import (
    health,
    lessons,
    messages,
    profile,
    progress,
    roadmap,
    sessions,
)
from app.config.constants import (
    API_DESCRIPTION,
    API_TITLE,
    API_V1_PREFIX,
    API_VERSION,
)
from app.config.settings import settings
from app.core.logging import configure_logging
from app.database.connection import dispose_engine
from app.web import web_router

logger = structlog.get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = logger.bind(app=settings.APP_NAME, env=settings.APP_ENV)
    log.info("app_starting")
    yield
    log.info("app_stopping")
    await dispose_engine()
    log.info("app_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    register_exception_handlers(app)

    if settings.is_development:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    static_dir = BASE_DIR / "app" / "web" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    # JSON API
    app.include_router(health.router, prefix=API_V1_PREFIX)
    app.include_router(sessions.router, prefix=API_V1_PREFIX)
    app.include_router(profile.router, prefix=API_V1_PREFIX)
    app.include_router(roadmap.router, prefix=API_V1_PREFIX)
    app.include_router(lessons.router, prefix=API_V1_PREFIX)
    app.include_router(progress.router, prefix=API_V1_PREFIX)
    app.include_router(messages.router, prefix=API_V1_PREFIX)

    # HTML UI
    app.include_router(web_router)

    return app


app = create_app()


__all__ = ["app", "create_app"]

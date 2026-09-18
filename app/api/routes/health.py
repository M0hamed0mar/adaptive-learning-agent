"""
Health check endpoint.

Used by load balancers (AWS ALB, App Runner) and Docker HEALTHCHECK.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.api.dependencies import SettingsDep
from app.config.constants import API_VERSION

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
)
async def health_check(settings: SettingsDep) -> HealthResponse:
    """Return the service health status."""
    return HealthResponse(
        status="ok",
        version=API_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc),
    )


__all__ = ["router"]

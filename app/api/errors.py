"""
FastAPI exception handlers.

Registers handlers that convert application exceptions into structured
JSON error responses. Every error response has the same shape:

    {
        "error": {
            "code": "record_not_found",
            "message": "Requested record was not found.",
            "details": {...}
        }
    }

Handlers:
    - AppError                 → uses the exception's status_code/error_code
    - RequestValidationError   → 422 with field-level errors
    - HTTPException            → passthrough with normalized shape
    - Exception                → 500 with a generic message (details are
                                 logged server-side, never leaked)
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.core.exceptions import AppError

logger = structlog.get_logger(__name__)


# ============================================================
# Response builders
# ============================================================

def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    """Build a normalized JSON error response."""
    body = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


# ============================================================
# Handler registration
# ============================================================

def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""

    # --------------------------------------------------------
    # 1. Application errors (AppError hierarchy)
    # --------------------------------------------------------
    @app.exception_handler(AppError)
    async def _handle_app_error(
        request: Request,
        exc: AppError,
    ) -> JSONResponse:
        log = logger.bind(
            handler="app_error",
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
            error_code=exc.error_code,
        )

        if exc.status_code >= 500:
            log.error("api_error", message=exc.message, details=exc.details)
        else:
            log.warning("api_error", message=exc.message, details=exc.details)

        return _error_response(
            status_code=exc.status_code,
            code=exc.error_code,
            message=exc.message,
            details=exc.details or None,
        )

    # --------------------------------------------------------
    # 2. Request validation errors (Pydantic)
    # --------------------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "api_validation_error",
            method=request.method,
            path=request.url.path,
            errors=exc.errors(),
        )
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="request_validation_error",
            message="Request body or parameters failed validation.",
            details={"errors": exc.errors()},
        )

    # --------------------------------------------------------
    # 3. Plain HTTPException (404s raised by routes, etc.)
    # --------------------------------------------------------
    @app.exception_handler(HTTPException)
    async def _handle_http_exception(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        # If the detail is already a dict with "code"/"message", keep it.
        # Otherwise, wrap the string detail in the standard shape.
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", "http_error")
            message = exc.detail.get("message", str(exc.detail))
            details = exc.detail.get("details")
        else:
            code = "http_error"
            message = str(exc.detail)
            details = None

        logger.info(
            "api_http_exception",
            method=request.method,
            path=request.url.path,
            status_code=exc.status_code,
        )

        return _error_response(
            status_code=exc.status_code,
            code=code,
            message=message,
            details=details,
        )

    # --------------------------------------------------------
    # 4. Catch-all for unexpected exceptions
    # --------------------------------------------------------
    @app.exception_handler(Exception)
    async def _handle_unexpected(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        # Always log the full traceback server-side.
        logger.exception(
            "api_unhandled_exception",
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
        )

        # In development, include the exception details to speed up
        # debugging. In production, return a generic message.
        details = None
        if settings.is_development:
            details = {
                "type": type(exc).__name__,
                "message": str(exc),
            }

        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected internal error occurred.",
            details=details,
        )


__all__ = ["register_exception_handlers"]
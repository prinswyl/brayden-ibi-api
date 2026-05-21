"""
FastAPI application factory.

The app is created by create_app() which:
  1. Registers middleware (in reverse execution order due to Starlette stacking).
  2. Attaches the global exception handlers.
  3. Mounts the versioned API router.
  4. Manages the database lifecycle through the async lifespan context.

Import the module-level `app` instance when running with uvicorn:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.config import get_settings
from app.database import close_db, init_db
from app.events.handlers import on_shutdown, on_startup
from app.middleware.logging import StructuredLoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.routers.api import api_router
from app.services.supabase_admin import SupabaseAdminError
from app.shared.exceptions import BraydenIBIException
from app.shared.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    logger.info(
        "Starting Brayden IBI API",
        version="0.1.0",
        environment=settings.environment,
    )

    init_db()
    await on_startup()
    logger.info("Application startup complete — accepting requests")

    yield

    logger.info("Shutting down Brayden IBI API")
    await on_shutdown()
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Brayden IBI API",
        description=(
            "Enterprise Workforce Infrastructure Platform for Multi-Academy Trusts. "
            "Provides internal staff bank management, compliance tracking, booking, "
            "timesheet management, and payroll export workflows."
        ),
        version="0.1.0",
        # Disable docs in production — enable behind auth if needed later
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    # Starlette wraps middleware in reverse registration order, so the first
    # registered here is the outermost (last to process the request,
    # first to process the response).
    #
    # Execution order (request → response):
    #   CORSMiddleware → SecurityHeaders → RequestID → StructuredLogging → route

    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[settings.request_id_header],
    )

    # ── Exception handlers ────────────────────────────────────────────────────

    @app.exception_handler(BraydenIBIException)
    async def brayden_exception_handler(
        request: Request, exc: BraydenIBIException
    ) -> ORJSONResponse:
        logger.warning(
            "application_exception",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            path=str(request.url),
        )
        return ORJSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(SupabaseAdminError)
    async def supabase_admin_error_handler(
        request: Request, exc: SupabaseAdminError
    ) -> ORJSONResponse:
        logger.error("supabase_admin_error", message=str(exc), path=str(request.url))
        return ORJSONResponse(
            status_code=exc.status_code,
            content={"error": "EMAIL_DELIVERY_FAILED", "message": str(exc), "details": None},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> ORJSONResponse:
        logger.exception("unhandled_exception", path=str(request.url))
        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": None,
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


app = create_app()

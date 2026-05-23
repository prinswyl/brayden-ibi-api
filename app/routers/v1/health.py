"""
Health and readiness endpoints.

These routes are intentionally excluded from authentication requirements —
they must be reachable by load balancers and container orchestrators.

  GET /api/v1/health        — lightweight liveness probe (no DB call)
  GET /api/v1/health/db     — database connectivity check
  GET /api/v1/health/ready  — full readiness gate (all critical dependencies)
"""

import time

import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import get_engine
from app.schemas.health import DBHealthStatus, HealthStatus, ReadinessStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])

_VERSION = "0.1.0"


@router.api_route("", methods=["GET", "HEAD"], response_model=HealthStatus, summary="Liveness probe")
async def health() -> HealthStatus:
    """Returns 200 immediately — used by load balancers and uptime monitors."""
    settings = get_settings()
    return HealthStatus(
        status="ok",
        version=_VERSION,
        environment=settings.environment,
    )


@router.get("/db", response_model=DBHealthStatus, summary="Database connectivity")
async def health_db() -> DBHealthStatus:
    """Executes SELECT 1 against the database and returns latency."""
    try:
        engine = get_engine()
        start = time.perf_counter()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return DBHealthStatus(status="ok", latency_ms=latency_ms)
    except Exception as exc:
        logger.error("Database health check failed", error=str(exc))
        return DBHealthStatus(status="unavailable", error="Database unreachable")


@router.get("/ready", response_model=ReadinessStatus, summary="Readiness probe")
async def health_ready() -> ReadinessStatus:
    """
    Composite readiness check. Returns 200 only when all critical dependencies
    are available. Used by Kubernetes readinessProbe / ECS health checks.
    """
    checks: dict[str, str] = {}
    overall_ready = True

    # Database
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Readiness: database check failed", error=str(exc))
        checks["database"] = "unavailable"
        overall_ready = False

    return ReadinessStatus(
        status="ready" if overall_ready else "not_ready",
        checks=checks,
    )

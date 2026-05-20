"""
Application startup and shutdown event handlers.

These are called from the FastAPI lifespan context in app/main.py.
Add any resource initialisation / teardown here — connection pool warmup,
cache priming, background scheduler start/stop, etc.
"""

import structlog
from sqlalchemy import text

from app.database import get_engine

logger = structlog.get_logger(__name__)


async def on_startup() -> None:
    """Run once when the application starts accepting requests."""
    await _warm_db_pool()


async def on_shutdown() -> None:
    """Run once when the application is shutting down."""
    logger.info("Running shutdown handlers")


async def _warm_db_pool() -> None:
    """
    Open a single test connection to validate DB connectivity and
    pre-warm the connection pool before the first real request arrives.
    """
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection pool warmed up")
    except Exception as exc:
        logger.error("Database connectivity check failed", error=str(exc))
        raise

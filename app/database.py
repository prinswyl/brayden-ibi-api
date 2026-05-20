"""
Async database engine and session factory.

Lifecycle:
  - init_db() is called once in the FastAPI lifespan (startup).
  - close_db() is called once in the lifespan (shutdown).
  - get_session_factory() returns the shared session factory used by dependencies.

The RLS session variables (trust_id, user_id) are NOT set here —
they are set per-request by app/core/dependencies.py::get_db().
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """Initialise the engine and session factory from application settings."""
    global _engine, _session_factory

    from app.config import get_settings

    settings = get_settings()

    _engine = create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_pre_ping=True,
        echo=settings.debug,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def close_db() -> None:
    """Dispose of the connection pool on shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine not initialised. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory not initialised. Call init_db() first.")
    return _session_factory

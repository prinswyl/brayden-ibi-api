"""
Core FastAPI dependencies for database session management with RLS.

get_db() creates an async SQLAlchemy session and immediately sets the
PostgreSQL session variables that activate Row Level Security policies:

  app.current_trust_id  — restricts every SELECT/INSERT/UPDATE/DELETE to
                          rows belonging to the authenticated trust.
  app.current_user_id   — available for audit triggers / policies.
  app.is_superadmin     — when 'true', bypass policies allow full access.

These variables are LOCAL to the transaction so they are automatically
cleared when the connection returns to the pool.
"""

from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.database import get_session_factory
from app.shared.constants import PG_VAR_IS_SUPERADMIN, PG_VAR_TRUST_ID, PG_VAR_USER_ID

logger = structlog.get_logger(__name__)


async def get_db(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Tenant-isolated database session dependency.

    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        await _apply_rls_context(session, current_user)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_superadmin_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Unrestricted database session — for platform-level operations only.
    No RLS variables are set; relies on the superadmin Postgres role.

    Only inject this dependency into routes already protected by
    require_superadmin() or equivalent.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_public_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Unauthenticated database session for public endpoints (e.g. worker
    self-registration). No auth dependency or RLS context is set — callers
    that need RLS must execute set_config() statements manually.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _apply_rls_context(session: AsyncSession, user: CurrentUser) -> None:
    """Execute SET LOCAL statements to activate RLS for this session."""
    stmts = [
        text(f"SELECT set_config('{PG_VAR_TRUST_ID}', :trust_id, true)").bindparams(
            trust_id=str(user.trust_id)
        ),
        text(f"SELECT set_config('{PG_VAR_USER_ID}', :user_id, true)").bindparams(
            user_id=str(user.user_id)
        ),
        text(f"SELECT set_config('{PG_VAR_IS_SUPERADMIN}', :is_sa, true)").bindparams(
            is_sa="true" if user.is_superadmin else "false"
        ),
    ]
    for stmt in stmts:
        await session.execute(stmt)

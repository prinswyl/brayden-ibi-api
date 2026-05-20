"""
Pytest fixtures for the Brayden IBI test suite.

Test isolation strategy:
  - Each test runs inside a database transaction that is rolled back at teardown.
  - The RLS session variables are set to a deterministic test trust_id so
    all queries behave identically to production multi-tenant queries.
  - JWT tokens are generated locally using the test JWT secret — no Supabase
    network calls are made in tests.
"""

import os
# Force ENVIRONMENT=test before any app imports so pydantic-settings picks it up.
os.environ["ENVIRONMENT"] = "test"

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.main import create_app
from app.models.base import Base
import app.models  # ensure all ORM classes are registered on Base.metadata  # noqa: F401
from app.shared.constants import ROLE_TRUST_ADMIN, ROLE_WORKER

# ── Fixtures ──────────────────────────────────────────────────────────────────

TEST_TRUST_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
TEST_SCHOOL_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest_asyncio.fixture(scope="session")
async def engine(settings):
    """Create an async engine connected to the test database.
    NullPool disables connection reuse — required on Python 3.14 where asyncpg
    raises 'another operation is in progress' if connections are recycled.

    We do NOT call create_all/drop_all here — the schema is managed by Alembic
    migrations on the real database. Test data isolation is handled per-test
    via transaction rollback in db_session."""
    _engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Transactional test session — rolls back after each test.
    RLS session variables are pre-set to test values.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        # Batch all session-variable sets into one round-trip to avoid
        # asyncpg "another operation is in progress" errors on Python 3.14.
        await session.execute(
            sa_text("""
                SELECT
                    set_config('app.current_trust_id', :trust_id, true),
                    set_config('app.current_user_id',  :user_id,  true),
                    set_config('app.is_superadmin',    'true',    true)
            """),
            {"trust_id": str(TEST_TRUST_ID), "user_id": str(TEST_USER_ID)},
        )
        # Seed the minimal rows needed to satisfy FK constraints.
        # All inserts are inside this transaction and rolled back after each test.
        await session.execute(sa_text("""
            INSERT INTO trusts (id, name, slug, status, contact_email, country, subscription_tier, settings, created_at, updated_at)
            VALUES (:id, 'Test Trust', 'test-trust', 'active', 'trust@test.example.com', 'GB', 'starter', '{}', now(), now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_TRUST_ID)})
        await session.execute(sa_text("""
            INSERT INTO users (id, trust_id, email, first_name, last_name, status, created_at, updated_at)
            VALUES (:id, :trust_id, 'admin@test.example.com', 'Test', 'Admin', 'active', now(), now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_USER_ID), "trust_id": str(TEST_TRUST_ID)})
        await session.execute(sa_text("""
            INSERT INTO users (id, trust_id, email, first_name, last_name, status, created_at, updated_at)
            VALUES (:id, :trust_id, 'hr@test.example.com', 'HR', 'Manager', 'active', now(), now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_HR_USER_ID), "trust_id": str(TEST_TRUST_ID)})
        await session.execute(sa_text("""
            INSERT INTO users (id, trust_id, email, first_name, last_name, status, created_at, updated_at)
            VALUES (:id, :trust_id, 'worker@test.example.com', 'Test', 'Worker', 'active', now(), now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_WORKER_USER_ID), "trust_id": str(TEST_TRUST_ID)})
        await session.execute(sa_text("""
            INSERT INTO users (id, trust_id, email, first_name, last_name, status, created_at, updated_at)
            VALUES (:id, :trust_id, 'leader@test.example.com', 'School', 'Leader', 'active', now(), now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_SCHOOL_LEADER_USER_ID), "trust_id": str(TEST_TRUST_ID)})
        await session.execute(sa_text("""
            INSERT INTO schools (id, trust_id, name, is_active, settings, created_at, updated_at)
            VALUES (:id, :trust_id, 'Test School', true, '{}', now(), now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_SCHOOL_ID), "trust_id": str(TEST_TRUST_ID)})
        await session.execute(sa_text("""
            INSERT INTO worker_role_types (id, trust_id, name, is_active, created_at)
            VALUES (:id, :trust_id, 'Teaching Assistant', true, now())
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(TEST_ROLE_TYPE_ID), "trust_id": str(TEST_TRUST_ID)})
        try:
            yield session
        finally:
            await session.rollback()


# Import here to avoid circular import at module level
from sqlalchemy import text as sa_text  # noqa: E402


def make_jwt(
    user_id: uuid.UUID = TEST_USER_ID,
    trust_id: uuid.UUID = TEST_TRUST_ID,
    roles: list[str] | None = None,
    *,
    expired: bool = False,
) -> str:
    """Generate a signed test JWT without calling Supabase."""
    settings = get_settings()
    import time

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": "test@example.com",
        "trust_id": str(trust_id),
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": (now - 60) if expired else (now + 3600),
        "app_metadata": {"roles": roles or [ROLE_TRUST_ADMIN]},
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def trust_admin_token() -> str:
    return make_jwt(roles=[ROLE_TRUST_ADMIN])


@pytest.fixture
def worker_token() -> str:
    return make_jwt(roles=[ROLE_WORKER])


@pytest.fixture
def expired_token() -> str:
    return make_jwt(expired=True)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTPX async test client with the DB dependency overridden to use the
    transactional test session (so tests never commit to the real DB).
    """
    app: FastAPI = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ── Compliance Vault fixtures ─────────────────────────────────────────────────

TEST_HR_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
TEST_WORKER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000011")
TEST_WORKER_PROFILE_ID = uuid.UUID("00000000-0000-0000-0000-000000000012")

# ── Bookings & Timesheets fixtures ────────────────────────────────────────────

TEST_ROLE_TYPE_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")
TEST_SCHOOL_LEADER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000021")


@pytest.fixture
def hr_manager_token() -> str:
    from app.shared.constants import ROLE_HR_MANAGER
    return make_jwt(user_id=TEST_HR_USER_ID, roles=[ROLE_HR_MANAGER])


@pytest.fixture
def hr_current_user() -> CurrentUser:
    from app.shared.constants import ROLE_HR_MANAGER
    return CurrentUser(
        user_id=TEST_HR_USER_ID,
        trust_id=TEST_TRUST_ID,
        email="hr@test.example.com",
        roles=[ROLE_HR_MANAGER],
    )


@pytest.fixture
def trust_admin_current_user() -> CurrentUser:
    return CurrentUser(
        user_id=TEST_USER_ID,
        trust_id=TEST_TRUST_ID,
        email="admin@test.example.com",
        roles=[ROLE_TRUST_ADMIN],
    )


@pytest.fixture
def school_leader_token() -> str:
    from app.shared.constants import ROLE_SCHOOL_LEADER
    return make_jwt(user_id=TEST_SCHOOL_LEADER_USER_ID, roles=[ROLE_SCHOOL_LEADER])


@pytest.fixture
def school_leader_current_user() -> CurrentUser:
    from app.shared.constants import ROLE_SCHOOL_LEADER
    return CurrentUser(
        user_id=TEST_SCHOOL_LEADER_USER_ID,
        trust_id=TEST_TRUST_ID,
        email="leader@test.example.com",
        roles=[ROLE_SCHOOL_LEADER],
    )


@pytest.fixture
def cover_supervisor_token() -> str:
    from app.shared.constants import ROLE_COVER_SUPERVISOR
    return make_jwt(user_id=TEST_SCHOOL_LEADER_USER_ID, roles=[ROLE_COVER_SUPERVISOR])


@pytest.fixture
def cover_supervisor_current_user() -> CurrentUser:
    from app.shared.constants import ROLE_COVER_SUPERVISOR
    return CurrentUser(
        user_id=TEST_SCHOOL_LEADER_USER_ID,
        trust_id=TEST_TRUST_ID,
        email="leader@test.example.com",
        roles=[ROLE_COVER_SUPERVISOR],
    )


@pytest.fixture
def worker_current_user() -> CurrentUser:
    return CurrentUser(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        email="worker@test.example.com",
        roles=[ROLE_WORKER],
    )

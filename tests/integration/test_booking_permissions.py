"""
Permission enforcement tests for Bookings & Timesheets endpoints.

Tests are at the HTTP layer so the router's require_permission() dependencies
are exercised, which is where access control actually lives.

Role permission summary (from app/core/permissions.py):
  trust_admin   — wildcard (all permissions)
  school_leader — bookings:read/create/cancel, timesheets:read/approve/reject
  hr_manager    — bookings:read/create, timesheets:read (no confirm/cancel/approve)
  worker        — availability:read/write, bookings:read, timesheets:read/submit
"""

import uuid
import pytest
from datetime import date, timedelta
from httpx import AsyncClient

from tests.conftest import make_jwt, TEST_TRUST_ID, TEST_SCHOOL_ID, TEST_ROLE_TYPE_ID
from app.shared.constants import (
    ROLE_WORKER, ROLE_HR_MANAGER, ROLE_SCHOOL_LEADER, ROLE_TRUST_ADMIN,
    ROLE_COVER_SUPERVISOR, ROLE_RECEPTIONIST,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def trust_admin_token() -> str:
    return make_jwt(roles=[ROLE_TRUST_ADMIN])


@pytest.fixture
def school_leader_token_perm() -> str:
    return make_jwt(roles=[ROLE_SCHOOL_LEADER])


@pytest.fixture
def cover_supervisor_token_perm() -> str:
    return make_jwt(roles=[ROLE_COVER_SUPERVISOR])


@pytest.fixture
def receptionist_token_perm() -> str:
    return make_jwt(roles=[ROLE_RECEPTIONIST])


@pytest.fixture
def hr_token() -> str:
    return make_jwt(roles=[ROLE_HR_MANAGER])


@pytest.fixture
def worker_token_perm() -> str:
    return make_jwt(roles=[ROLE_WORKER])


_BOOKING_BODY = {
    "school_id": str(TEST_SCHOOL_ID),
    "role_type_id": str(TEST_ROLE_TYPE_ID),
    "shift_date": str(date.today() + timedelta(days=30)),
    "start_time": "09:00:00",
    "end_time": "15:00:00",
    "agreed_hourly_rate": "12.50",
    "dispatch_mode": "broadcast",
}


# ── Unauthenticated ───────────────────────────────────────────────────────────

class TestUnauthenticated:
    @pytest.mark.asyncio
    async def test_list_bookings_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/bookings")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_create_booking_requires_auth(self, client: AsyncClient):
        r = await client.post("/api/v1/bookings", json=_BOOKING_BODY)
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_shifts_dashboard_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/shifts/dashboard")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_timesheets_list_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/timesheets")
        assert r.status_code == 401


# ── Worker role restrictions ──────────────────────────────────────────────────

class TestWorkerRestrictions:
    @pytest.mark.asyncio
    async def test_worker_cannot_create_booking(self, client: AsyncClient, worker_token_perm: str):
        r = await client.post(
            "/api/v1/bookings",
            json=_BOOKING_BODY,
            headers={"Authorization": f"Bearer {worker_token_perm}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_worker_can_list_bookings(self, client: AsyncClient, worker_token_perm: str):
        # Workers have bookings:read
        r = await client.get(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {worker_token_perm}"},
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_worker_cannot_approve_timesheet(self, client: AsyncClient, worker_token_perm: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/timesheets/{fake_id}/approve",
            headers={"Authorization": f"Bearer {worker_token_perm}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_worker_cannot_cancel_booking(self, client: AsyncClient, worker_token_perm: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/bookings/{fake_id}/cancel",
            json={"reason": "Worker cancels."},
            headers={"Authorization": f"Bearer {worker_token_perm}"},
        )
        assert r.status_code == 403


# ── HR Manager restrictions ───────────────────────────────────────────────────

class TestHRManagerRestrictions:
    @pytest.mark.asyncio
    async def test_hr_can_list_bookings(self, client: AsyncClient, hr_token: str):
        r = await client.get(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_hr_cannot_cancel_booking(self, client: AsyncClient, hr_token: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/bookings/{fake_id}/cancel",
            json={"reason": "HR cancels."},
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_hr_cannot_approve_timesheet(self, client: AsyncClient, hr_token: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/timesheets/{fake_id}/approve",
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert r.status_code == 403


# ── School Leader access (read-only) ─────────────────────────────────────────

class TestSchoolLeaderAccess:
    @pytest.mark.asyncio
    async def test_school_leader_can_list_bookings(self, client: AsyncClient, school_leader_token_perm: str):
        r = await client.get(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {school_leader_token_perm}"},
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_school_leader_cannot_create_booking(self, client: AsyncClient, school_leader_token_perm: str):
        r = await client.post(
            "/api/v1/bookings",
            json=_BOOKING_BODY,
            headers={"Authorization": f"Bearer {school_leader_token_perm}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_school_leader_cannot_approve_timesheet(self, client: AsyncClient, school_leader_token_perm: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/timesheets/{fake_id}/approve",
            headers={"Authorization": f"Bearer {school_leader_token_perm}"},
        )
        assert r.status_code == 403


# ── Cover Supervisor access ───────────────────────────────────────────────────

class TestCoverSupervisorAccess:
    @pytest.mark.asyncio
    async def test_cover_supervisor_can_create_booking(self, client: AsyncClient, cover_supervisor_token_perm: str):
        # 422/404 = auth passed, downstream validation failed (no seeded FK in HTTP test context)
        r = await client.post(
            "/api/v1/bookings",
            json=_BOOKING_BODY,
            headers={"Authorization": f"Bearer {cover_supervisor_token_perm}"},
        )
        assert r.status_code in (201, 422, 404)

    @pytest.mark.asyncio
    async def test_cover_supervisor_can_approve_timesheet(self, client: AsyncClient, cover_supervisor_token_perm: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/timesheets/{fake_id}/approve",
            headers={"Authorization": f"Bearer {cover_supervisor_token_perm}"},
        )
        assert r.status_code in (200, 404, 422)  # 403 = auth failed

    @pytest.mark.asyncio
    async def test_cover_supervisor_can_cancel_booking(self, client: AsyncClient, cover_supervisor_token_perm: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/bookings/{fake_id}/cancel",
            json={"reason": "Supervisor cancels."},
            headers={"Authorization": f"Bearer {cover_supervisor_token_perm}"},
        )
        assert r.status_code in (200, 404, 422)  # 403 = auth failed


# ── Receptionist access ───────────────────────────────────────────────────────

class TestReceptionistAccess:
    @pytest.mark.asyncio
    async def test_receptionist_can_verify_first_shift(self, client: AsyncClient, receptionist_token_perm: str):
        # 422 = auth passed, body validation failed — that's fine for a permission test
        r = await client.post(
            "/api/v1/verification/first-shift",
            json={
                "worker_id": str(uuid.uuid4()),
                "school_id": str(uuid.uuid4()),
                "dbs_seen_and_matched": True,
            },
            headers={"Authorization": f"Bearer {receptionist_token_perm}"},
        )
        assert r.status_code in (201, 404, 422)  # 403 = auth failed

    @pytest.mark.asyncio
    async def test_receptionist_cannot_create_booking(self, client: AsyncClient, receptionist_token_perm: str):
        r = await client.post(
            "/api/v1/bookings",
            json=_BOOKING_BODY,
            headers={"Authorization": f"Bearer {receptionist_token_perm}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_receptionist_cannot_approve_timesheet(self, client: AsyncClient, receptionist_token_perm: str):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/timesheets/{fake_id}/approve",
            headers={"Authorization": f"Bearer {receptionist_token_perm}"},
        )
        assert r.status_code == 403


# ── Trust Admin full access ───────────────────────────────────────────────────

class TestTrustAdminAccess:
    @pytest.mark.asyncio
    async def test_trust_admin_can_list_bookings(self, client: AsyncClient, trust_admin_token: str):
        r = await client.get(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {trust_admin_token}"},
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_trust_admin_can_view_dashboard(self, client: AsyncClient, trust_admin_token: str):
        r = await client.get(
            "/api/v1/shifts/dashboard",
            headers={"Authorization": f"Bearer {trust_admin_token}"},
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_trust_admin_can_list_timesheets(self, client: AsyncClient, trust_admin_token: str):
        r = await client.get(
            "/api/v1/timesheets",
            headers={"Authorization": f"Bearer {trust_admin_token}"},
        )
        assert r.status_code == 200

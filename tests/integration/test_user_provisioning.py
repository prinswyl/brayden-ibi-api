"""
Integration tests for User Provisioning endpoints.

Covers:
  - Invite user (POST /users/invite)
  - List users (GET /users)
  - Get user with assignments (GET /users/{id})
  - Assign a role (POST /users/{id}/assignments)
  - Revoke a role (DELETE /users/{id}/assignments/{asgn_id})
  - Deactivate a user (DELETE /users/{id})
  - Permission enforcement (non-admin cannot invite/manage users)
  - Validation — trust-wide role with school_id, school-scoped without school_id

Tests mock the Supabase Admin invite call so no network is required.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import make_jwt, TEST_TRUST_ID, TEST_SCHOOL_ID
from app.shared.constants import (
    ROLE_TRUST_ADMIN,
    ROLE_COVER_SUPERVISOR,
    ROLE_HR_MANAGER,
    ROLE_WORKER,
    ROLE_RECEPTIONIST,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _admin_headers() -> dict:
    return {"Authorization": f"Bearer {make_jwt(roles=[ROLE_TRUST_ADMIN])}"}


def _worker_headers() -> dict:
    return {"Authorization": f"Bearer {make_jwt(roles=[ROLE_WORKER])}"}


def _new_email() -> str:
    return f"user_{uuid.uuid4().hex[:8]}@test.example.com"


# Patch target — supabase invite in the service module
_INVITE_PATCH = "app.services.user_provisioning.SupabaseAdminService.invite_user_by_email"


# ── Invite ────────────────────────────────────────────────────────────────────

class TestInviteUser:
    @pytest.mark.asyncio
    async def test_trust_admin_can_invite_trust_wide_role(self, client: AsyncClient):
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            r = await client.post(
                "/api/v1/users/invite",
                json={
                    "email": _new_email(),
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "role": ROLE_HR_MANAGER,
                    "school_id": None,
                },
                headers=_admin_headers(),
            )
        assert r.status_code == 201
        data = r.json()
        assert data["email"].endswith("@test.example.com")
        assert data["status"] == "invited"

    @pytest.mark.asyncio
    async def test_trust_admin_can_invite_school_scoped_role(self, client: AsyncClient):
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            r = await client.post(
                "/api/v1/users/invite",
                json={
                    "email": _new_email(),
                    "first_name": "Sam",
                    "last_name": "Smith",
                    "role": ROLE_COVER_SUPERVISOR,
                    "school_id": str(TEST_SCHOOL_ID),
                },
                headers=_admin_headers(),
            )
        assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_worker_cannot_invite(self, client: AsyncClient):
        r = await client.post(
            "/api/v1/users/invite",
            json={
                "email": _new_email(),
                "first_name": "X",
                "last_name": "Y",
                "role": ROLE_WORKER,
                "school_id": None,
            },
            headers=_worker_headers(),
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_invite(self, client: AsyncClient):
        r = await client.post(
            "/api/v1/users/invite",
            json={
                "email": _new_email(),
                "first_name": "X",
                "last_name": "Y",
                "role": ROLE_WORKER,
                "school_id": None,
            },
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_409(self, client: AsyncClient):
        email = _new_email()
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "A", "last_name": "B", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
            r = await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "A", "last_name": "B", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_trust_wide_role_with_school_id_returns_422(self, client: AsyncClient):
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            r = await client.post(
                "/api/v1/users/invite",
                json={
                    "email": _new_email(),
                    "first_name": "X",
                    "last_name": "Y",
                    "role": ROLE_HR_MANAGER,
                    "school_id": str(TEST_SCHOOL_ID),
                },
                headers=_admin_headers(),
            )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_school_scoped_role_without_school_id_returns_422(self, client: AsyncClient):
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            r = await client.post(
                "/api/v1/users/invite",
                json={
                    "email": _new_email(),
                    "first_name": "X",
                    "last_name": "Y",
                    "role": ROLE_COVER_SUPERVISOR,
                    "school_id": None,
                },
                headers=_admin_headers(),
            )
        assert r.status_code == 422


# ── List users ────────────────────────────────────────────────────────────────

class TestListUsers:
    @pytest.mark.asyncio
    async def test_trust_admin_can_list_users(self, client: AsyncClient):
        r = await client.get("/api/v1/users", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_worker_cannot_list_users(self, client: AsyncClient):
        r = await client.get("/api/v1/users", headers=_worker_headers())
        assert r.status_code == 403


# ── Get user ──────────────────────────────────────────────────────────────────

class TestGetUser:
    @pytest.mark.asyncio
    async def test_get_existing_user_returns_assignments(self, client: AsyncClient):
        email = _new_email()
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            create_resp = await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "T", "last_name": "U", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
        user_id = create_resp.json()["id"]

        r = await client.get(f"/api/v1/users/{user_id}", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == user_id
        assert len(data["assignments"]) >= 1
        assert data["assignments"][0]["role"] == ROLE_HR_MANAGER

    @pytest.mark.asyncio
    async def test_get_nonexistent_user_returns_404(self, client: AsyncClient):
        r = await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=_admin_headers())
        assert r.status_code == 404


# ── Assign / revoke role ──────────────────────────────────────────────────────

class TestAssignRevokeRole:
    @pytest.mark.asyncio
    async def test_assign_additional_role_to_user(self, client: AsyncClient):
        email = _new_email()
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            create_resp = await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "A", "last_name": "B", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
        user_id = create_resp.json()["id"]

        r = await client.post(
            f"/api/v1/users/{user_id}/assignments",
            json={"role": ROLE_COVER_SUPERVISOR, "school_id": str(TEST_SCHOOL_ID)},
            headers=_admin_headers(),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["role"] == ROLE_COVER_SUPERVISOR
        assert data["school_id"] == str(TEST_SCHOOL_ID)

    @pytest.mark.asyncio
    async def test_duplicate_assignment_returns_409(self, client: AsyncClient):
        email = _new_email()
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            create_resp = await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "A", "last_name": "B", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
        user_id = create_resp.json()["id"]

        r = await client.post(
            f"/api/v1/users/{user_id}/assignments",
            json={"role": ROLE_HR_MANAGER, "school_id": None},
            headers=_admin_headers(),
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_revoke_role_assignment(self, client: AsyncClient):
        email = _new_email()
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            create_resp = await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "A", "last_name": "B", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
        user_id = create_resp.json()["id"]

        # Get the assignment ID
        get_resp = await client.get(f"/api/v1/users/{user_id}", headers=_admin_headers())
        assignment_id = get_resp.json()["assignments"][0]["id"]

        r = await client.delete(
            f"/api/v1/users/{user_id}/assignments/{assignment_id}",
            headers=_admin_headers(),
        )
        assert r.status_code == 200
        assert r.json()["message"] == "Role assignment revoked."

        # Assignment should now be inactive
        get_resp2 = await client.get(f"/api/v1/users/{user_id}", headers=_admin_headers())
        active = [a for a in get_resp2.json()["assignments"] if a["is_active"]]
        assert not any(a["id"] == assignment_id for a in active)

    @pytest.mark.asyncio
    async def test_revoked_assignment_can_be_reactivated(self, client: AsyncClient):
        email = _new_email()
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            create_resp = await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "A", "last_name": "B", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
        user_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/users/{user_id}", headers=_admin_headers())
        assignment_id = get_resp.json()["assignments"][0]["id"]

        # Revoke
        await client.delete(
            f"/api/v1/users/{user_id}/assignments/{assignment_id}",
            headers=_admin_headers(),
        )

        # Re-assign same role — should reactivate, not create duplicate
        r = await client.post(
            f"/api/v1/users/{user_id}/assignments",
            json={"role": ROLE_HR_MANAGER, "school_id": None},
            headers=_admin_headers(),
        )
        assert r.status_code == 201
        assert r.json()["is_active"] is True


# ── Deactivate user ───────────────────────────────────────────────────────────

class TestDeactivateUser:
    @pytest.mark.asyncio
    async def test_deactivate_user_suspends_and_revokes_roles(self, client: AsyncClient):
        email = _new_email()
        with patch(_INVITE_PATCH, new=AsyncMock(return_value={"id": str(uuid.uuid4())})):
            create_resp = await client.post(
                "/api/v1/users/invite",
                json={"email": email, "first_name": "D", "last_name": "E", "role": ROLE_HR_MANAGER},
                headers=_admin_headers(),
            )
        user_id = create_resp.json()["id"]

        r = await client.delete(f"/api/v1/users/{user_id}", headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["message"] == "User deactivated."

        # User status should now be suspended
        get_resp = await client.get(f"/api/v1/users/{user_id}", headers=_admin_headers())
        assert get_resp.json()["status"] == "suspended"

        # All assignments inactive
        active_assignments = [
            a for a in get_resp.json()["assignments"] if a["is_active"]
        ]
        assert active_assignments == []

    @pytest.mark.asyncio
    async def test_worker_cannot_deactivate_user(self, client: AsyncClient):
        r = await client.delete(
            f"/api/v1/users/{uuid.uuid4()}",
            headers=_worker_headers(),
        )
        assert r.status_code == 403

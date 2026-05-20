"""
Permission enforcement tests for compliance vault endpoints.

Verifies that:
  - Unauthenticated requests return 401
  - Workers (no HR role) cannot access HR-only endpoints
  - HR managers can access their permitted endpoints
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_jwt, TEST_TRUST_ID, TEST_USER_ID
from app.shared.constants import ROLE_WORKER, ROLE_HR_MANAGER


@pytest.fixture
def worker_token() -> str:
    return make_jwt(roles=[ROLE_WORKER])


@pytest.fixture
def hr_token() -> str:
    return make_jwt(roles=[ROLE_HR_MANAGER])


class TestUnauthenticated:
    @pytest.mark.asyncio
    async def test_list_workers_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/workers")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/compliance/dashboard")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_review_queue_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/compliance/dashboard/review-queue")
        assert response.status_code == 401


class TestWorkerRoleRestrictions:
    @pytest.mark.asyncio
    async def test_worker_cannot_list_all_workers(self, client: AsyncClient, worker_token: str):
        response = await client.get(
            "/api/v1/workers",
            headers={"Authorization": f"Bearer {worker_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_worker_cannot_create_worker_profile(self, client: AsyncClient, worker_token: str):
        import uuid
        response = await client.post(
            "/api/v1/workers",
            json={"user_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {worker_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_worker_cannot_access_dashboard(self, client: AsyncClient, worker_token: str):
        response = await client.get(
            "/api/v1/compliance/dashboard",
            headers={"Authorization": f"Bearer {worker_token}"},
        )
        assert response.status_code == 403


class TestHRManagerAccess:
    @pytest.mark.asyncio
    async def test_hr_can_list_workers(self, client: AsyncClient, hr_token: str):
        response = await client.get(
            "/api/v1/workers",
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hr_can_access_dashboard(self, client: AsyncClient, hr_token: str):
        response = await client.get(
            "/api/v1/compliance/dashboard",
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hr_can_access_pending_review(self, client: AsyncClient, hr_token: str):
        response = await client.get(
            "/api/v1/compliance/dashboard/pending-review",
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hr_can_access_review_queue(self, client: AsyncClient, hr_token: str):
        response = await client.get(
            "/api/v1/compliance/dashboard/review-queue",
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert response.status_code == 200


class TestTrustAdminAccess:
    @pytest.mark.asyncio
    async def test_trust_admin_can_access_all_compliance_endpoints(
        self, client: AsyncClient, trust_admin_token: str
    ):
        for path in [
            "/api/v1/workers",
            "/api/v1/compliance/dashboard",
            "/api/v1/compliance/dashboard/pending-review",
            "/api/v1/compliance/dashboard/expiring-documents",
        ]:
            response = await client.get(
                path, headers={"Authorization": f"Bearer {trust_admin_token}"}
            )
            assert response.status_code == 200, f"Expected 200 for {path}, got {response.status_code}"

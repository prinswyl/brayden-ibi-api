"""
Integration tests for health endpoints.

These tests run against the real test database to verify end-to-end
connectivity. They do not require authentication.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "test"


@pytest.mark.asyncio
async def test_health_includes_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_health_propagates_request_id(client: AsyncClient) -> None:
    custom_id = "my-request-id-123"
    response = await client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_auth_me_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_rejects_expired_token(
    client: AsyncClient, expired_token: str
) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_auth_me_returns_user_identity(
    client: AsyncClient, trust_admin_token: str
) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {trust_admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "trust_id" in data
    assert "trust_admin" in data["roles"]

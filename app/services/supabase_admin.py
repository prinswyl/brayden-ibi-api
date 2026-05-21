"""
Thin async wrapper around the Supabase Management / Admin Auth API.

Used only for:
  - Inviting users (sends magic-link / invite email via Supabase Auth)
  - Setting app_metadata on an existing auth user

All other user data is stored and managed in the application's own `users`
table. This service is intentionally minimal.
"""

from uuid import UUID

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


class SupabaseAdminService:
    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.supabase_url.rstrip("/")
        self._service_key = settings.supabase_service_role_key
        self._headers = {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
        }

    async def invite_user_by_email(
        self,
        email: str,
        *,
        data: dict | None = None,
    ) -> dict:
        """
        Send a Supabase Auth invite email. Returns the created auth user object.
        `data` is stored as user_metadata on the Supabase auth.users record.
        """
        payload: dict = {"email": email}
        if data:
            payload["data"] = data

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/auth/v1/invite",
                json=payload,
                headers=self._headers,
                timeout=10.0,
            )

        if resp.status_code not in (200, 201):
            logger.error(
                "supabase_invite_failed",
                email=email,
                status=resp.status_code,
                body=resp.text,
            )
            raise SupabaseAdminError(
                f"Supabase invite failed ({resp.status_code}): {resp.text}"
            )

        return resp.json()

    async def update_user_metadata(
        self,
        auth_user_id: UUID,
        *,
        app_metadata: dict,
    ) -> None:
        """
        Patch app_metadata on an existing Supabase auth user.
        Used to force-sync roles/trust_id if the custom claims hook hasn't run yet.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base_url}/auth/v1/admin/users/{auth_user_id}",
                json={"app_metadata": app_metadata},
                headers=self._headers,
                timeout=10.0,
            )

        if resp.status_code not in (200, 201):
            logger.error(
                "supabase_metadata_update_failed",
                user_id=str(auth_user_id),
                status=resp.status_code,
            )
            raise SupabaseAdminError(
                f"Supabase metadata update failed ({resp.status_code})"
            )


class SupabaseAdminError(Exception):
    """Raised when the Supabase Admin API returns an unexpected error."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        self.status_code = status_code
        super().__init__(message)

from uuid import UUID

from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    """Response body for the /auth/me endpoint."""
    user_id: UUID
    trust_id: UUID
    email: str
    roles: list[str]
    is_superadmin: bool

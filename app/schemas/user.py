from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr

from app.schemas.base import APIModel, ORMModel, TenantedModel
from app.shared.enums import UserStatus


# ── Request schemas ───────────────────────────────────────────────────────────

class UserInviteRequest(APIModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: str
    school_id: UUID | None = None


class AssignRoleRequest(APIModel):
    role: str
    school_id: UUID | None = None


# ── Response schemas ──────────────────────────────────────────────────────────

class AssignmentResponse(ORMModel):
    id: UUID
    trust_id: UUID
    user_id: UUID
    school_id: UUID | None
    role: str
    is_active: bool
    assigned_by: UUID | None
    created_at: datetime
    updated_at: datetime


class UserResponse(TenantedModel):
    email: str
    first_name: str
    last_name: str
    phone: str | None
    status: UserStatus
    invited_by: UUID | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserWithAssignmentsResponse(UserResponse):
    assignments: list[AssignmentResponse] = []


class UserListResponse(ORMModel):
    items: list[UserResponse]
    total: int
    offset: int
    limit: int

"""
User provisioning endpoints.

  POST   /api/v1/users/invite                          — invite a new user to the trust
  GET    /api/v1/users                                 — list all users in the trust
  GET    /api/v1/users/{user_id}                       — get user profile + assignments
  DELETE /api/v1/users/{user_id}                       — deactivate user
  POST   /api/v1/users/{user_id}/assignments           — assign a role to a user
  DELETE /api/v1/users/{user_id}/assignments/{asgn_id} — revoke a role assignment
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.base import MessageResponse
from app.schemas.user import (
    AssignmentResponse,
    AssignRoleRequest,
    UserInviteRequest,
    UserListResponse,
    UserResponse,
    UserWithAssignmentsResponse,
)
from app.services.user_provisioning import UserProvisioningService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "/invite",
    response_model=UserResponse,
    status_code=201,
    summary="Invite a new user to the trust",
    dependencies=[Depends(require_permission("users:invite"))],
)
async def invite_user(
    body: UserInviteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    svc = UserProvisioningService(db)
    user = await svc.invite_user(
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        school_id=body.school_id,
        current_user=current_user,
    )
    return UserResponse.model_validate(user)


@router.get(
    "/me",
    response_model=UserWithAssignmentsResponse,
    summary="Get the currently authenticated user's own profile and assignments",
)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserWithAssignmentsResponse:
    svc = UserProvisioningService(db)
    user = await svc.get_user(current_user.user_id)
    assignments = await svc.get_user_assignments(current_user.user_id)
    user_resp = UserResponse.model_validate(user)
    return UserWithAssignmentsResponse(
        **user_resp.model_dump(),
        assignments=[AssignmentResponse.model_validate(a) for a in assignments],
    )


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users in the trust",
    dependencies=[Depends(require_permission("users:read"))],
)
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    svc = UserProvisioningService(db)
    users, total = await svc.list_users(current_user.trust_id, offset=offset, limit=limit)
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{user_id}",
    response_model=UserWithAssignmentsResponse,
    summary="Get user with their role assignments",
    dependencies=[Depends(require_permission("users:read"))],
)
async def get_user(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserWithAssignmentsResponse:
    svc = UserProvisioningService(db)
    user = await svc.get_user(user_id)
    assignments = await svc.get_user_assignments(user_id)
    user_resp = UserResponse.model_validate(user)
    return UserWithAssignmentsResponse(
        **user_resp.model_dump(),
        assignments=[AssignmentResponse.model_validate(a) for a in assignments],
    )


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Deactivate a user and revoke all their roles",
    dependencies=[Depends(require_permission("users:deactivate"))],
)
async def deactivate_user(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    svc = UserProvisioningService(db)
    await svc.deactivate_user(user_id, current_user=current_user)
    return MessageResponse(message="User deactivated.")


@router.post(
    "/{user_id}/assignments",
    response_model=AssignmentResponse,
    status_code=201,
    summary="Assign a role to a user",
    dependencies=[Depends(require_permission("users:update"))],
)
async def assign_role(
    user_id: UUID,
    body: AssignRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssignmentResponse:
    svc = UserProvisioningService(db)
    assignment = await svc.assign_role(
        user_id=user_id,
        role=body.role,
        school_id=body.school_id,
        current_user=current_user,
    )
    return AssignmentResponse.model_validate(assignment)


@router.delete(
    "/{user_id}/assignments/{assignment_id}",
    response_model=MessageResponse,
    summary="Revoke a specific role assignment",
    dependencies=[Depends(require_permission("users:update"))],
)
async def revoke_assignment(
    user_id: UUID,
    assignment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    svc = UserProvisioningService(db)
    await svc.revoke_role(assignment_id=assignment_id, current_user=current_user)
    return MessageResponse(message="Role assignment revoked.")

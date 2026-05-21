from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.models.worker import WorkerRoleType

router = APIRouter(prefix="/role-types", tags=["Role Types"])


class RoleTypeResponse(BaseModel):
    id: UUID
    trust_id: UUID
    name: str
    category: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class RoleTypeCreate(BaseModel):
    name: str
    category: str | None = None


@router.get("", response_model=list[RoleTypeResponse])
async def list_role_types(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    result = await db.execute(
        select(WorkerRoleType)
        .where(
            WorkerRoleType.trust_id == current_user.trust_id,
            WorkerRoleType.is_active == True,  # noqa: E712
        )
        .order_by(WorkerRoleType.name)
    )
    return list(result.scalars().all())


@router.post("", response_model=RoleTypeResponse, status_code=201)
async def create_role_type(
    body: RoleTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    from datetime import UTC, datetime

    role_type = WorkerRoleType(
        trust_id=current_user.trust_id,
        name=body.name,
        category=body.category,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db.add(role_type)
    await db.flush()
    await db.refresh(role_type)
    return role_type

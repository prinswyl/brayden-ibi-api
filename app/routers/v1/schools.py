"""
School management endpoints.

  GET    /api/v1/schools           — list all schools in the trust
  POST   /api/v1/schools           — add a new school
  GET    /api/v1/schools/{id}      — get a single school
  PATCH  /api/v1/schools/{id}      — update school details
  DELETE /api/v1/schools/{id}      — deactivate a school
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.repositories.school import SchoolRepository
from app.schemas.base import MessageResponse
from app.schemas.school import (
    SchoolCreateRequest,
    SchoolListResponse,
    SchoolResponse,
    SchoolUpdateRequest,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/schools", tags=["Schools"])


@router.get(
    "",
    response_model=SchoolListResponse,
    summary="List schools in the trust",
    dependencies=[Depends(require_permission("schools:read"))],
)
async def list_schools(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    active_only: bool = Query(True),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SchoolListResponse:
    repo = SchoolRepository(db)
    schools, total = await repo.list_for_trust(
        current_user.trust_id, offset=offset, limit=limit, active_only=active_only
    )
    return SchoolListResponse(
        items=[SchoolResponse.model_validate(s) for s in schools],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post(
    "",
    response_model=SchoolResponse,
    status_code=201,
    summary="Add a school to the trust",
    dependencies=[Depends(require_permission("schools:write"))],
)
async def create_school(
    body: SchoolCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    repo = SchoolRepository(db)
    school = await repo.create(trust_id=current_user.trust_id, **body.model_dump())
    logger.info("school.created", school_id=str(school.id), trust_id=str(current_user.trust_id))
    return SchoolResponse.model_validate(school)


@router.get(
    "/{school_id}",
    response_model=SchoolResponse,
    summary="Get a single school",
    dependencies=[Depends(require_permission("schools:read"))],
)
async def get_school(
    school_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    repo = SchoolRepository(db)
    school = await repo.get_for_trust(school_id, current_user.trust_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return SchoolResponse.model_validate(school)


@router.patch(
    "/{school_id}",
    response_model=SchoolResponse,
    summary="Update school details",
    dependencies=[Depends(require_permission("schools:write"))],
)
async def update_school(
    school_id: UUID,
    body: SchoolUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SchoolResponse:
    repo = SchoolRepository(db)
    school = await repo.get_for_trust(school_id, current_user.trust_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    school = await repo.update(school, **updates)
    return SchoolResponse.model_validate(school)


@router.delete(
    "/{school_id}",
    response_model=MessageResponse,
    summary="Deactivate a school",
    dependencies=[Depends(require_permission("schools:write"))],
)
async def deactivate_school(
    school_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    repo = SchoolRepository(db)
    school = await repo.get_for_trust(school_id, current_user.trust_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    await repo.update(school, is_active=False)
    return MessageResponse(message="School deactivated.")

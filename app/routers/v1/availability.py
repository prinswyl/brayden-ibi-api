from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.availability import (
    AvailabilityBulkSet,
    AvailabilityPreferencesResponse,
    AvailabilityPreferencesUpdate,
    AvailabilityResponse,
    AvailabilitySet,
)
from app.services.availability import AvailabilityService

router = APIRouter(prefix="/workers/{worker_id}/availability", tags=["availability"])


@router.put(
    "",
    response_model=AvailabilityResponse,
    dependencies=[Depends(require_permission("availability:write"))],
)
async def set_availability(
    worker_id: UUID,
    body: AvailabilitySet,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("availability:write")),
):
    svc = AvailabilityService(db)
    record = await svc.set_availability(
        worker_id=worker_id,
        trust_id=current_user.trust_id,
        available_date=body.available_date,
        is_available=body.is_available,
        am_available=body.am_available,
        pm_available=body.pm_available,
        note=body.note,
        current_user=current_user,
    )
    return record


@router.post(
    "/bulk",
    response_model=list[AvailabilityResponse],
    dependencies=[Depends(require_permission("availability:write"))],
)
async def bulk_set_availability(
    worker_id: UUID,
    body: AvailabilityBulkSet,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("availability:write")),
):
    svc = AvailabilityService(db)
    records = await svc.bulk_set_availability(
        worker_id=worker_id,
        trust_id=current_user.trust_id,
        dates=body.dates,
        is_available=body.is_available,
        current_user=current_user,
    )
    return records


@router.get(
    "",
    response_model=list[AvailabilityResponse],
    dependencies=[Depends(require_permission("availability:read"))],
)
async def get_availability(
    worker_id: UUID,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("availability:read")),
):
    svc = AvailabilityService(db)
    return await svc.get_availability(worker_id, from_date=from_date, to_date=to_date)


@router.put(
    "/preferences",
    response_model=AvailabilityPreferencesResponse,
    dependencies=[Depends(require_permission("availability:write"))],
)
async def set_preferences(
    worker_id: UUID,
    body: AvailabilityPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("availability:write")),
):
    svc = AvailabilityService(db)
    return await svc.set_preferences(
        worker_id=worker_id,
        trust_id=current_user.trust_id,
        **body.model_dump(exclude_none=True),
        current_user=current_user,
    )


@router.get(
    "/preferences",
    response_model=AvailabilityPreferencesResponse | None,
    dependencies=[Depends(require_permission("availability:read"))],
)
async def get_preferences(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("availability:read")),
):
    svc = AvailabilityService(db)
    return await svc.get_preferences(worker_id)

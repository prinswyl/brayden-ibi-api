from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.timesheet import (
    TimesheetCorrectionRequest,
    TimesheetCorrectionResponse,
    TimesheetListResponse,
    TimesheetReject,
    TimesheetResponse,
    TimesheetSubmit,
)
from app.services.timesheet import TimesheetService
from app.shared.enums import TimesheetStatus

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


@router.post("/bookings/{booking_id}", response_model=TimesheetResponse, status_code=201)
async def create_draft(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:submit")),
):
    svc = TimesheetService(db)
    return await svc.create_draft(booking_id, current_user=current_user)


@router.get("/{timesheet_id}", response_model=TimesheetResponse)
async def get_timesheet(
    timesheet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:read")),
):
    from app.repositories.timesheet import TimesheetRepository
    repo = TimesheetRepository(db)
    return await repo.get_by_id_or_404(timesheet_id)


@router.post("/{timesheet_id}/submit", response_model=TimesheetResponse)
async def submit_timesheet(
    timesheet_id: UUID,
    body: TimesheetSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:submit")),
):
    svc = TimesheetService(db)
    return await svc.submit(
        timesheet_id,
        actual_start_time=body.actual_start_time,
        actual_end_time=body.actual_end_time,
        break_minutes=body.break_minutes,
        overtime_hours=body.overtime_hours,
        worker_notes=body.worker_notes,
        current_user=current_user,
    )


@router.post("/{timesheet_id}/approve", response_model=TimesheetResponse)
async def approve_timesheet(
    timesheet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:approve")),
):
    svc = TimesheetService(db)
    return await svc.approve(timesheet_id, current_user=current_user)


@router.post("/{timesheet_id}/reject", response_model=TimesheetResponse)
async def reject_timesheet(
    timesheet_id: UUID,
    body: TimesheetReject,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:reject")),
):
    svc = TimesheetService(db)
    return await svc.reject(timesheet_id, reason=body.reason, current_user=current_user)


@router.post("/{timesheet_id}/request-correction", response_model=TimesheetResponse)
async def request_correction(
    timesheet_id: UUID,
    body: TimesheetCorrectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:approve")),
):
    svc = TimesheetService(db)
    timesheet, _ = await svc.request_correction(timesheet_id, reason=body.reason, current_user=current_user)
    return timesheet


@router.get("/{timesheet_id}/corrections", response_model=list[TimesheetCorrectionResponse])
async def list_corrections(
    timesheet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:read")),
):
    svc = TimesheetService(db)
    return await svc.get_corrections(timesheet_id)


@router.get("", response_model=TimesheetListResponse)
async def list_timesheets(
    status: TimesheetStatus | None = Query(None),
    school_id: UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:read")),
):
    from app.repositories.timesheet import TimesheetRepository
    repo = TimesheetRepository(db)
    filters = {k: v for k, v in {"status": status, "school_id": school_id}.items() if v is not None}
    items, total = await repo.list_all(filters=filters or None, offset=offset, limit=limit)
    return TimesheetListResponse(items=items, total=total, offset=offset, limit=limit)

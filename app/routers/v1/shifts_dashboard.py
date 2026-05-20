from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.booking import BookingListResponse
from app.schemas.timesheet import TimesheetListResponse
from app.services.booking_dashboard import BookingDashboardService

router = APIRouter(prefix="/shifts", tags=["shifts-dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    svc = BookingDashboardService(db)
    return await svc.get_summary(current_user.trust_id)


@router.get("/open", response_model=BookingListResponse)
async def get_open_shifts(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    svc = BookingDashboardService(db)
    items, total = await svc.get_open_shifts(current_user.trust_id, offset=offset, limit=limit)
    return BookingListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/pending-timesheets", response_model=TimesheetListResponse)
async def get_pending_timesheets(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("timesheets:read")),
):
    svc = BookingDashboardService(db)
    items, total = await svc.get_pending_timesheets(current_user.trust_id, offset=offset, limit=limit)
    return TimesheetListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/no-shows", response_model=BookingListResponse)
async def get_no_shows(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    svc = BookingDashboardService(db)
    items, total = await svc.get_no_shows(
        current_user.trust_id, from_date=from_date, to_date=to_date, offset=offset, limit=limit
    )
    return BookingListResponse(items=items, total=total, offset=offset, limit=limit)

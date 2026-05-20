from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.booking import BookingResponse
from app.services.attendance import AttendanceService
from app.shared.enums import BookingStatus

router = APIRouter(prefix="/bookings/{booking_id}/attendance", tags=["attendance"])


class CompleteShiftRequest(BaseModel):
    check_out_time: datetime | None = None


class NoShowRequest(BaseModel):
    reason: str | None = None


class ManualOverrideRequest(BaseModel):
    target_status: BookingStatus
    reason: str


@router.post("/check-in", response_model=BookingResponse)
async def check_in(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = AttendanceService(db)
    return await svc.check_in(booking_id, current_user=current_user)


@router.post("/complete", response_model=BookingResponse)
async def complete_shift(
    booking_id: UUID,
    body: CompleteShiftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = AttendanceService(db)
    return await svc.complete_shift(booking_id, check_out_time=body.check_out_time, current_user=current_user)


@router.post("/no-show", response_model=BookingResponse)
async def record_no_show(
    booking_id: UUID,
    body: NoShowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = AttendanceService(db)
    return await svc.record_no_show(booking_id, reason=body.reason, current_user=current_user)


@router.post("/override", response_model=BookingResponse)
async def manual_override(
    booking_id: UUID,
    body: ManualOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = AttendanceService(db)
    return await svc.manual_override(
        booking_id, target_status=body.target_status, reason=body.reason, current_user=current_user
    )

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.booking import (
    AcceptOfferRequest,
    BookingCreate,
    BookingListResponse,
    BookingOfferResponse,
    BookingResponse,
    BookingStatusHistoryResponse,
    BookingUpdate,
    CancelBookingRequest,
    DeclineOfferRequest,
    DispatchOffersRequest,
)
from app.services.booking import BookingService
from app.shared.enums import BookingStatus

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingResponse, status_code=201)
async def create_booking(
    body: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = BookingService(db)
    return await svc.create_booking(
        school_id=body.school_id,
        trust_id=current_user.trust_id,
        role_type_id=body.role_type_id,
        shift_date=body.shift_date,
        end_date=body.end_date,
        start_time=body.start_time,
        end_time=body.end_time,
        agreed_hourly_rate=body.agreed_hourly_rate,
        dispatch_mode=body.dispatch_mode,
        urgency=body.urgency,
        directed_worker_id=body.directed_worker_id,
        reason=body.reason,
        notes=body.notes,
        offer_expires_at=body.offer_expires_at,
        current_user=current_user,
    )


@router.get("", response_model=BookingListResponse)
async def list_bookings(
    status: BookingStatus | None = Query(None),
    school_id: UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    svc = BookingService(db)
    items, total = await svc.list_bookings(status=status, school_id=school_id, offset=offset, limit=limit)
    return BookingListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    svc = BookingService(db)
    return await svc.get_booking(booking_id)


@router.patch("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: UUID,
    body: BookingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = BookingService(db)
    return await svc.update_booking(booking_id, body, current_user=current_user)


@router.post("/{booking_id}/dispatch", response_model=BookingResponse)
async def dispatch_offers(
    booking_id: UUID,
    body: DispatchOffersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = BookingService(db)
    booking, _ = await svc.dispatch_offers(
        booking_id,
        school_lat=body.school_lat,
        school_lon=body.school_lon,
        current_user=current_user,
    )
    return booking


@router.post("/{booking_id}/accept", response_model=BookingResponse)
async def accept_offer(
    booking_id: UUID,
    body: AcceptOfferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    svc = BookingService(db)
    return await svc.accept_offer(booking_id, worker_id=body.worker_id, current_user=current_user)


@router.post("/{booking_id}/decline", response_model=BookingOfferResponse)
async def decline_offer(
    booking_id: UUID,
    body: DeclineOfferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    svc = BookingService(db)
    return await svc.decline_offer(
        booking_id, worker_id=body.worker_id, reason=body.reason, current_user=current_user
    )


@router.post("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:create")),
):
    svc = BookingService(db)
    return await svc.confirm_booking(booking_id, current_user=current_user)


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:cancel")),
):
    svc = BookingService(db)
    return await svc.cancel_booking(booking_id, reason=body.reason, current_user=current_user)


@router.get("/{booking_id}/offers", response_model=list[BookingOfferResponse])
async def list_offers(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    from app.repositories.booking import BookingOfferRepository
    repo = BookingOfferRepository(db)
    return await repo.list_for_booking(booking_id)


@router.get("/{booking_id}/history", response_model=list[BookingStatusHistoryResponse])
async def get_booking_history(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("bookings:read")),
):
    from sqlalchemy import select
    from app.models.booking import BookingStatusHistory
    result = await db.execute(
        select(BookingStatusHistory)
        .where(BookingStatusHistory.booking_id == booking_id)
        .order_by(BookingStatusHistory.created_at.asc())
    )
    return list(result.scalars().all())

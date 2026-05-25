"""
Booking service — state machine and dispatch orchestration.

State transitions:
  requested → offered       (dispatch_offers)
  offered   → accepted      (worker accepts)
  offered   → expired       (offer window closes)
  accepted  → confirmed     (school confirms)
  confirmed → checked_in    (attendance.check_in — see AttendanceService)
  confirmed → cancelled     (cancel)
  checked_in→ completed     (attendance.complete — see AttendanceService)
  checked_in→ no_show       (attendance.record_no_show)
  any       → cancelled     (cancel, before check-in)
  any       → rejected      (admin override)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app import core
from app.core.audit import log as audit_log
from app.core.auth import CurrentUser
from app.events import booking_events
from app.models.booking import Booking, BookingOffer
from app.repositories.booking import BookingOfferRepository, BookingRepository
from app.services.worker_matching import WorkerMatchingService
from app.shared.enums import (
    BookingOfferStatus,
    BookingStatus,
    DispatchMode,
    UrgencyLevel,
)
from app.shared.exceptions import ConflictError, NotFoundError, WorkflowError

# Valid transitions: current → allowed next states
_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.requested: {BookingStatus.offered, BookingStatus.cancelled},
    BookingStatus.offered: {
        BookingStatus.accepted,
        BookingStatus.expired,
        BookingStatus.cancelled,
    },
    BookingStatus.accepted: {
        BookingStatus.confirmed,
        BookingStatus.cancelled,
    },
    BookingStatus.confirmed: {
        BookingStatus.checked_in,
        BookingStatus.cancelled,
        BookingStatus.no_show,
    },
    BookingStatus.checked_in: {
        BookingStatus.completed,
        BookingStatus.no_show,
    },
    BookingStatus.completed: set(),
    BookingStatus.cancelled: set(),
    BookingStatus.no_show: set(),
    BookingStatus.rejected: set(),
    BookingStatus.expired: set(),
}

# Default offer window by urgency
_OFFER_EXPIRY_HOURS: dict[UrgencyLevel, int] = {
    UrgencyLevel.standard: 24,
    UrgencyLevel.urgent: 4,
    UrgencyLevel.emergency: 1,
}


def _assert_transition(current: BookingStatus, target: BookingStatus) -> None:
    allowed = _TRANSITIONS.get(current, set())
    if target not in allowed:
        raise WorkflowError(
            f"Cannot move booking status from '{current.value}' to '{target.value}'. "
            f"Allowed: {[s.value for s in allowed]}"
        )


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self._bookings = BookingRepository(session)
        self._offers = BookingOfferRepository(session)
        self._matching = WorkerMatchingService(session)
        self._session = session

    async def create_booking(
        self,
        *,
        school_id: UUID,
        trust_id: UUID,
        role_type_id: UUID,
        shift_date,
        end_date=None,
        start_time=None,
        end_time=None,
        agreed_hourly_rate: Decimal = Decimal("0"),
        dispatch_mode: DispatchMode = DispatchMode.broadcast,
        urgency: UrgencyLevel = UrgencyLevel.standard,
        directed_worker_id: UUID | None = None,
        reason: str | None = None,
        notes: str | None = None,
        offer_expires_at: datetime | None = None,
        current_user: CurrentUser,
    ) -> Booking:
        if dispatch_mode == DispatchMode.directed and not directed_worker_id:
            raise WorkflowError("Directed bookings require a worker_id.")

        if offer_expires_at is None:
            hours = _OFFER_EXPIRY_HOURS[urgency]
            offer_expires_at = datetime.now(UTC) + timedelta(hours=hours)

        booking = await self._bookings.create(
            trust_id=trust_id,
            school_id=school_id,
            role_type_id=role_type_id,
            requested_by=current_user.user_id,
            shift_date=shift_date,
            end_date=end_date or shift_date,
            start_time=start_time,
            end_time=end_time,
            dispatch_mode=dispatch_mode,
            urgency=urgency,
            agreed_hourly_rate=agreed_hourly_rate,
            offer_expires_at=offer_expires_at,
            status=BookingStatus.requested,
            reason=reason,
            notes=notes,
            worker_id=directed_worker_id,
        )

        await self._bookings.write_status_history(
            booking.id, trust_id, None, BookingStatus.requested, current_user.user_id
        )
        await audit_log(
            self._session, action=core.audit.AuditAction.create,
            resource_type="bookings", resource_id=booking.id,
            trust_id=trust_id, user_id=current_user.user_id,
            school_id=school_id,
            new_values={"status": BookingStatus.requested.value, "dispatch_mode": dispatch_mode.value},
        )

        await booking_events.dispatch(booking_events.BookingCreatedEvent(
            booking_id=booking.id, trust_id=trust_id, school_id=school_id,
            role_type_id=role_type_id, shift_date=str(shift_date),
            dispatch_mode=dispatch_mode.value, requested_by=current_user.user_id,
            occurred_at=datetime.now(UTC),
        ))
        return booking

    async def update_booking(
        self,
        booking_id: UUID,
        body,
        *,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)
        updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
        if not updates:
            return booking
        old_values = {k: getattr(booking, k) for k in updates}
        booking = await self._bookings.update(booking, **updates)
        await audit_log(
            self._session, action=core.audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            old_values={str(k): str(v) for k, v in old_values.items()},
            new_values={str(k): str(v) for k, v in updates.items()},
        )
        return booking

    async def dispatch_offers(
        self,
        booking_id: UUID,
        *,
        school_lat: Decimal | None = None,
        school_lon: Decimal | None = None,
        current_user: CurrentUser,
    ) -> tuple[Booking, list[BookingOffer]]:
        booking = await self._bookings.get_by_id_or_404(booking_id)
        _assert_transition(booking.status, BookingStatus.offered)

        now = datetime.now(UTC)

        if booking.dispatch_mode == DispatchMode.directed:
            eligible_ids = [booking.worker_id] if booking.worker_id else []
        else:
            eligible_workers = await self._matching.find_eligible_workers(
                booking.role_type_id, booking.trust_id, booking.shift_date,
                school_lat=school_lat, school_lon=school_lon,
            )
            eligible_ids = [w.id for w in eligible_workers]

        if not eligible_ids:
            raise WorkflowError("No eligible workers found for this booking.")

        offers: list[BookingOffer] = []
        for worker_id in eligible_ids:
            offer = await self._offers.create(
                trust_id=booking.trust_id,
                booking_id=booking.id,
                worker_id=worker_id,
                status=BookingOfferStatus.offered,
                offered_at=now,
                expires_at=booking.offer_expires_at,
            )
            offers.append(offer)

        booking = await self._bookings.update(booking, status=BookingStatus.offered, offered_at=now)
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, BookingStatus.requested, BookingStatus.offered, current_user.user_id
        )
        await audit_log(
            self._session, action=core.audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            new_values={"status": BookingStatus.offered.value, "offer_count": len(offers)},
        )
        await booking_events.dispatch(booking_events.BookingOfferedEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            worker_ids=eligible_ids, shift_date=str(booking.shift_date),
            offer_expires_at=booking.offer_expires_at, occurred_at=now,
        ))
        return booking, offers

    async def accept_offer(
        self,
        booking_id: UUID,
        *,
        worker_id: UUID,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)
        _assert_transition(booking.status, BookingStatus.accepted)

        offer = await self._offers.get_for_booking_and_worker(booking_id, worker_id)
        if not offer or offer.status != BookingOfferStatus.offered:
            raise WorkflowError("No active offer found for this worker.")

        now = datetime.now(UTC)
        if offer.expires_at and now > offer.expires_at:
            await self._offers.update(offer, status=BookingOfferStatus.expired, responded_at=now)
            raise WorkflowError("This offer has expired.")

        # Expire all other offers (first-accept-wins)
        await self._offers.expire_all_for_booking(booking_id)
        # Mark this one accepted
        await self._offers.update(offer, status=BookingOfferStatus.accepted, responded_at=now)

        booking = await self._bookings.update(
            booking, status=BookingStatus.accepted, accepted_at=now, worker_id=worker_id
        )
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, BookingStatus.offered, BookingStatus.accepted, current_user.user_id
        )
        await audit_log(
            self._session, action=core.audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            new_values={"status": BookingStatus.accepted.value, "worker_id": str(worker_id)},
        )
        await booking_events.dispatch(booking_events.BookingAcceptedEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            worker_id=worker_id, shift_date=str(booking.shift_date),
            occurred_at=now,
        ))
        return booking

    async def decline_offer(
        self,
        booking_id: UUID,
        *,
        worker_id: UUID,
        reason: str | None = None,
        current_user: CurrentUser,
    ) -> BookingOffer:
        offer = await self._offers.get_for_booking_and_worker(booking_id, worker_id)
        if not offer or offer.status != BookingOfferStatus.offered:
            raise WorkflowError("No active offer found for this worker.")
        now = datetime.now(UTC)
        return await self._offers.update(
            offer, status=BookingOfferStatus.declined, responded_at=now, decline_reason=reason
        )

    async def confirm_booking(
        self,
        booking_id: UUID,
        *,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)
        _assert_transition(booking.status, BookingStatus.confirmed)
        now = datetime.now(UTC)
        booking = await self._bookings.update(
            booking, status=BookingStatus.confirmed,
            confirmed_at=now, school_confirmed_at=now,
            school_confirmed_by=current_user.user_id,
        )
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, BookingStatus.accepted, BookingStatus.confirmed, current_user.user_id
        )
        await audit_log(
            self._session, action=core.audit.AuditAction.approve,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            new_values={"status": BookingStatus.confirmed.value},
        )
        await booking_events.dispatch(booking_events.BookingConfirmedEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            worker_id=booking.worker_id, school_id=booking.school_id,
            confirmed_by=current_user.user_id, occurred_at=now,
        ))
        return booking

    async def cancel_booking(
        self,
        booking_id: UUID,
        *,
        reason: str | None = None,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)
        _assert_transition(booking.status, BookingStatus.cancelled)
        prior = booking.status
        now = datetime.now(UTC)
        # Expire any pending offers
        await self._offers.expire_all_for_booking(booking_id)
        booking = await self._bookings.update(
            booking, status=BookingStatus.cancelled,
            cancelled_at=now, cancelled_by=current_user.user_id,
            cancellation_reason=reason,
        )
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, prior, BookingStatus.cancelled, current_user.user_id, reason
        )
        await audit_log(
            self._session, action=core.audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            new_values={"status": BookingStatus.cancelled.value, "reason": reason},
        )
        await booking_events.dispatch(booking_events.BookingCancelledEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            cancelled_by=current_user.user_id, reason=reason,
            from_status=prior.value, occurred_at=now,
        ))
        return booking

    async def expire_booking(
        self,
        booking_id: UUID,
        *,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)
        _assert_transition(booking.status, BookingStatus.expired)
        now = datetime.now(UTC)
        await self._offers.expire_all_for_booking(booking_id)
        booking = await self._bookings.update(booking, status=BookingStatus.expired, expired_at=now)
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, BookingStatus.offered, BookingStatus.expired, current_user.user_id
        )
        await booking_events.dispatch(booking_events.BookingExpiredEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            shift_date=str(booking.shift_date), occurred_at=now,
        ))
        return booking

    async def get_booking(self, booking_id: UUID) -> Booking:
        return await self._bookings.get_by_id_or_404(booking_id)

    async def list_bookings(
        self,
        *,
        status: BookingStatus | None = None,
        school_id: UUID | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[Booking], int]:
        filters = {k: v for k, v in {"status": status, "school_id": school_id}.items() if v is not None}
        return await self._bookings.list_all(filters=filters or None, offset=offset, limit=limit)

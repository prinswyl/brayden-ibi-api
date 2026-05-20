"""
Attendance service — check-in, check-out, no-show, manual override.

Check-in requires the booking to be confirmed.
First-shift verification is enforced here if this is the worker's first
shift at the school (delegates to FirstShiftService).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log as audit_log
from app.core import audit as core_audit
from app.core.auth import CurrentUser
from app.events import booking_events
from app.models.booking import Booking
from app.repositories.booking import BookingRepository
from app.shared.enums import BookingStatus
from app.shared.exceptions import WorkflowError


class AttendanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._bookings = BookingRepository(session)
        self._session = session

    async def check_in(
        self,
        booking_id: UUID,
        *,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)

        if booking.status != BookingStatus.confirmed:
            raise WorkflowError(
                f"Cannot check in: booking is '{booking.status.value}', expected 'confirmed'."
            )

        # First-shift verification gate.
        # Once a worker's DBS has been physically sighted at any school within this trust,
        # they are cleared trust-wide (first_shift_cleared=True on the worker profile).
        # The per-school first_shift_verifications records remain as the audit trail of
        # who verified the certificate and at which school.
        if booking.worker_id:
            from app.repositories.worker import WorkerRepository
            worker_repo = WorkerRepository(self._session)
            worker = await worker_repo.get_by_id_or_404(booking.worker_id)
            if not worker.first_shift_cleared:
                raise WorkflowError(
                    "First-shift DBS physical verification must be completed before check-in. "
                    "A receptionist or HR officer at any school in the trust must confirm the "
                    "worker's DBS certificate in person."
                )

        now = datetime.now(UTC)
        booking = await self._bookings.update(
            booking,
            status=BookingStatus.checked_in,
            checked_in_at=now,
            checked_in_by=current_user.user_id,
        )
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, BookingStatus.confirmed, BookingStatus.checked_in, current_user.user_id
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            school_id=booking.school_id, worker_id=booking.worker_id,
            new_values={"status": BookingStatus.checked_in.value},
        )
        await booking_events.dispatch(booking_events.BookingCheckedInEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            worker_id=booking.worker_id, school_id=booking.school_id,
            checked_in_by=current_user.user_id, occurred_at=now,
        ))
        return booking

    async def complete_shift(
        self,
        booking_id: UUID,
        *,
        check_out_time: datetime | None = None,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)

        if booking.status != BookingStatus.checked_in:
            raise WorkflowError(
                f"Cannot complete shift: booking is '{booking.status.value}', expected 'checked_in'."
            )

        now = datetime.now(UTC)
        booking = await self._bookings.update(
            booking,
            status=BookingStatus.completed,
            completed_at=now,
            check_out_at=check_out_time or now,
        )
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, BookingStatus.checked_in, BookingStatus.completed, current_user.user_id
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            school_id=booking.school_id, worker_id=booking.worker_id,
            new_values={"status": BookingStatus.completed.value},
        )
        await booking_events.dispatch(booking_events.BookingCompletedEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            worker_id=booking.worker_id, school_id=booking.school_id,
            shift_date=str(booking.shift_date), occurred_at=now,
        ))
        return booking

    async def record_no_show(
        self,
        booking_id: UUID,
        *,
        reason: str | None = None,
        current_user: CurrentUser,
    ) -> Booking:
        booking = await self._bookings.get_by_id_or_404(booking_id)

        if booking.status not in (BookingStatus.confirmed, BookingStatus.checked_in):
            raise WorkflowError(
                f"Cannot record no-show: booking is '{booking.status.value}'."
            )

        prior = booking.status
        now = datetime.now(UTC)
        booking = await self._bookings.update(
            booking, status=BookingStatus.no_show, no_show_reason=reason
        )
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, prior, BookingStatus.no_show, current_user.user_id, reason
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            school_id=booking.school_id, worker_id=booking.worker_id,
            new_values={"status": BookingStatus.no_show.value, "reason": reason},
        )
        await booking_events.dispatch(booking_events.BookingNoShowEvent(
            booking_id=booking.id, trust_id=booking.trust_id,
            worker_id=booking.worker_id, school_id=booking.school_id,
            shift_date=str(booking.shift_date), recorded_by=current_user.user_id,
            occurred_at=now,
        ))
        return booking

    async def manual_override(
        self,
        booking_id: UUID,
        *,
        target_status: BookingStatus,
        reason: str,
        current_user: CurrentUser,
    ) -> Booking:
        """Admin override — can force any terminal status with a mandatory reason."""
        terminal = {BookingStatus.completed, BookingStatus.cancelled, BookingStatus.no_show, BookingStatus.rejected}
        if target_status not in terminal:
            raise WorkflowError(f"Manual override only allows terminal statuses. Got: {target_status.value}")

        booking = await self._bookings.get_by_id_or_404(booking_id)
        prior = booking.status
        now = datetime.now(UTC)
        booking = await self._bookings.update(booking, status=target_status)
        await self._bookings.write_status_history(
            booking.id, booking.trust_id, prior, target_status, current_user.user_id, f"[OVERRIDE] {reason}"
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.update,
            resource_type="bookings", resource_id=booking.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            new_values={"status": target_status.value, "override_reason": reason},
        )
        return booking

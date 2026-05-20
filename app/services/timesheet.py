"""
Timesheet service.

Lifecycle: draft → submitted → approved / rejected / correction_requested
Approved timesheets are locked and cannot be modified.
Corrections create an immutable TimesheetCorrection record.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log as audit_log
from app.core import audit as core_audit
from app.core.auth import CurrentUser
from app.events import booking_events
from app.models.timesheet import Timesheet, TimesheetCorrection
from app.repositories.booking import BookingRepository
from app.repositories.timesheet import TimesheetCorrectionRepository, TimesheetRepository
from app.shared.enums import BookingStatus, TimesheetStatus
from app.shared.exceptions import ConflictError, NotFoundError, WorkflowError


class TimesheetService:
    def __init__(self, session: AsyncSession) -> None:
        self._timesheets = TimesheetRepository(session)
        self._corrections = TimesheetCorrectionRepository(session)
        self._bookings = BookingRepository(session)
        self._session = session

    async def create_draft(
        self,
        booking_id: UUID,
        *,
        current_user: CurrentUser,
    ) -> Timesheet:
        """Create a draft timesheet for a completed booking. One per booking."""
        booking = await self._bookings.get_by_id_or_404(booking_id)

        if booking.status != BookingStatus.completed:
            raise WorkflowError(
                f"Timesheets can only be created for completed bookings (status: {booking.status.value})."
            )

        existing = await self._timesheets.get_for_booking(booking_id)
        if existing:
            raise ConflictError(f"A timesheet already exists for booking {booking_id}.")

        timesheet = await self._timesheets.create(
            trust_id=booking.trust_id,
            booking_id=booking_id,
            worker_id=booking.worker_id,
            school_id=booking.school_id,
            shift_date=booking.shift_date,
            hourly_rate=booking.agreed_hourly_rate,
            status=TimesheetStatus.draft,
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.create,
            resource_type="timesheets", resource_id=timesheet.id,
            trust_id=booking.trust_id, user_id=current_user.user_id,
            worker_id=booking.worker_id, school_id=booking.school_id,
        )
        return timesheet

    async def submit(
        self,
        timesheet_id: UUID,
        *,
        actual_start_time,
        actual_end_time,
        break_minutes: int = 0,
        overtime_hours: Decimal = Decimal("0"),
        worker_notes: str | None = None,
        current_user: CurrentUser,
    ) -> Timesheet:
        timesheet = await self._timesheets.get_by_id_or_404(timesheet_id)

        if timesheet.status not in (TimesheetStatus.draft, TimesheetStatus.correction_requested):
            raise WorkflowError(
                f"Cannot submit timesheet with status '{timesheet.status.value}'."
            )

        # Compute total hours from actual times
        from datetime import date, timedelta
        dummy_date = date(2000, 1, 1)
        start_dt = datetime.combine(dummy_date, actual_start_time)
        end_dt = datetime.combine(dummy_date, actual_end_time)
        worked_mins = (end_dt - start_dt).total_seconds() / 60 - break_minutes
        total_hours = Decimal(str(round(worked_mins / 60, 2)))

        gross_pay = None
        if timesheet.hourly_rate:
            gross_pay = round((total_hours + overtime_hours) * timesheet.hourly_rate, 2)

        now = datetime.now(UTC)
        timesheet = await self._timesheets.update(
            timesheet,
            status=TimesheetStatus.submitted,
            actual_start_time=actual_start_time,
            actual_end_time=actual_end_time,
            break_minutes=break_minutes,
            total_hours=total_hours,
            overtime_hours=overtime_hours,
            gross_pay=gross_pay,
            worker_notes=worker_notes,
            submitted_at=now,
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.update,
            resource_type="timesheets", resource_id=timesheet.id,
            trust_id=timesheet.trust_id, user_id=current_user.user_id,
            new_values={"status": TimesheetStatus.submitted.value, "total_hours": str(total_hours)},
        )
        await booking_events.dispatch(booking_events.TimesheetSubmittedEvent(
            timesheet_id=timesheet.id, trust_id=timesheet.trust_id,
            booking_id=timesheet.booking_id, worker_id=timesheet.worker_id,
            school_id=timesheet.school_id, shift_date=str(timesheet.shift_date),
            total_hours=str(total_hours), occurred_at=now,
        ))
        return timesheet

    async def approve(
        self,
        timesheet_id: UUID,
        *,
        current_user: CurrentUser,
    ) -> Timesheet:
        timesheet = await self._timesheets.get_by_id_or_404(timesheet_id)

        if timesheet.status != TimesheetStatus.submitted:
            raise WorkflowError(
                f"Cannot approve timesheet with status '{timesheet.status.value}'."
            )

        now = datetime.now(UTC)
        timesheet = await self._timesheets.update(
            timesheet,
            status=TimesheetStatus.approved,
            approved_by=current_user.user_id,
            approved_at=now,
            locked_at=now,  # immutable after approval
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.approve,
            resource_type="timesheets", resource_id=timesheet.id,
            trust_id=timesheet.trust_id, user_id=current_user.user_id,
        )
        await booking_events.dispatch(booking_events.TimesheetApprovedEvent(
            timesheet_id=timesheet.id, trust_id=timesheet.trust_id,
            worker_id=timesheet.worker_id, school_id=timesheet.school_id,
            approved_by=current_user.user_id, occurred_at=now,
        ))
        return timesheet

    async def reject(
        self,
        timesheet_id: UUID,
        *,
        reason: str,
        current_user: CurrentUser,
    ) -> Timesheet:
        timesheet = await self._timesheets.get_by_id_or_404(timesheet_id)

        if timesheet.status != TimesheetStatus.submitted:
            raise WorkflowError(
                f"Cannot reject timesheet with status '{timesheet.status.value}'."
            )

        now = datetime.now(UTC)
        timesheet = await self._timesheets.update(
            timesheet,
            status=TimesheetStatus.rejected,
            rejected_by=current_user.user_id,
            rejected_at=now,
            rejection_reason=reason,
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.reject,
            resource_type="timesheets", resource_id=timesheet.id,
            trust_id=timesheet.trust_id, user_id=current_user.user_id,
            new_values={"reason": reason},
        )
        await booking_events.dispatch(booking_events.TimesheetRejectedEvent(
            timesheet_id=timesheet.id, trust_id=timesheet.trust_id,
            worker_id=timesheet.worker_id, rejected_by=current_user.user_id,
            reason=reason, occurred_at=now,
        ))
        return timesheet

    async def request_correction(
        self,
        timesheet_id: UUID,
        *,
        reason: str,
        current_user: CurrentUser,
    ) -> tuple[Timesheet, TimesheetCorrection]:
        timesheet = await self._timesheets.get_by_id_or_404(timesheet_id)

        if timesheet.status != TimesheetStatus.submitted:
            raise WorkflowError(
                f"Cannot request correction on timesheet with status '{timesheet.status.value}'."
            )

        if timesheet.locked_at:
            raise WorkflowError("Timesheet is locked and cannot be corrected.")

        # Snapshot current values for correction record
        old_values: dict[str, Any] = {
            "actual_start_time": str(timesheet.actual_start_time) if timesheet.actual_start_time else None,
            "actual_end_time": str(timesheet.actual_end_time) if timesheet.actual_end_time else None,
            "break_minutes": timesheet.break_minutes,
            "total_hours": str(timesheet.total_hours) if timesheet.total_hours else None,
            "overtime_hours": str(timesheet.overtime_hours),
        }

        now = datetime.now(UTC)
        correction = await self._corrections.create(
            trust_id=timesheet.trust_id,
            timesheet_id=timesheet_id,
            requested_by=current_user.user_id,
            reason=reason,
            old_values=old_values,
            created_at=now,
        )
        timesheet = await self._timesheets.update(
            timesheet,
            status=TimesheetStatus.correction_requested,
            correction_requested_at=now,
            correction_requested_by=current_user.user_id,
        )
        await audit_log(
            self._session, action=core_audit.AuditAction.update,
            resource_type="timesheets", resource_id=timesheet.id,
            trust_id=timesheet.trust_id, user_id=current_user.user_id,
            new_values={"status": TimesheetStatus.correction_requested.value, "reason": reason},
        )
        await booking_events.dispatch(booking_events.TimesheetCorrectionRequestedEvent(
            timesheet_id=timesheet.id, trust_id=timesheet.trust_id,
            worker_id=timesheet.worker_id, requested_by=current_user.user_id,
            reason=reason, occurred_at=now,
        ))
        return timesheet, correction

    async def get_corrections(self, timesheet_id: UUID) -> list[TimesheetCorrection]:
        return await self._corrections.list_for_timesheet(timesheet_id)

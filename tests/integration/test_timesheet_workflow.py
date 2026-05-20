"""
Integration tests for the timesheet workflow.

submit → approve / reject → request correction
"""

import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.booking import BookingService
from app.services.attendance import AttendanceService
from app.services.first_shift import FirstShiftService
from app.services.onboarding import OnboardingService
from app.services.timesheet import TimesheetService
from app.shared.enums import BookingStatus, DispatchMode, TimesheetStatus
from app.shared.exceptions import ConflictError, WorkflowError
from tests.conftest import (
    TEST_TRUST_ID, TEST_SCHOOL_ID, TEST_ROLE_TYPE_ID,
    TEST_WORKER_USER_ID,
)


async def _completed_booking(session, current_user):
    """Helper: create a fully completed booking ready for timesheets."""
    onb = OnboardingService(session)
    worker = await onb.create_worker_profile(
        user_id=TEST_WORKER_USER_ID, trust_id=TEST_TRUST_ID, current_user=current_user
    )
    worker = await onb.submit_for_review(worker.id, current_user=current_user)
    worker = await onb.start_review(worker.id, current_user=current_user)
    worker = await onb.approve_worker(worker.id, current_user=current_user)

    fss = FirstShiftService(session)
    await fss.verify_first_shift(
        worker_id=worker.id,
        school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID,
        dbs_seen_and_matched=True,
        current_user=current_user,
    )

    svc = BookingService(session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=1),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=current_user)
    booking = await svc.confirm_booking(booking.id, current_user=current_user)

    att = AttendanceService(session)
    booking = await att.check_in(booking.id, current_user=current_user)
    booking = await att.complete_shift(booking.id, current_user=current_user)

    return booking, worker


@pytest.mark.asyncio
async def test_timesheet_draft_and_submit(db_session: AsyncSession, trust_admin_current_user):
    booking, worker = await _completed_booking(db_session, trust_admin_current_user)

    ts_svc = TimesheetService(db_session)
    timesheet = await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)
    assert timesheet.status == TimesheetStatus.draft
    assert timesheet.booking_id == booking.id
    assert timesheet.worker_id == worker.id

    timesheet = await ts_svc.submit(
        timesheet.id,
        actual_start_time=time(9, 5),
        actual_end_time=time(15, 0),
        break_minutes=30,
        worker_notes="Good shift.",
        current_user=trust_admin_current_user,
    )
    assert timesheet.status == TimesheetStatus.submitted
    assert timesheet.total_hours is not None
    assert timesheet.total_hours > 0


@pytest.mark.asyncio
async def test_timesheet_approve(db_session: AsyncSession, trust_admin_current_user):
    booking, _ = await _completed_booking(db_session, trust_admin_current_user)
    ts_svc = TimesheetService(db_session)

    timesheet = await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)
    timesheet = await ts_svc.submit(
        timesheet.id,
        actual_start_time=time(9, 0),
        actual_end_time=time(15, 0),
        break_minutes=0,
        current_user=trust_admin_current_user,
    )

    timesheet = await ts_svc.approve(timesheet.id, current_user=trust_admin_current_user)
    assert timesheet.status == TimesheetStatus.approved
    assert timesheet.locked_at is not None


@pytest.mark.asyncio
async def test_timesheet_reject(db_session: AsyncSession, trust_admin_current_user):
    booking, _ = await _completed_booking(db_session, trust_admin_current_user)
    ts_svc = TimesheetService(db_session)

    timesheet = await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)
    timesheet = await ts_svc.submit(
        timesheet.id,
        actual_start_time=time(9, 0),
        actual_end_time=time(15, 0),
        break_minutes=0,
        current_user=trust_admin_current_user,
    )

    timesheet = await ts_svc.reject(
        timesheet.id,
        reason="Hours do not match school records.",
        current_user=trust_admin_current_user,
    )
    assert timesheet.status == TimesheetStatus.rejected


@pytest.mark.asyncio
async def test_timesheet_request_correction(db_session: AsyncSession, trust_admin_current_user):
    booking, _ = await _completed_booking(db_session, trust_admin_current_user)
    ts_svc = TimesheetService(db_session)

    timesheet = await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)
    timesheet = await ts_svc.submit(
        timesheet.id,
        actual_start_time=time(9, 0),
        actual_end_time=time(15, 0),
        break_minutes=0,
        current_user=trust_admin_current_user,
    )

    timesheet, correction = await ts_svc.request_correction(
        timesheet.id,
        reason="Please update break minutes to 30.",
        current_user=trust_admin_current_user,
    )
    assert timesheet.status == TimesheetStatus.correction_requested

    corrections = await ts_svc.get_corrections(timesheet.id)
    assert len(corrections) == 1
    assert corrections[0].reason == "Please update break minutes to 30."
    assert corrections[0].old_values is not None


@pytest.mark.asyncio
async def test_cannot_create_duplicate_timesheet(db_session: AsyncSession, trust_admin_current_user):
    booking, _ = await _completed_booking(db_session, trust_admin_current_user)
    ts_svc = TimesheetService(db_session)

    await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)

    with pytest.raises(ConflictError):
        await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)


@pytest.mark.asyncio
async def test_cannot_edit_locked_timesheet(db_session: AsyncSession, trust_admin_current_user):
    booking, _ = await _completed_booking(db_session, trust_admin_current_user)
    ts_svc = TimesheetService(db_session)

    timesheet = await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)
    timesheet = await ts_svc.submit(
        timesheet.id,
        actual_start_time=time(9, 0),
        actual_end_time=time(15, 0),
        break_minutes=0,
        current_user=trust_admin_current_user,
    )
    timesheet = await ts_svc.approve(timesheet.id, current_user=trust_admin_current_user)

    # Approved timesheets are locked — request_correction should fail
    with pytest.raises(WorkflowError):
        await ts_svc.request_correction(
            timesheet.id,
            reason="Change hours.",
            current_user=trust_admin_current_user,
        )


@pytest.mark.asyncio
async def test_cannot_create_timesheet_for_non_completed_booking(
    db_session: AsyncSession, trust_admin_current_user
):
    onb = OnboardingService(db_session)
    worker = await onb.create_worker_profile(
        user_id=TEST_WORKER_USER_ID, trust_id=TEST_TRUST_ID, current_user=trust_admin_current_user
    )
    worker = await onb.submit_for_review(worker.id, current_user=trust_admin_current_user)
    worker = await onb.start_review(worker.id, current_user=trust_admin_current_user)
    worker = await onb.approve_worker(worker.id, current_user=trust_admin_current_user)

    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=2),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    # Booking is only in 'requested' state — cannot create timesheet yet
    ts_svc = TimesheetService(db_session)
    with pytest.raises(WorkflowError):
        await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)

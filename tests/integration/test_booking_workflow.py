"""
Integration tests for the core booking workflow.

directed: school → create booking → dispatch → worker accepts → school confirms
→ check-in → complete → timesheet
"""

import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.booking import BookingService
from app.services.attendance import AttendanceService
from app.services.onboarding import OnboardingService
from app.services.timesheet import TimesheetService
from app.services.first_shift import FirstShiftService
from app.shared.enums import BookingStatus, DispatchMode, TimesheetStatus
from app.shared.exceptions import WorkflowError
from tests.conftest import (
    TEST_TRUST_ID, TEST_USER_ID, TEST_WORKER_USER_ID,
    TEST_SCHOOL_ID, TEST_ROLE_TYPE_ID, TEST_WORKER_PROFILE_ID,
)


async def _create_approved_worker(session, trust_admin_current_user):
    """Helper: create and fully approve a worker profile."""
    onb = OnboardingService(session)
    worker = await onb.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    worker = await onb.submit_for_review(worker.id, current_user=trust_admin_current_user)
    worker = await onb.start_review(worker.id, current_user=trust_admin_current_user)
    worker = await onb.approve_worker(worker.id, current_user=trust_admin_current_user)
    return worker


@pytest.mark.asyncio
async def test_directed_booking_full_lifecycle(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)

    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=3),
        start_time=time(9, 0),
        end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    assert booking.status == BookingStatus.requested
    assert booking.dispatch_mode == DispatchMode.directed

    booking, offers = await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.offered
    assert len(offers) == 1
    assert offers[0].worker_id == worker.id

    booking = await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.accepted
    assert booking.worker_id == worker.id

    booking = await svc.confirm_booking(booking.id, current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.confirmed


@pytest.mark.asyncio
async def test_booking_history_is_written(db_session: AsyncSession, trust_admin_current_user):
    from app.models.booking import BookingStatusHistory
    from sqlalchemy import select

    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)

    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=5),
        start_time=time(8, 0), end_time=time(16, 0),
        agreed_hourly_rate=Decimal("13.00"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)

    result = await db_session.execute(
        select(BookingStatusHistory).where(BookingStatusHistory.booking_id == booking.id)
    )
    history = list(result.scalars().all())
    statuses = [h.to_status for h in history]
    assert BookingStatus.requested in statuses
    assert BookingStatus.offered in statuses
    assert BookingStatus.accepted in statuses


@pytest.mark.asyncio
async def test_cancel_before_acceptance(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)

    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=2),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.00"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    booking = await svc.cancel_booking(booking.id, reason="School closure.", current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.cancelled
    assert booking.cancellation_reason == "School closure."


@pytest.mark.asyncio
async def test_illegal_transition_raises(db_session: AsyncSession, trust_admin_current_user):
    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=4),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.00"),
        current_user=trust_admin_current_user,
    )
    # Cannot confirm without acceptance
    with pytest.raises(WorkflowError):
        await svc.confirm_booking(booking.id, current_user=trust_admin_current_user)


@pytest.mark.asyncio
async def test_directed_booking_requires_worker_id(db_session: AsyncSession, trust_admin_current_user):
    svc = BookingService(db_session)
    with pytest.raises(WorkflowError):
        await svc.create_booking(
            school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
            role_type_id=TEST_ROLE_TYPE_ID,
            shift_date=date.today() + timedelta(days=3),
            start_time=time(9, 0), end_time=time(15, 0),
            agreed_hourly_rate=Decimal("12.00"),
            dispatch_mode=DispatchMode.directed,
            directed_worker_id=None,  # missing
            current_user=trust_admin_current_user,
        )


@pytest.mark.asyncio
async def test_full_attendance_flow(db_session: AsyncSession, trust_admin_current_user):
    """confirmed → checked_in → completed"""
    worker = await _create_approved_worker(db_session, trust_admin_current_user)

    # First: complete first-shift verification so check-in is allowed
    fss = FirstShiftService(db_session)
    await fss.verify_first_shift(
        worker_id=worker.id,
        school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID,
        dbs_seen_and_matched=True,
        current_user=trust_admin_current_user,
    )

    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=1),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)
    booking = await svc.confirm_booking(booking.id, current_user=trust_admin_current_user)

    att = AttendanceService(db_session)
    booking = await att.check_in(booking.id, current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.checked_in
    assert booking.checked_in_at is not None

    booking = await att.complete_shift(booking.id, current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.completed
    assert booking.completed_at is not None


@pytest.mark.asyncio
async def test_no_show_from_confirmed(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=2),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.00"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)
    await svc.confirm_booking(booking.id, current_user=trust_admin_current_user)

    att = AttendanceService(db_session)
    booking = await att.record_no_show(booking.id, reason="Worker did not arrive.", current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.no_show
    assert booking.no_show_reason == "Worker did not arrive."

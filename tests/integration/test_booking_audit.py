"""
Audit trail tests for the Bookings & Timesheets domain.

Verifies that audit_logs rows are written for key booking and timesheet actions.
"""

import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.booking import BookingService
from app.services.attendance import AttendanceService
from app.services.first_shift import FirstShiftService
from app.services.onboarding import OnboardingService
from app.services.timesheet import TimesheetService
from app.shared.enums import AuditAction, DispatchMode
from tests.conftest import (
    TEST_TRUST_ID, TEST_SCHOOL_ID, TEST_ROLE_TYPE_ID,
    TEST_WORKER_USER_ID, TEST_USER_ID,
)


async def _approved_worker(session, current_user):
    onb = OnboardingService(session)
    worker = await onb.create_worker_profile(
        user_id=TEST_WORKER_USER_ID, trust_id=TEST_TRUST_ID, current_user=current_user
    )
    worker = await onb.submit_for_review(worker.id, current_user=current_user)
    worker = await onb.start_review(worker.id, current_user=current_user)
    return await onb.approve_worker(worker.id, current_user=current_user)


async def _audit_rows(session, resource_type: str, resource_id) -> list[dict]:
    result = await session.execute(
        text("SELECT action, user_id FROM audit_logs WHERE resource_type = :rt AND resource_id = :rid"),
        {"rt": resource_type, "rid": str(resource_id)},
    )
    return [{"action": row[0], "user_id": str(row[1])} for row in result.fetchall()]


@pytest.mark.asyncio
async def test_audit_on_booking_create(db_session: AsyncSession, trust_admin_current_user):
    worker = await _approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=5),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )

    rows = await _audit_rows(db_session, "bookings", booking.id)
    actions = [r["action"] for r in rows]
    assert AuditAction.create.value in actions


@pytest.mark.asyncio
async def test_audit_on_booking_accept(db_session: AsyncSession, trust_admin_current_user):
    worker = await _approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=6),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)

    rows = await _audit_rows(db_session, "bookings", booking.id)
    actions = [r["action"] for r in rows]
    assert AuditAction.update.value in actions


@pytest.mark.asyncio
async def test_audit_on_booking_confirm(db_session: AsyncSession, trust_admin_current_user):
    worker = await _approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=7),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)
    await svc.confirm_booking(booking.id, current_user=trust_admin_current_user)

    rows = await _audit_rows(db_session, "bookings", booking.id)
    # At minimum: create, update (accept), approve (confirm)
    assert len(rows) >= 3


@pytest.mark.asyncio
async def test_audit_on_booking_cancel(db_session: AsyncSession, trust_admin_current_user):
    worker = await _approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=8),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.cancel_booking(booking.id, reason="Cancelled for testing.", current_user=trust_admin_current_user)

    rows = await _audit_rows(db_session, "bookings", booking.id)
    actions = [r["action"] for r in rows]
    assert AuditAction.create.value in actions
    assert AuditAction.update.value in actions


@pytest.mark.asyncio
async def test_audit_actor_is_current_user(db_session: AsyncSession, trust_admin_current_user):
    worker = await _approved_worker(db_session, trust_admin_current_user)
    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=9),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )

    rows = await _audit_rows(db_session, "bookings", booking.id)
    create_row = next(r for r in rows if r["action"] == AuditAction.create.value)
    assert create_row["user_id"] == str(TEST_USER_ID)


@pytest.mark.asyncio
async def test_audit_on_timesheet_approve(db_session: AsyncSession, trust_admin_current_user):
    worker = await _approved_worker(db_session, trust_admin_current_user)

    fss = FirstShiftService(db_session)
    await fss.verify_first_shift(
        worker_id=worker.id, school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID, dbs_seen_and_matched=True, current_user=trust_admin_current_user,
    )

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
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)
    booking = await svc.confirm_booking(booking.id, current_user=trust_admin_current_user)

    att = AttendanceService(db_session)
    await att.check_in(booking.id, current_user=trust_admin_current_user)
    booking = await att.complete_shift(booking.id, current_user=trust_admin_current_user)

    ts_svc = TimesheetService(db_session)
    ts = await ts_svc.create_draft(booking.id, current_user=trust_admin_current_user)
    ts = await ts_svc.submit(
        ts.id, actual_start_time=time(9, 0), actual_end_time=time(15, 0),
        break_minutes=0, current_user=trust_admin_current_user,
    )
    await ts_svc.approve(ts.id, current_user=trust_admin_current_user)

    rows = await _audit_rows(db_session, "timesheets", ts.id)
    actions = [r["action"] for r in rows]
    assert AuditAction.approve.value in actions

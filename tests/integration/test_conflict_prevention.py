"""
Conflict prevention tests.

Verifies that double-bookings, availability conflicts, and
first-accept-wins race conditions are correctly prevented.
"""

import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.availability import AvailabilityService
from app.services.booking import BookingService
from app.services.onboarding import OnboardingService
from app.shared.enums import BookingOfferStatus, BookingStatus, DispatchMode
from app.shared.exceptions import ConflictError, WorkflowError
from tests.conftest import (
    TEST_TRUST_ID, TEST_SCHOOL_ID, TEST_ROLE_TYPE_ID,
    TEST_WORKER_USER_ID,
)


async def _approved_worker(session, current_user):
    onb = OnboardingService(session)
    worker = await onb.create_worker_profile(
        user_id=TEST_WORKER_USER_ID, trust_id=TEST_TRUST_ID, current_user=current_user
    )
    worker = await onb.submit_for_review(worker.id, current_user=current_user)
    worker = await onb.start_review(worker.id, current_user=current_user)
    return await onb.approve_worker(worker.id, current_user=current_user)


@pytest.mark.asyncio
async def test_cannot_mark_unavailable_with_active_booking(db_session: AsyncSession, trust_admin_current_user):
    worker = await _approved_worker(db_session, trust_admin_current_user)
    shift_date = date.today() + timedelta(days=5)

    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=shift_date, start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)

    avail_svc = AvailabilityService(db_session)
    with pytest.raises(ConflictError):
        await avail_svc.set_availability(
            worker_id=worker.id, trust_id=TEST_TRUST_ID,
            available_date=shift_date, is_available=False,
            current_user=trust_admin_current_user,
        )


@pytest.mark.asyncio
async def test_first_accept_wins_expires_other_offers(db_session: AsyncSession, trust_admin_current_user):
    """When one worker accepts, all other outstanding offers are expired."""
    from tests.conftest import TEST_SCHOOL_LEADER_USER_ID
    from app.services.onboarding import OnboardingService

    worker1 = await _approved_worker(db_session, trust_admin_current_user)

    # Create a second fully-approved worker profile using the school-leader user slot
    onb = OnboardingService(db_session)
    worker2 = await onb.create_worker_profile(
        user_id=TEST_SCHOOL_LEADER_USER_ID, trust_id=TEST_TRUST_ID, current_user=trust_admin_current_user
    )
    worker2 = await onb.submit_for_review(worker2.id, current_user=trust_admin_current_user)
    worker2 = await onb.start_review(worker2.id, current_user=trust_admin_current_user)
    worker2 = await onb.approve_worker(worker2.id, current_user=trust_admin_current_user)

    svc = BookingService(db_session)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=6),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.broadcast,
        current_user=trust_admin_current_user,
    )

    # Manually create two offers (one per worker) to simulate broadcast dispatch
    from app.repositories.booking import BookingOfferRepository, BookingRepository
    from app.shared.enums import BookingOfferStatus
    from datetime import UTC, datetime
    offer_repo = BookingOfferRepository(db_session)
    await offer_repo.create(
        trust_id=TEST_TRUST_ID,
        booking_id=booking.id,
        worker_id=worker1.id,
        status=BookingOfferStatus.offered,
        offered_at=datetime.now(UTC),
    )
    await offer_repo.create(
        trust_id=TEST_TRUST_ID,
        booking_id=booking.id,
        worker_id=worker2.id,
        status=BookingOfferStatus.offered,
        offered_at=datetime.now(UTC),
    )
    booking_repo = BookingRepository(db_session)
    await booking_repo.update(booking, status=BookingStatus.offered)

    # Worker1 accepts first
    booking = await svc.accept_offer(booking.id, worker_id=worker1.id, current_user=trust_admin_current_user)
    assert booking.status == BookingStatus.accepted

    # Worker2's offer should now be expired
    other_offer = await offer_repo.get_for_booking_and_worker(booking.id, worker2.id)
    assert other_offer.status == BookingOfferStatus.expired


@pytest.mark.asyncio
async def test_cannot_accept_expired_offer(db_session: AsyncSession, trust_admin_current_user):
    from datetime import UTC, datetime, timedelta
    worker = await _approved_worker(db_session, trust_admin_current_user)

    svc = BookingService(db_session)
    # Create with past expiry
    past_expiry = datetime.now(UTC) - timedelta(hours=1)
    booking = await svc.create_booking(
        school_id=TEST_SCHOOL_ID, trust_id=TEST_TRUST_ID,
        role_type_id=TEST_ROLE_TYPE_ID,
        shift_date=date.today() + timedelta(days=7),
        start_time=time(9, 0), end_time=time(15, 0),
        agreed_hourly_rate=Decimal("12.50"),
        dispatch_mode=DispatchMode.directed,
        directed_worker_id=worker.id,
        offer_expires_at=past_expiry,
        current_user=trust_admin_current_user,
    )
    await svc.dispatch_offers(booking.id, current_user=trust_admin_current_user)

    with pytest.raises(WorkflowError, match="expired"):
        await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)


@pytest.mark.asyncio
async def test_cannot_accept_already_accepted_booking(db_session: AsyncSession, trust_admin_current_user):
    from tests.conftest import TEST_HR_USER_ID
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
    await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)

    # Booking is now accepted — try to accept again
    with pytest.raises(WorkflowError):
        await svc.accept_offer(booking.id, worker_id=worker.id, current_user=trust_admin_current_user)


@pytest.mark.asyncio
async def test_check_in_blocked_without_first_shift_verification(db_session: AsyncSession, trust_admin_current_user):
    """Worker must have first-shift DBS verified before check-in."""
    worker = await _approved_worker(db_session, trust_admin_current_user)

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
    await svc.confirm_booking(booking.id, current_user=trust_admin_current_user)

    from app.services.attendance import AttendanceService
    att = AttendanceService(db_session)
    with pytest.raises(WorkflowError, match="First-shift"):
        await att.check_in(booking.id, current_user=trust_admin_current_user)

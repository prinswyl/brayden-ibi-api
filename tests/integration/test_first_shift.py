"""
Integration tests for the first-shift DBS verification workflow.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.first_shift import FirstShiftService
from app.services.onboarding import OnboardingService
from app.shared.exceptions import ConflictError, WorkflowError
from tests.conftest import TEST_SCHOOL_ID, TEST_TRUST_ID, TEST_WORKER_USER_ID


async def _create_approved_worker(db, current_user):
    svc = OnboardingService(db)
    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=current_user,
    )
    worker = await svc.submit_for_review(worker.id, current_user=current_user)
    worker = await svc.start_review(worker.id, current_user=current_user)
    worker = await svc.approve_worker(worker.id, current_user=current_user)
    return worker


@pytest.mark.asyncio
async def test_verify_first_shift_success(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = FirstShiftService(db_session)

    verification = await svc.verify_first_shift(
        worker_id=worker.id,
        school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID,
        dbs_seen_and_matched=True,
        notes="DBS certificate verified at front desk.",
        current_user=trust_admin_current_user,
    )
    assert verification.id is not None
    assert verification.dbs_seen_and_matched is True
    assert verification.worker_id == worker.id
    assert verification.school_id == TEST_SCHOOL_ID


@pytest.mark.asyncio
async def test_verify_first_shift_sets_trust_level_flag(db_session: AsyncSession, trust_admin_current_user):
    from app.repositories.worker import WorkerRepository
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = FirstShiftService(db_session)

    await svc.verify_first_shift(
        worker_id=worker.id,
        school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID,
        dbs_seen_and_matched=True,
        current_user=trust_admin_current_user,
    )
    repo = WorkerRepository(db_session)
    updated_worker = await repo.get_by_id(worker.id)
    assert updated_worker.first_shift_cleared is True


@pytest.mark.asyncio
async def test_duplicate_verification_raises_conflict(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = FirstShiftService(db_session)

    await svc.verify_first_shift(
        worker_id=worker.id,
        school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID,
        dbs_seen_and_matched=True,
        current_user=trust_admin_current_user,
    )
    with pytest.raises(ConflictError):
        await svc.verify_first_shift(
            worker_id=worker.id,
            school_id=TEST_SCHOOL_ID,
            trust_id=TEST_TRUST_ID,
            dbs_seen_and_matched=True,
            current_user=trust_admin_current_user,
        )


@pytest.mark.asyncio
async def test_unapproved_worker_cannot_be_verified(db_session: AsyncSession, trust_admin_current_user):
    svc_onboarding = OnboardingService(db_session)
    worker = await svc_onboarding.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    # Worker is still in draft
    svc = FirstShiftService(db_session)
    with pytest.raises(WorkflowError):
        await svc.verify_first_shift(
            worker_id=worker.id,
            school_id=TEST_SCHOOL_ID,
            trust_id=TEST_TRUST_ID,
            dbs_seen_and_matched=True,
            current_user=trust_admin_current_user,
        )


@pytest.mark.asyncio
async def test_get_verification_status_returns_none_when_not_verified(
    db_session: AsyncSession, trust_admin_current_user
):
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = FirstShiftService(db_session)
    result = await svc.get_verification_status(worker.id, TEST_SCHOOL_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_verification_status_returns_record_after_verification(
    db_session: AsyncSession, trust_admin_current_user
):
    worker = await _create_approved_worker(db_session, trust_admin_current_user)
    svc = FirstShiftService(db_session)

    await svc.verify_first_shift(
        worker_id=worker.id,
        school_id=TEST_SCHOOL_ID,
        trust_id=TEST_TRUST_ID,
        dbs_seen_and_matched=True,
        current_user=trust_admin_current_user,
    )
    result = await svc.get_verification_status(worker.id, TEST_SCHOOL_ID)
    assert result is not None
    assert result.dbs_seen_and_matched is True

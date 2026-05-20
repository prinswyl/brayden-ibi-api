"""
Integration tests for the onboarding workflow.

Tests run inside a rolled-back transaction — no permanent DB changes.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.onboarding import OnboardingService
from app.shared.enums import ComplianceStage, OnboardingStatus
from app.shared.exceptions import WorkflowError
from tests.conftest import TEST_TRUST_ID, TEST_USER_ID, TEST_WORKER_USER_ID, trust_admin_current_user


@pytest.mark.asyncio
async def test_create_worker_profile(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)
    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    assert worker.id is not None
    assert worker.onboarding_status == OnboardingStatus.draft
    assert worker.compliance_stage == ComplianceStage.not_started
    assert worker.is_amber is False


@pytest.mark.asyncio
async def test_duplicate_worker_profile_raises(db_session: AsyncSession, trust_admin_current_user):
    from app.shared.exceptions import ConflictError
    svc = OnboardingService(db_session)
    await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    with pytest.raises(ConflictError):
        await svc.create_worker_profile(
            user_id=TEST_WORKER_USER_ID,
            trust_id=TEST_TRUST_ID,
            current_user=trust_admin_current_user,
        )


@pytest.mark.asyncio
async def test_full_approval_workflow(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)

    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )

    worker = await svc.submit_for_review(worker.id, current_user=trust_admin_current_user)
    assert worker.onboarding_status == OnboardingStatus.submitted

    worker = await svc.start_review(worker.id, current_user=trust_admin_current_user)
    assert worker.onboarding_status == OnboardingStatus.under_review

    worker = await svc.approve_worker(worker.id, current_user=trust_admin_current_user, notes="All clear.")
    assert worker.onboarding_status == OnboardingStatus.approved
    assert worker.compliance_stage == ComplianceStage.clearance_granted
    assert worker.is_amber is False


@pytest.mark.asyncio
async def test_rejection_workflow(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)

    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    worker = await svc.submit_for_review(worker.id, current_user=trust_admin_current_user)
    worker = await svc.start_review(worker.id, current_user=trust_admin_current_user)
    worker = await svc.reject_worker(
        worker.id, reason="DBS flagged — cannot proceed.", current_user=trust_admin_current_user
    )
    assert worker.onboarding_status == OnboardingStatus.rejected
    assert worker.compliance_stage == ComplianceStage.clearance_denied


@pytest.mark.asyncio
async def test_rejection_allows_restart(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)

    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    worker = await svc.submit_for_review(worker.id, current_user=trust_admin_current_user)
    worker = await svc.reject_worker(worker.id, reason="Missing documentation entirely.", current_user=trust_admin_current_user)

    # Restart from rejected
    worker = await svc.submit_for_review(worker.id, current_user=trust_admin_current_user)
    assert worker.onboarding_status == OnboardingStatus.submitted


@pytest.mark.asyncio
async def test_suspension_workflow(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)

    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    worker = await svc.submit_for_review(worker.id, current_user=trust_admin_current_user)
    worker = await svc.start_review(worker.id, current_user=trust_admin_current_user)
    worker = await svc.approve_worker(worker.id, current_user=trust_admin_current_user)
    worker = await svc.suspend_worker(
        worker.id, reason="Safeguarding concern raised by school.", current_user=trust_admin_current_user
    )
    assert worker.onboarding_status == OnboardingStatus.suspended
    assert worker.suspended_at is not None
    assert worker.suspension_reason == "Safeguarding concern raised by school."

    worker = await svc.reinstate_worker(worker.id, current_user=trust_admin_current_user)
    assert worker.onboarding_status == OnboardingStatus.approved
    assert worker.suspended_at is None


@pytest.mark.asyncio
async def test_amber_flag_workflow(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)

    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    worker = await svc.set_amber(worker.id, reason="Awaiting updated reference.", current_user=trust_admin_current_user)
    assert worker.is_amber is True

    worker = await svc.clear_amber(worker.id, current_user=trust_admin_current_user)
    assert worker.is_amber is False


@pytest.mark.asyncio
async def test_manual_note_is_persisted(db_session: AsyncSession, trust_admin_current_user):
    from app.repositories.onboarding_note import OnboardingNoteRepository
    from app.shared.enums import NoteVisibility

    svc = OnboardingService(db_session)
    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    await svc.add_manual_note(
        worker.id,
        content="Worker contacted to arrange document drop-off.",
        visibility=NoteVisibility.internal,
        current_user=trust_admin_current_user,
    )

    repo = OnboardingNoteRepository(db_session)
    notes = await repo.list_for_worker(worker.id)
    # Should have the creation note + the manual note
    assert len(notes) >= 2
    contents = [n.content for n in notes]
    assert any("drop-off" in c for c in contents)


@pytest.mark.asyncio
async def test_illegal_transition_raises_workflow_error(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)

    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    # Cannot approve directly from draft
    with pytest.raises(WorkflowError):
        await svc.approve_worker(worker.id, current_user=trust_admin_current_user)

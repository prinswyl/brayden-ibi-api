"""
Tests that every compliance action produces an audit log entry.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.compliance_document import ComplianceDocumentService
from app.services.hr_review import HRReviewService
from app.services.onboarding import OnboardingService
from app.shared.enums import DocumentType
from tests.conftest import TEST_TRUST_ID, TEST_WORKER_USER_ID


async def _audit_count(db: AsyncSession, resource_type: str, action: str) -> int:
    result = await db.execute(
        text(
            "SELECT COUNT(*) FROM audit_logs WHERE resource_type = :rt AND action = :a"
        ),
        {"rt": resource_type, "a": action},
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_creating_worker_writes_audit_log(db_session: AsyncSession, trust_admin_current_user):
    before = await _audit_count(db_session, "worker_profiles", "create")
    svc = OnboardingService(db_session)
    await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    after = await _audit_count(db_session, "worker_profiles", "create")
    assert after == before + 1


@pytest.mark.asyncio
async def test_status_transition_writes_audit_log(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)
    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    before = await _audit_count(db_session, "worker_profiles", "update")
    await svc.submit_for_review(worker.id, current_user=trust_admin_current_user)
    after = await _audit_count(db_session, "worker_profiles", "update")
    assert after == before + 1


@pytest.mark.asyncio
async def test_document_upload_writes_audit_log(db_session: AsyncSession, trust_admin_current_user):
    svc_o = OnboardingService(db_session)
    worker = await svc_o.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    before = await _audit_count(db_session, "compliance_documents", "upload")
    svc = ComplianceDocumentService(db_session)
    await svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="path/dbs.pdf",
        file_name="dbs.pdf",
        current_user=trust_admin_current_user,
    )
    after = await _audit_count(db_session, "compliance_documents", "upload")
    assert after == before + 1


@pytest.mark.asyncio
async def test_document_approval_writes_audit_log(db_session: AsyncSession, trust_admin_current_user):
    svc_o = OnboardingService(db_session)
    worker = await svc_o.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    svc_d = ComplianceDocumentService(db_session)
    doc = await svc_d.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="path/dbs.pdf",
        file_name="dbs.pdf",
        current_user=trust_admin_current_user,
    )
    before = await _audit_count(db_session, "compliance_documents", "approve")
    svc_hr = HRReviewService(db_session)
    await svc_hr.approve_document(doc.id, current_user=trust_admin_current_user)
    after = await _audit_count(db_session, "compliance_documents", "approve")
    assert after == before + 1


@pytest.mark.asyncio
async def test_suspension_writes_audit_log(db_session: AsyncSession, trust_admin_current_user):
    svc = OnboardingService(db_session)
    worker = await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=trust_admin_current_user,
    )
    await svc.submit_for_review(worker.id, current_user=trust_admin_current_user)
    await svc.start_review(worker.id, current_user=trust_admin_current_user)
    await svc.approve_worker(worker.id, current_user=trust_admin_current_user)

    before = await _audit_count(db_session, "worker_profiles", "update")
    await svc.suspend_worker(
        worker.id, reason="Concern raised — pending investigation.", current_user=trust_admin_current_user
    )
    after = await _audit_count(db_session, "worker_profiles", "update")
    assert after > before

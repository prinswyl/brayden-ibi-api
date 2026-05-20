"""
Integration tests for compliance document upload, versioning, and lifecycle.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.compliance_document import ComplianceDocumentService
from app.services.hr_review import HRReviewService
from app.services.onboarding import OnboardingService
from app.shared.enums import DocumentStatus, DocumentType
from app.shared.exceptions import WorkflowError
from tests.conftest import TEST_TRUST_ID, TEST_USER_ID, TEST_WORKER_USER_ID


async def _create_worker(db, current_user):
    svc = OnboardingService(db)
    return await svc.create_worker_profile(
        user_id=TEST_WORKER_USER_ID,
        trust_id=TEST_TRUST_ID,
        current_user=current_user,
    )


@pytest.mark.asyncio
async def test_record_upload_creates_document(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_worker(db_session, trust_admin_current_user)
    svc = ComplianceDocumentService(db_session)

    doc = await svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="compliance-docs/worker-1/dbs.pdf",
        file_name="dbs.pdf",
        current_user=trust_admin_current_user,
    )
    assert doc.id is not None
    assert doc.status == DocumentStatus.uploaded
    assert doc.version_number == 1
    assert doc.supersedes_id is None


@pytest.mark.asyncio
async def test_second_upload_supersedes_first(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_worker(db_session, trust_admin_current_user)
    svc = ComplianceDocumentService(db_session)

    first = await svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="compliance-docs/dbs-v1.pdf",
        file_name="dbs-v1.pdf",
        current_user=trust_admin_current_user,
    )

    second = await svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="compliance-docs/dbs-v2.pdf",
        file_name="dbs-v2.pdf",
        current_user=trust_admin_current_user,
    )

    assert second.version_number == 2
    assert second.supersedes_id == first.id

    # Reload first — should now be superseded
    from app.repositories.compliance_document import ComplianceDocumentRepository
    repo = ComplianceDocumentRepository(db_session)
    reloaded_first = await repo.get_by_id(first.id)
    assert reloaded_first.status == DocumentStatus.superseded


@pytest.mark.asyncio
async def test_hr_approve_document(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_worker(db_session, trust_admin_current_user)
    doc_svc = ComplianceDocumentService(db_session)
    hr_svc = HRReviewService(db_session)

    doc = await doc_svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="compliance-docs/dbs.pdf",
        file_name="dbs.pdf",
        current_user=trust_admin_current_user,
    )
    approved_doc = await hr_svc.approve_document(
        doc.id, notes="Certificate sighted and verified.", current_user=trust_admin_current_user
    )
    assert approved_doc.status == DocumentStatus.approved
    assert approved_doc.reviewed_by == trust_admin_current_user.user_id
    assert approved_doc.review_notes == "Certificate sighted and verified."


@pytest.mark.asyncio
async def test_hr_reject_document(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_worker(db_session, trust_admin_current_user)
    doc_svc = ComplianceDocumentService(db_session)
    hr_svc = HRReviewService(db_session)

    doc = await doc_svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="compliance-docs/dbs.pdf",
        file_name="dbs.pdf",
        current_user=trust_admin_current_user,
    )
    rejected_doc = await hr_svc.reject_document(
        doc.id, reason="Certificate is illegible — please re-upload.", current_user=trust_admin_current_user
    )
    assert rejected_doc.status == DocumentStatus.rejected


@pytest.mark.asyncio
async def test_cannot_approve_already_rejected_document(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_worker(db_session, trust_admin_current_user)
    doc_svc = ComplianceDocumentService(db_session)
    hr_svc = HRReviewService(db_session)

    doc = await doc_svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="compliance-docs/dbs.pdf",
        file_name="dbs.pdf",
        current_user=trust_admin_current_user,
    )
    await hr_svc.reject_document(doc.id, reason="Blurry image — cannot read.", current_user=trust_admin_current_user)

    with pytest.raises(WorkflowError):
        await hr_svc.approve_document(doc.id, current_user=trust_admin_current_user)


@pytest.mark.asyncio
async def test_override_document_status(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_worker(db_session, trust_admin_current_user)
    doc_svc = ComplianceDocumentService(db_session)
    hr_svc = HRReviewService(db_session)

    doc = await doc_svc.record_upload(
        worker_id=worker.id,
        trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="compliance-docs/dbs.pdf",
        file_name="dbs.pdf",
        current_user=trust_admin_current_user,
    )
    overridden = await hr_svc.override_document_status(
        doc.id,
        new_status=DocumentStatus.approved,
        notes="Manual override — original copy physically verified by Head of HR.",
        current_user=trust_admin_current_user,
    )
    assert overridden.status == DocumentStatus.approved
    assert "[OVERRIDE]" in overridden.review_notes


@pytest.mark.asyncio
async def test_list_documents_excludes_superseded_by_default(db_session: AsyncSession, trust_admin_current_user):
    worker = await _create_worker(db_session, trust_admin_current_user)
    svc = ComplianceDocumentService(db_session)

    await svc.record_upload(
        worker_id=worker.id, trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="path/v1.pdf", file_name="v1.pdf",
        current_user=trust_admin_current_user,
    )
    await svc.record_upload(
        worker_id=worker.id, trust_id=TEST_TRUST_ID,
        document_type=DocumentType.dbs_certificate,
        storage_path="path/v2.pdf", file_name="v2.pdf",
        current_user=trust_admin_current_user,
    )

    docs, total = await svc.list_worker_documents(worker.id)
    assert total == 1
    assert docs[0].version_number == 2

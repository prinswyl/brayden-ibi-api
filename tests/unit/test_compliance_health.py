"""
Unit tests for ComplianceDashboardService.compute_health().

Pure function tests — no DB, no fixtures.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.compliance_dashboard import REQUIRED_DOCUMENT_TYPES, ComplianceDashboardService
from app.shared.enums import ComplianceHealth, DocumentStatus, DocumentType


def _make_worker(*, is_amber: bool = False) -> MagicMock:
    w = MagicMock()
    w.is_amber = is_amber
    return w


def _make_doc(
    doc_type: DocumentType = DocumentType.dbs_certificate,
    status: DocumentStatus = DocumentStatus.approved,
    expiry_date: date | None = None,
) -> MagicMock:
    d = MagicMock()
    d.document_type = doc_type.value
    d.status = status
    d.expiry_date = expiry_date
    return d


svc = ComplianceDashboardService.__new__(ComplianceDashboardService)


class TestAmber:
    def test_amber_worker_returns_amber_regardless_of_docs(self):
        worker = _make_worker(is_amber=True)
        docs = [_make_doc(status=DocumentStatus.approved)]
        assert svc.compute_health(worker, docs) == ComplianceHealth.amber


class TestNotStarted:
    def test_no_docs_returns_not_started(self):
        worker = _make_worker()
        assert svc.compute_health(worker, []) == ComplianceHealth.not_started

    def test_only_superseded_docs_returns_not_started(self):
        worker = _make_worker()
        docs = [_make_doc(status=DocumentStatus.superseded)]
        assert svc.compute_health(worker, docs) == ComplianceHealth.not_started


class TestCompliant:
    def test_all_required_approved_and_not_expired_is_compliant(self):
        worker = _make_worker()
        future = date.today() + timedelta(days=365)
        docs = [
            _make_doc(DocumentType.dbs_certificate, DocumentStatus.approved, future),
            _make_doc(DocumentType.right_to_work, DocumentStatus.approved, future),
            _make_doc(DocumentType.proof_of_identity, DocumentStatus.approved, future),
        ]
        assert svc.compute_health(worker, docs) == ComplianceHealth.compliant

    def test_all_required_approved_no_expiry_is_compliant(self):
        worker = _make_worker()
        docs = [
            _make_doc(DocumentType.dbs_certificate, DocumentStatus.approved),
            _make_doc(DocumentType.right_to_work, DocumentStatus.approved),
            _make_doc(DocumentType.proof_of_identity, DocumentStatus.approved),
        ]
        assert svc.compute_health(worker, docs) == ComplianceHealth.compliant


class TestNonCompliant:
    def test_rejected_required_doc_is_non_compliant(self):
        worker = _make_worker()
        docs = [
            _make_doc(DocumentType.dbs_certificate, DocumentStatus.rejected),
            _make_doc(DocumentType.right_to_work, DocumentStatus.approved),
            _make_doc(DocumentType.proof_of_identity, DocumentStatus.approved),
        ]
        assert svc.compute_health(worker, docs) == ComplianceHealth.non_compliant


class TestExpired:
    def test_expired_document_returns_expired(self):
        worker = _make_worker()
        past = date.today() - timedelta(days=1)
        docs = [_make_doc(DocumentType.dbs_certificate, DocumentStatus.expired)]
        assert svc.compute_health(worker, docs) == ComplianceHealth.expired

    def test_approved_doc_with_past_expiry_returns_expired(self):
        worker = _make_worker()
        past = date.today() - timedelta(days=1)
        docs = [
            _make_doc(DocumentType.dbs_certificate, DocumentStatus.approved, past),
            _make_doc(DocumentType.right_to_work, DocumentStatus.approved),
            _make_doc(DocumentType.proof_of_identity, DocumentStatus.approved),
        ]
        assert svc.compute_health(worker, docs) == ComplianceHealth.expired


class TestInProgress:
    def test_some_required_docs_missing_returns_in_progress(self):
        worker = _make_worker()
        docs = [
            _make_doc(DocumentType.dbs_certificate, DocumentStatus.approved),
            # right_to_work and proof_of_identity missing
        ]
        assert svc.compute_health(worker, docs) == ComplianceHealth.in_progress

    def test_uploaded_but_not_reviewed_returns_in_progress(self):
        worker = _make_worker()
        docs = [
            _make_doc(DocumentType.dbs_certificate, DocumentStatus.uploaded),
        ]
        assert svc.compute_health(worker, docs) == ComplianceHealth.in_progress

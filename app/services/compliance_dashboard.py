"""
Compliance dashboard query service.

Provides aggregated, filterable views for HR compliance dashboards.
ComplianceHealth is computed at read time — not stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ComplianceDocument
from app.models.worker import WorkerProfile
from app.repositories.compliance_document import ComplianceDocumentRepository
from app.repositories.worker import WorkerRepository
from app.shared.enums import (
    ComplianceHealth,
    ComplianceStage,
    DocumentStatus,
    DocumentType,
    OnboardingStatus,
)

logger = structlog.get_logger(__name__)

# Documents that must be present and approved for a worker to be "compliant"
REQUIRED_DOCUMENT_TYPES: frozenset[DocumentType] = frozenset({
    DocumentType.dbs_certificate,
    DocumentType.right_to_work,
    DocumentType.proof_of_identity,
})


@dataclass
class WorkerComplianceSummary:
    worker_id: UUID
    onboarding_status: OnboardingStatus
    compliance_stage: ComplianceStage
    compliance_health: ComplianceHealth
    is_amber: bool
    compliance_expires_at: datetime | None
    total_documents: int
    approved_documents: int
    pending_documents: int
    rejected_documents: int
    expiring_soon: int


@dataclass
class DashboardSummary:
    pending_review_count: int
    amber_count: int
    expiring_within_30_days: int
    expiring_within_7_days: int
    onboarding_by_status: dict[str, int]
    recent_rejections: int


class ComplianceDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._workers = WorkerRepository(session)
        self._docs = ComplianceDocumentRepository(session)
        self._session = session

    def compute_health(self, worker: WorkerProfile, documents: list[ComplianceDocument]) -> ComplianceHealth:
        """
        Derive aggregate compliance health from worker state and document statuses.
        Pure function — no DB calls.
        """
        if worker.is_amber:
            return ComplianceHealth.amber

        active_docs = [d for d in documents if d.status != DocumentStatus.superseded]

        if not active_docs:
            return ComplianceHealth.not_started

        statuses = {d.status for d in active_docs}

        # Any expired docs → expired health
        if DocumentStatus.expired in statuses:
            return ComplianceHealth.expired

        # Check required types
        required_types_present = {
            DocumentType(d.document_type)
            for d in active_docs
            if d.status == DocumentStatus.approved
            and d.document_type in {t.value for t in REQUIRED_DOCUMENT_TYPES}
        }

        # If any required type is rejected → non_compliant
        rejected_types = {
            DocumentType(d.document_type)
            for d in active_docs
            if d.status == DocumentStatus.rejected
            and d.document_type in {t.value for t in REQUIRED_DOCUMENT_TYPES}
        }
        if rejected_types:
            return ComplianceHealth.non_compliant

        # All required types approved and not expired
        if REQUIRED_DOCUMENT_TYPES.issubset(required_types_present):
            # Check none are past expiry
            today = datetime.now(UTC).date()
            any_expired = any(
                d.expiry_date and d.expiry_date < today
                for d in active_docs
                if d.status == DocumentStatus.approved
                and d.document_type in {t.value for t in REQUIRED_DOCUMENT_TYPES}
            )
            if any_expired:
                return ComplianceHealth.expired
            return ComplianceHealth.compliant

        # Some required docs present/in-progress but not complete
        return ComplianceHealth.in_progress

    async def get_worker_compliance_summary(
        self, worker_id: UUID
    ) -> WorkerComplianceSummary:
        worker = await self._workers.get_by_id_or_404(worker_id)
        docs, _ = await self._docs.list_for_worker(worker_id, include_superseded=True)

        active_docs = [d for d in docs if d.status != DocumentStatus.superseded]
        health = self.compute_health(worker, active_docs)

        today = datetime.now(UTC).date()
        soon_cutoff = today + timedelta(days=30)
        expiring_soon = sum(
            1 for d in active_docs
            if d.status == DocumentStatus.approved
            and d.expiry_date
            and today <= d.expiry_date <= soon_cutoff
        )

        return WorkerComplianceSummary(
            worker_id=worker.id,
            onboarding_status=OnboardingStatus(worker.onboarding_status),
            compliance_stage=ComplianceStage(worker.compliance_stage),
            compliance_health=health,
            is_amber=worker.is_amber,
            compliance_expires_at=worker.compliance_expires_at,
            total_documents=len(active_docs),
            approved_documents=sum(1 for d in active_docs if d.status == DocumentStatus.approved),
            pending_documents=sum(1 for d in active_docs if d.status in (DocumentStatus.uploaded, DocumentStatus.under_review)),
            rejected_documents=sum(1 for d in active_docs if d.status == DocumentStatus.rejected),
            expiring_soon=expiring_soon,
        )

    async def get_dashboard_summary(self) -> DashboardSummary:
        today = datetime.now(UTC).date()
        cutoff_30 = today + timedelta(days=30)
        cutoff_7 = today + timedelta(days=7)

        # pending review count (documents uploaded/under_review)
        pending_stmt = select(func.count()).select_from(ComplianceDocument).where(
            ComplianceDocument.status.in_([DocumentStatus.uploaded.value, DocumentStatus.under_review.value]),
            ComplianceDocument.deleted_at.is_(None),
        )
        pending_count = (await self._session.execute(pending_stmt)).scalar_one()

        # amber workers
        amber_stmt = select(func.count()).select_from(WorkerProfile).where(
            WorkerProfile.is_amber.is_(True),
            WorkerProfile.deleted_at.is_(None),
        )
        amber_count = (await self._session.execute(amber_stmt)).scalar_one()

        # expiring within 30 days
        exp30_stmt = select(func.count()).select_from(ComplianceDocument).where(
            ComplianceDocument.expiry_date.between(today, cutoff_30),
            ComplianceDocument.status == DocumentStatus.approved.value,
            ComplianceDocument.deleted_at.is_(None),
        )
        exp30 = (await self._session.execute(exp30_stmt)).scalar_one()

        # expiring within 7 days
        exp7_stmt = select(func.count()).select_from(ComplianceDocument).where(
            ComplianceDocument.expiry_date.between(today, cutoff_7),
            ComplianceDocument.status == DocumentStatus.approved.value,
            ComplianceDocument.deleted_at.is_(None),
        )
        exp7 = (await self._session.execute(exp7_stmt)).scalar_one()

        # onboarding status breakdown
        status_stmt = select(
            WorkerProfile.onboarding_status, func.count()
        ).where(WorkerProfile.deleted_at.is_(None)).group_by(WorkerProfile.onboarding_status)
        status_rows = (await self._session.execute(status_stmt)).all()
        by_status = {row[0]: row[1] for row in status_rows}

        # recent rejections (last 7 days)
        from datetime import timezone
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        rejections_stmt = select(func.count()).select_from(ComplianceDocument).where(
            ComplianceDocument.status == DocumentStatus.rejected.value,
            ComplianceDocument.reviewed_at >= seven_days_ago,
            ComplianceDocument.deleted_at.is_(None),
        )
        recent_rejections = (await self._session.execute(rejections_stmt)).scalar_one()

        return DashboardSummary(
            pending_review_count=pending_count,
            amber_count=amber_count,
            expiring_within_30_days=exp30,
            expiring_within_7_days=exp7,
            onboarding_by_status=by_status,
            recent_rejections=recent_rejections,
        )

    async def list_workers_pending_review(
        self, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[WorkerProfile], int]:
        return await self._workers.list_by_onboarding_status(
            OnboardingStatus.submitted, offset=offset, limit=limit
        )

    async def list_workers_under_review(
        self, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[WorkerProfile], int]:
        return await self._workers.list_by_onboarding_status(
            OnboardingStatus.under_review, offset=offset, limit=limit
        )

    async def list_expiring_documents(
        self, *, days_ahead: int = 30, offset: int = 0, limit: int = 50
    ) -> tuple[list[ComplianceDocument], int]:
        cutoff = (datetime.now(UTC) + timedelta(days=days_ahead)).date()
        return await self._docs.list_expiring_before(cutoff, offset=offset, limit=limit)

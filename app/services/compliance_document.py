"""
Compliance document lifecycle service.

Handles upload recording, versioning, and expiry tracking.
Document files are stored by the frontend directly to Supabase Storage
(presigned URL flow). The backend records the storage path and metadata.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser
from app.events import compliance_events as events
from app.models.compliance import ComplianceDocument
from app.models.worker import WorkerProfile
from app.repositories.compliance_document import ComplianceDocumentRepository
from app.repositories.worker import WorkerRepository
from app.shared.enums import AuditAction, ComplianceStage, DocumentStatus, DocumentType
from app.shared.exceptions import ConflictError, NotFoundError, WorkflowError

logger = structlog.get_logger(__name__)


class ComplianceDocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self._docs = ComplianceDocumentRepository(session)
        self._workers = WorkerRepository(session)
        self._session = session

    async def record_upload(
        self,
        *,
        worker_id: UUID,
        trust_id: UUID,
        document_type: DocumentType,
        storage_path: str,
        file_name: str,
        storage_bucket: str = "compliance-docs",
        file_size_bytes: int | None = None,
        mime_type: str | None = None,
        expiry_date: date | None = None,
        label: str | None = None,
        current_user: CurrentUser,
    ) -> ComplianceDocument:
        """Record a document upload. The file itself is already in Supabase Storage."""
        worker = await self._workers.get_by_id_or_404(worker_id)

        # Calculate version number: supersede any existing approved/uploaded doc of same type
        existing = await self._docs.get_latest_by_type(worker_id, document_type)
        version_number = 1
        supersedes_id = None

        if existing:
            if existing.status in (DocumentStatus.approved, DocumentStatus.uploaded, DocumentStatus.under_review):
                version_number = existing.version_number + 1
                supersedes_id = existing.id
            elif existing.status in (DocumentStatus.rejected, DocumentStatus.expired):
                version_number = existing.version_number + 1
                supersedes_id = existing.id

        doc = await self._docs.create(
            trust_id=trust_id,
            worker_id=worker_id,
            document_type=document_type,
            label=label,
            status=DocumentStatus.uploaded,
            storage_path=storage_path,
            storage_bucket=storage_bucket,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            expiry_date=expiry_date,
            version_number=version_number,
            supersedes_id=supersedes_id,
            uploaded_by=current_user.user_id,
        )

        # Mark previous version as superseded
        if existing and supersedes_id:
            await self._docs.update(existing, status=DocumentStatus.superseded)

        # Advance compliance stage if still at not_started/awaiting
        if worker.compliance_stage in (
            ComplianceStage.not_started, ComplianceStage.awaiting_documents
        ):
            await self._workers.update(
                worker, compliance_stage=ComplianceStage.documents_received
            )

        await audit.log(
            self._session,
            action=AuditAction.upload,
            resource_type="compliance_documents",
            resource_id=doc.id,
            trust_id=trust_id,
            user_id=current_user.user_id,
            worker_id=worker_id,
            new_values={
                "document_type": document_type.value,
                "file_name": file_name,
                "version_number": version_number,
                "status": DocumentStatus.uploaded.value,
            },
        )
        return doc

    async def get_document(self, document_id: UUID) -> ComplianceDocument:
        return await self._docs.get_by_id_or_404(document_id)

    async def list_worker_documents(
        self,
        worker_id: UUID,
        *,
        include_superseded: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ComplianceDocument], int]:
        await self._workers.get_by_id_or_404(worker_id)
        return await self._docs.list_for_worker(
            worker_id,
            include_superseded=include_superseded,
            offset=offset,
            limit=limit,
        )

    async def refresh_compliance_expiry(
        self, worker_id: UUID
    ) -> datetime | None:
        """Recalculate and store the earliest expiry date across all approved documents."""
        docs, _ = await self._docs.list_for_worker(worker_id, include_superseded=False)
        approved_with_expiry = [
            d for d in docs
            if d.status == DocumentStatus.approved and d.expiry_date is not None
        ]
        worker = await self._workers.get_by_id_or_404(worker_id)
        if not approved_with_expiry:
            await self._workers.update(worker, compliance_expires_at=None)
            return None

        earliest: date = min(d.expiry_date for d in approved_with_expiry)  # type: ignore[type-var]
        expires_at = datetime(earliest.year, earliest.month, earliest.day, tzinfo=UTC)
        await self._workers.update(worker, compliance_expires_at=expires_at)
        return expires_at

    async def check_and_emit_expiry_warnings(
        self, worker_id: UUID, *, days_warning: int = 30
    ) -> list[ComplianceDocument]:
        cutoff = (datetime.now(UTC) + timedelta(days=days_warning)).date()
        docs, _ = await self._docs.list_expiring_before(cutoff)
        worker_docs = [d for d in docs if d.worker_id == worker_id]

        worker = await self._workers.get_by_id_or_404(worker_id)
        for doc in worker_docs:
            days_left = (doc.expiry_date - datetime.now(UTC).date()).days  # type: ignore[operator]
            await events.dispatch(events.ComplianceExpiringEvent(
                trust_id=worker.trust_id,
                worker_id=worker_id,
                document_id=doc.id,
                document_type=doc.document_type,
                days_until_expiry=days_left,
            ))
        return worker_docs

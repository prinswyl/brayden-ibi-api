"""
HR review workflow service.

HR can: approve, reject, request re-upload, or override document status.
Every action produces an audit log entry and an onboarding note, and
may trigger a compliance event dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser
from app.events import compliance_events as events
from app.models.compliance import ComplianceDocument
from app.repositories.compliance_document import ComplianceDocumentRepository
from app.repositories.onboarding_note import OnboardingNoteRepository
from app.repositories.worker import WorkerRepository
from app.services.compliance_document import ComplianceDocumentService
from app.shared.enums import (
    AuditAction,
    ComplianceStage,
    DocumentStatus,
    NoteVisibility,
    OnboardingNoteType,
)
from app.shared.exceptions import WorkflowError

logger = structlog.get_logger(__name__)

# Statuses from which HR can review
_REVIEWABLE_STATUSES = {DocumentStatus.uploaded, DocumentStatus.under_review}


class HRReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._docs = ComplianceDocumentRepository(session)
        self._workers = WorkerRepository(session)
        self._notes = OnboardingNoteRepository(session)
        self._doc_service = ComplianceDocumentService(session)
        self._session = session

    async def approve_document(
        self,
        document_id: UUID,
        *,
        notes: str | None = None,
        current_user: CurrentUser,
    ) -> ComplianceDocument:
        doc = await self._docs.get_by_id_or_404(document_id)
        if doc.status not in _REVIEWABLE_STATUSES:
            raise WorkflowError(
                f"Document status '{doc.status}' cannot be approved. "
                f"Must be one of: {[s.value for s in _REVIEWABLE_STATUSES]}."
            )

        old_status = doc.status
        doc = await self._docs.update(
            doc,
            status=DocumentStatus.approved,
            reviewed_by=current_user.user_id,
            reviewed_at=datetime.now(UTC),
            review_notes=notes,
        )

        await self._append_document_note(
            doc, f"Document approved.{f' Note: {notes}' if notes else ''}",
            current_user, note_type=OnboardingNoteType.hr_review
        )
        await audit.log(
            self._session,
            action=AuditAction.approve,
            resource_type="compliance_documents",
            resource_id=doc.id,
            trust_id=doc.trust_id,
            user_id=current_user.user_id,
            worker_id=doc.worker_id,
            old_values={"status": old_status.value if hasattr(old_status, "value") else str(old_status)},
            new_values={"status": DocumentStatus.approved.value, "review_notes": notes},
        )
        await events.dispatch(events.DocumentApprovedEvent(
            trust_id=doc.trust_id,
            worker_id=doc.worker_id,
            document_id=doc.id,
            document_type=doc.document_type,
            approved_by=current_user.user_id,
        ))

        # Recalculate earliest compliance expiry after each approval
        await self._doc_service.refresh_compliance_expiry(doc.worker_id)
        await self._recalculate_compliance_stage(doc.worker_id)
        return doc

    async def reject_document(
        self,
        document_id: UUID,
        *,
        reason: str,
        current_user: CurrentUser,
    ) -> ComplianceDocument:
        doc = await self._docs.get_by_id_or_404(document_id)
        if doc.status not in _REVIEWABLE_STATUSES:
            raise WorkflowError(
                f"Document status '{doc.status}' cannot be rejected. "
                f"Must be one of: {[s.value for s in _REVIEWABLE_STATUSES]}."
            )

        old_status = doc.status
        doc = await self._docs.update(
            doc,
            status=DocumentStatus.rejected,
            reviewed_by=current_user.user_id,
            reviewed_at=datetime.now(UTC),
            review_notes=reason,
        )

        await self._append_document_note(
            doc, f"Document rejected. Reason: {reason}",
            current_user, note_type=OnboardingNoteType.hr_review
        )
        await audit.log(
            self._session,
            action=AuditAction.reject,
            resource_type="compliance_documents",
            resource_id=doc.id,
            trust_id=doc.trust_id,
            user_id=current_user.user_id,
            worker_id=doc.worker_id,
            old_values={"status": old_status.value if hasattr(old_status, "value") else str(old_status)},
            new_values={"status": DocumentStatus.rejected.value, "review_notes": reason},
        )
        await events.dispatch(events.DocumentRejectedEvent(
            trust_id=doc.trust_id,
            worker_id=doc.worker_id,
            document_id=doc.id,
            document_type=doc.document_type,
            rejected_by=current_user.user_id,
            reason=reason,
        ))
        return doc

    async def request_reupload(
        self,
        document_id: UUID,
        *,
        reason: str,
        current_user: CurrentUser,
    ) -> ComplianceDocument:
        doc = await self._docs.get_by_id_or_404(document_id)
        if doc.status not in {*_REVIEWABLE_STATUSES, DocumentStatus.rejected}:
            raise WorkflowError(
                f"Cannot request re-upload for document in status '{doc.status}'."
            )

        old_status = doc.status
        doc = await self._docs.update(
            doc,
            status=DocumentStatus.rejected,
            reviewed_by=current_user.user_id,
            reviewed_at=datetime.now(UTC),
            review_notes=f"Re-upload requested: {reason}",
        )

        await self._append_document_note(
            doc, f"Re-upload requested. Reason: {reason}",
            current_user, note_type=OnboardingNoteType.hr_review
        )
        await audit.log(
            self._session,
            action=AuditAction.reject,
            resource_type="compliance_documents",
            resource_id=doc.id,
            trust_id=doc.trust_id,
            user_id=current_user.user_id,
            worker_id=doc.worker_id,
            old_values={"status": old_status.value if hasattr(old_status, "value") else str(old_status)},
            new_values={"status": DocumentStatus.rejected.value, "reason": f"Re-upload: {reason}"},
        )
        await events.dispatch(events.DocumentReuploadRequestedEvent(
            trust_id=doc.trust_id,
            worker_id=doc.worker_id,
            document_id=doc.id,
            document_type=doc.document_type,
            requested_by=current_user.user_id,
            reason=reason,
        ))
        return doc

    async def override_document_status(
        self,
        document_id: UUID,
        *,
        new_status: DocumentStatus,
        notes: str,
        current_user: CurrentUser,
    ) -> ComplianceDocument:
        """HR admin override — allows setting any status with a mandatory note."""
        if new_status == DocumentStatus.superseded:
            raise WorkflowError("Cannot manually set a document to 'superseded'.")

        doc = await self._docs.get_by_id_or_404(document_id)
        old_status = doc.status
        doc = await self._docs.update(
            doc,
            status=new_status,
            reviewed_by=current_user.user_id,
            reviewed_at=datetime.now(UTC),
            review_notes=f"[OVERRIDE] {notes}",
        )

        await self._append_document_note(
            doc,
            f"Status overridden: {old_status} → {new_status.value}. Note: {notes}",
            current_user,
            note_type=OnboardingNoteType.hr_review,
        )
        await audit.log(
            self._session,
            action=AuditAction.update,
            resource_type="compliance_documents",
            resource_id=doc.id,
            trust_id=doc.trust_id,
            user_id=current_user.user_id,
            worker_id=doc.worker_id,
            old_values={"status": old_status.value if hasattr(old_status, "value") else str(old_status)},
            new_values={"status": new_status.value, "override_notes": notes},
            metadata={"is_override": True},
        )
        if new_status == DocumentStatus.approved:
            await self._doc_service.refresh_compliance_expiry(doc.worker_id)
        await self._recalculate_compliance_stage(doc.worker_id)
        return doc

    async def get_pending_review_queue(
        self, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[ComplianceDocument], int]:
        return await self._docs.list_by_status(
            DocumentStatus.uploaded, offset=offset, limit=limit
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _append_document_note(
        self,
        doc: ComplianceDocument,
        content: str,
        current_user: CurrentUser,
        *,
        note_type: OnboardingNoteType,
    ) -> None:
        await self._notes.create(
            trust_id=doc.trust_id,
            worker_id=doc.worker_id,
            author_id=current_user.user_id,
            note_type=note_type,
            content=content,
            visibility=NoteVisibility.internal,
            created_at=datetime.now(UTC),
        )

    async def _recalculate_compliance_stage(self, worker_id: UUID) -> None:
        """Nudge the internal compliance stage based on current document states."""
        docs, _ = await self._docs.list_for_worker(worker_id, include_superseded=False)
        worker = await self._workers.get_by_id_or_404(worker_id)

        statuses = {d.status for d in docs}

        # If any are still uploaded/under_review, we're in review
        if DocumentStatus.uploaded in statuses or DocumentStatus.under_review in statuses:
            if worker.compliance_stage != ComplianceStage.under_review:
                await self._workers.update(worker, compliance_stage=ComplianceStage.under_review)
            return

        # If any are rejected, clearance denied
        if DocumentStatus.rejected in statuses:
            await self._workers.update(worker, compliance_stage=ComplianceStage.clearance_denied)
            return

        # All approved — grant clearance (HR still makes final onboarding_status call)
        if statuses and all(s == DocumentStatus.approved for s in statuses):
            await self._workers.update(worker, compliance_stage=ComplianceStage.clearance_granted)

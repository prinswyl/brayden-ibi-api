"""
Onboarding lifecycle service.

Owns all transitions of WorkerProfile.onboarding_status. Every transition:
  1. Validates the transition is legal
  2. Updates the worker record
  3. Appends an OnboardingNote for audit visibility
  4. Writes a structured audit log entry
  5. Dispatches a compliance event hook
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app import core
from app.core import audit
from app.core.auth import CurrentUser
from app.events import compliance_events as events
from app.models.compliance import OnboardingNote
from app.models.worker import WorkerProfile
from app.repositories.worker import WorkerRepository
from app.repositories.onboarding_note import OnboardingNoteRepository
from app.shared.enums import (
    AuditAction,
    ComplianceStage,
    NoteVisibility,
    OnboardingNoteType,
    OnboardingStatus,
)
from app.shared.exceptions import ConflictError, NotFoundError, WorkflowError

logger = structlog.get_logger(__name__)

# Legal onboarding status transitions: {from_status: {allowed_to_statuses}}
_TRANSITIONS: dict[OnboardingStatus, set[OnboardingStatus]] = {
    OnboardingStatus.draft: {OnboardingStatus.submitted},
    OnboardingStatus.submitted: {
        OnboardingStatus.under_review,
        OnboardingStatus.rejected,
        OnboardingStatus.draft,           # HR sends back for completion
    },
    OnboardingStatus.under_review: {
        OnboardingStatus.approved,
        OnboardingStatus.rejected,
        OnboardingStatus.submitted,       # HR requests more info — back to submitted
    },
    OnboardingStatus.approved: {
        OnboardingStatus.suspended,
        OnboardingStatus.expired,
        OnboardingStatus.under_review,    # re-review if compliance lapses
    },
    OnboardingStatus.rejected: {
        OnboardingStatus.draft,           # worker can restart
        OnboardingStatus.submitted,       # HR re-submits on worker's behalf
    },
    OnboardingStatus.suspended: {
        OnboardingStatus.approved,        # reinstate
        OnboardingStatus.rejected,
    },
    OnboardingStatus.expired: {
        OnboardingStatus.under_review,    # re-review cycle
        OnboardingStatus.rejected,
    },
}


def _assert_transition_valid(
    current: OnboardingStatus, target: OnboardingStatus
) -> None:
    allowed = _TRANSITIONS.get(current, set())
    if target not in allowed:
        raise WorkflowError(
            f"Cannot move onboarding status from '{current.value}' to '{target.value}'. "
            f"Allowed targets: {[s.value for s in allowed] or 'none'}."
        )


class OnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._workers = WorkerRepository(session)
        self._notes = OnboardingNoteRepository(session)
        self._session = session

    async def get_worker(self, worker_id: UUID) -> WorkerProfile:
        return await self._workers.get_by_id_or_404(worker_id)

    async def create_worker_profile(
        self,
        *,
        user_id: UUID,
        trust_id: UUID,
        current_user: CurrentUser,
    ) -> WorkerProfile:
        existing = await self._workers.get_by_user_id(user_id)
        if existing:
            raise ConflictError(f"WorkerProfile already exists for user_id={user_id}")

        worker = await self._workers.create(
            user_id=user_id,
            trust_id=trust_id,
            onboarding_status=OnboardingStatus.draft,
            compliance_stage=ComplianceStage.not_started,
        )
        await self._append_note(
            worker_id=worker.id,
            trust_id=trust_id,
            author_id=current_user.user_id,
            content="Worker profile created.",
            note_type=OnboardingNoteType.system,
        )
        await audit.log(
            self._session,
            action=AuditAction.create,
            resource_type="worker_profiles",
            resource_id=worker.id,
            trust_id=trust_id,
            user_id=current_user.user_id,
            worker_id=worker.id,
            new_values={"onboarding_status": OnboardingStatus.draft.value},
        )
        return worker

    async def submit_for_review(
        self,
        worker_id: UUID,
        *,
        current_user: CurrentUser,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        _assert_transition_valid(worker.onboarding_status, OnboardingStatus.submitted)

        old_status = worker.onboarding_status
        worker = await self._workers.update(
            worker,
            onboarding_status=OnboardingStatus.submitted,
            compliance_stage=ComplianceStage.documents_received,
        )
        await self._record_transition(worker, old_status, OnboardingStatus.submitted, current_user)
        await events.dispatch(events.OnboardingSubmittedEvent(
            trust_id=worker.trust_id,
            worker_id=worker.id,
            submitted_by=current_user.user_id,
        ))
        return worker

    async def start_review(
        self,
        worker_id: UUID,
        *,
        current_user: CurrentUser,
        notes: str | None = None,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        _assert_transition_valid(worker.onboarding_status, OnboardingStatus.under_review)

        old_status = worker.onboarding_status
        worker = await self._workers.update(
            worker,
            onboarding_status=OnboardingStatus.under_review,
            compliance_stage=ComplianceStage.under_review,
        )
        await self._record_transition(
            worker, old_status, OnboardingStatus.under_review, current_user, notes=notes
        )
        return worker

    async def approve_worker(
        self,
        worker_id: UUID,
        *,
        current_user: CurrentUser,
        notes: str | None = None,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        _assert_transition_valid(worker.onboarding_status, OnboardingStatus.approved)

        old_status = worker.onboarding_status
        worker = await self._workers.update(
            worker,
            onboarding_status=OnboardingStatus.approved,
            compliance_stage=ComplianceStage.clearance_granted,
            is_amber=False,
        )
        await self._record_transition(
            worker, old_status, OnboardingStatus.approved, current_user, notes=notes
        )
        await events.dispatch(events.OnboardingApprovedEvent(
            trust_id=worker.trust_id,
            worker_id=worker.id,
            approved_by=current_user.user_id,
        ))
        return worker

    async def reject_worker(
        self,
        worker_id: UUID,
        *,
        reason: str,
        current_user: CurrentUser,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        _assert_transition_valid(worker.onboarding_status, OnboardingStatus.rejected)

        old_status = worker.onboarding_status
        worker = await self._workers.update(
            worker,
            onboarding_status=OnboardingStatus.rejected,
            compliance_stage=ComplianceStage.clearance_denied,
        )
        await self._record_transition(
            worker, old_status, OnboardingStatus.rejected, current_user, notes=reason
        )
        await events.dispatch(events.OnboardingRejectedEvent(
            trust_id=worker.trust_id,
            worker_id=worker.id,
            rejected_by=current_user.user_id,
            reason=reason,
        ))
        return worker

    async def suspend_worker(
        self,
        worker_id: UUID,
        *,
        reason: str,
        current_user: CurrentUser,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        _assert_transition_valid(worker.onboarding_status, OnboardingStatus.suspended)

        old_status = worker.onboarding_status
        worker = await self._workers.update(
            worker,
            onboarding_status=OnboardingStatus.suspended,
            suspended_at=datetime.now(UTC),
            suspension_reason=reason,
            suspended_by_id=current_user.user_id,
        )
        await self._record_transition(
            worker, old_status, OnboardingStatus.suspended, current_user, notes=reason
        )
        await events.dispatch(events.WorkerSuspendedEvent(
            trust_id=worker.trust_id,
            worker_id=worker.id,
            suspended_by=current_user.user_id,
            reason=reason,
        ))
        return worker

    async def reinstate_worker(
        self,
        worker_id: UUID,
        *,
        current_user: CurrentUser,
        notes: str | None = None,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        _assert_transition_valid(worker.onboarding_status, OnboardingStatus.approved)

        old_status = worker.onboarding_status
        worker = await self._workers.update(
            worker,
            onboarding_status=OnboardingStatus.approved,
            compliance_stage=ComplianceStage.clearance_granted,
            suspended_at=None,
            suspension_reason=None,
            suspended_by_id=None,
        )
        await self._record_transition(
            worker, old_status, OnboardingStatus.approved, current_user,
            notes=notes or "Worker reinstated."
        )
        return worker

    async def mark_expired(
        self,
        worker_id: UUID,
        *,
        current_user: CurrentUser,
        notes: str | None = None,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        _assert_transition_valid(worker.onboarding_status, OnboardingStatus.expired)

        old_status = worker.onboarding_status
        worker = await self._workers.update(
            worker,
            onboarding_status=OnboardingStatus.expired,
            compliance_stage=ComplianceStage.recheck_required,
        )
        await self._record_transition(
            worker, old_status, OnboardingStatus.expired, current_user,
            notes=notes or "Compliance expired — re-check required."
        )
        return worker

    async def set_amber(
        self,
        worker_id: UUID,
        *,
        reason: str,
        current_user: CurrentUser,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        worker = await self._workers.update(worker, is_amber=True)
        await self._append_note(
            worker_id=worker.id,
            trust_id=worker.trust_id,
            author_id=current_user.user_id,
            content=f"Worker flagged amber: {reason}",
            note_type=OnboardingNoteType.hr_review,
        )
        await audit.log(
            self._session,
            action=AuditAction.update,
            resource_type="worker_profiles",
            resource_id=worker.id,
            trust_id=worker.trust_id,
            user_id=current_user.user_id,
            worker_id=worker.id,
            old_values={"is_amber": False},
            new_values={"is_amber": True, "reason": reason},
        )
        return worker

    async def clear_amber(
        self,
        worker_id: UUID,
        *,
        current_user: CurrentUser,
    ) -> WorkerProfile:
        worker = await self._workers.get_by_id_or_404(worker_id)
        worker = await self._workers.update(worker, is_amber=False)
        await self._append_note(
            worker_id=worker.id,
            trust_id=worker.trust_id,
            author_id=current_user.user_id,
            content="Amber flag cleared.",
            note_type=OnboardingNoteType.hr_review,
        )
        await audit.log(
            self._session,
            action=AuditAction.update,
            resource_type="worker_profiles",
            resource_id=worker.id,
            trust_id=worker.trust_id,
            user_id=current_user.user_id,
            worker_id=worker.id,
            old_values={"is_amber": True},
            new_values={"is_amber": False},
        )
        return worker

    async def add_manual_note(
        self,
        worker_id: UUID,
        *,
        content: str,
        visibility: NoteVisibility,
        current_user: CurrentUser,
    ) -> OnboardingNote:
        worker = await self._workers.get_by_id_or_404(worker_id)
        return await self._append_note(
            worker_id=worker.id,
            trust_id=worker.trust_id,
            author_id=current_user.user_id,
            content=content,
            note_type=OnboardingNoteType.manual,
            visibility=visibility,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _record_transition(
        self,
        worker: WorkerProfile,
        old_status: OnboardingStatus,
        new_status: OnboardingStatus,
        current_user: CurrentUser,
        *,
        notes: str | None = None,
    ) -> None:
        content = f"Status changed: {old_status.value} → {new_status.value}."
        if notes:
            content = f"{content} Note: {notes}"

        await self._append_note(
            worker_id=worker.id,
            trust_id=worker.trust_id,
            author_id=current_user.user_id,
            content=content,
            note_type=OnboardingNoteType.status_change,
            previous_status=old_status,
            new_status=new_status,
        )
        await audit.log(
            self._session,
            action=AuditAction.update,
            resource_type="worker_profiles",
            resource_id=worker.id,
            trust_id=worker.trust_id,
            user_id=current_user.user_id,
            worker_id=worker.id,
            old_values={"onboarding_status": old_status.value},
            new_values={"onboarding_status": new_status.value},
            metadata={"notes": notes} if notes else None,
        )

    async def _append_note(
        self,
        *,
        worker_id: UUID,
        trust_id: uuid.UUID,
        author_id: UUID,
        content: str,
        note_type: OnboardingNoteType = OnboardingNoteType.manual,
        visibility: NoteVisibility = NoteVisibility.internal,
        previous_status: OnboardingStatus | None = None,
        new_status: OnboardingStatus | None = None,
    ) -> OnboardingNote:
        from app.repositories.onboarding_note import OnboardingNoteRepository
        repo = OnboardingNoteRepository(self._session)
        return await repo.create(
            trust_id=trust_id,
            worker_id=worker_id,
            author_id=author_id,
            note_type=note_type,
            content=content,
            visibility=visibility,
            previous_status=previous_status,
            new_status=new_status,
            created_at=datetime.now(UTC),
        )

"""
First-shift DBS verification service.

When a worker attends their first shift at a school, a receptionist or admin
must physically sight the worker's DBS certificate and confirm it matches.
This verification is school-scoped — a worker verified at School A still needs
verification at School B.

Once verified, the record is permanent (no soft delete, no override).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser
from app.events import compliance_events as events
from app.models.verification import FirstShiftVerification
from app.repositories.first_shift_verification import FirstShiftVerificationRepository
from app.repositories.worker import WorkerRepository
from app.shared.enums import AuditAction, OnboardingStatus
from app.shared.exceptions import ConflictError, WorkflowError

logger = structlog.get_logger(__name__)


class FirstShiftService:
    def __init__(self, session: AsyncSession) -> None:
        self._verifications = FirstShiftVerificationRepository(session)
        self._workers = WorkerRepository(session)
        self._session = session

    async def verify_first_shift(
        self,
        *,
        worker_id: UUID,
        school_id: UUID,
        trust_id: UUID,
        dbs_seen_and_matched: bool,
        verification_date: date | None = None,
        notes: str | None = None,
        current_user: CurrentUser,
    ) -> FirstShiftVerification:
        worker = await self._workers.get_by_id_or_404(worker_id)

        # Worker must be approved before first-shift verification
        if worker.onboarding_status != OnboardingStatus.approved:
            raise WorkflowError(
                f"First-shift verification requires an approved worker. "
                f"Current status: '{worker.onboarding_status}'."
            )

        # Idempotency: already verified at this school
        existing = await self._verifications.get_for_worker_school(worker_id, school_id)
        if existing:
            raise ConflictError(
                f"FirstShiftVerification already exists for worker_id={worker_id}, school_id={school_id}"
            )

        verification = await self._verifications.create(
            trust_id=trust_id,
            worker_id=worker_id,
            school_id=school_id,
            verified_by_id=current_user.user_id,
            verification_date=verification_date or datetime.now(UTC).date(),
            dbs_seen_and_matched=dbs_seen_and_matched,
            notes=notes,
            created_at=datetime.now(UTC),
        )

        await audit.log(
            self._session,
            action=AuditAction.create,
            resource_type="first_shift_verifications",
            resource_id=verification.id,
            trust_id=trust_id,
            user_id=current_user.user_id,
            worker_id=worker_id,
            school_id=school_id,
            new_values={
                "dbs_seen_and_matched": dbs_seen_and_matched,
                "verification_date": str(verification.verification_date),
            },
        )
        await events.dispatch(events.FirstShiftVerifiedEvent(
            trust_id=trust_id,
            worker_id=worker_id,
            school_id=school_id,
            verified_by=current_user.user_id,
        ))

        # If this is their first verified school, set the trust-level flag
        all_verifications = await self._verifications.list_for_worker(worker_id)
        if len(all_verifications) == 1:
            await self._workers.update(worker, first_shift_cleared=True)

        return verification

    async def get_verification_status(
        self, worker_id: UUID, school_id: UUID
    ) -> FirstShiftVerification | None:
        return await self._verifications.get_for_worker_school(worker_id, school_id)

    async def list_worker_verifications(
        self, worker_id: UUID
    ) -> list[FirstShiftVerification]:
        await self._workers.get_by_id_or_404(worker_id)
        return await self._verifications.list_for_worker(worker_id)

    async def list_school_verifications(
        self,
        school_id: UUID,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> list[FirstShiftVerification]:
        return await self._verifications.list_for_school(
            school_id, offset=offset, limit=limit
        )

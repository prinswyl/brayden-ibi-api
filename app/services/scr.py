"""
Single Central Record (SCR) service.

Owns all mutations to scr_records and computes the SCR status.
Every field update is written to the audit log with who changed it and when.

SCR status transitions:
  incomplete               → all other states (computed, never manually set)
  pending_review           → HR has submitted worker for review
  verified_pending_physical → digital/remote checks clear; awaiting in-person ID
  compliant                → physical ID confirmed; all mandatory checks satisfied
  suspended                → manually suspended by HR
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser
from app.models.scr import SCRRecord, WorkerAgreement, WorkerReference, WorkerSafeguardingInduction
from app.shared.enums import AuditAction, DBSApplicationStatus, IDVerificationMethod, ReferenceStatus, SCRStatus
from app.shared.exceptions import ConflictError, NotFoundError, WorkflowError

logger = structlog.get_logger(__name__)


class SCRService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── SCR record CRUD ───────────────────────────────────────────────────────

    async def get_or_create(self, worker_id: UUID, trust_id: UUID) -> SCRRecord:
        result = await self._session.execute(
            select(SCRRecord).where(SCRRecord.worker_id == worker_id)
        )
        scr = result.scalar_one_or_none()
        if scr:
            return scr
        scr = SCRRecord(
            worker_id=worker_id,
            trust_id=trust_id,
            scr_status=SCRStatus.incomplete,
        )
        self._session.add(scr)
        await self._session.flush()
        return scr

    async def get_by_worker(self, worker_id: UUID) -> SCRRecord | None:
        result = await self._session.execute(
            select(SCRRecord).where(SCRRecord.worker_id == worker_id)
        )
        return result.scalar_one_or_none()

    async def get_by_worker_or_404(self, worker_id: UUID) -> SCRRecord:
        scr = await self.get_by_worker(worker_id)
        if not scr:
            raise NotFoundError(f"SCR record not found for worker {worker_id}")
        return scr

    # ── ID verification ───────────────────────────────────────────────────────

    async def set_id_verification_method(
        self,
        worker_id: UUID,
        method: IDVerificationMethod,
        *,
        current_user: CurrentUser,
    ) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        old = scr.id_verification_method
        scr.id_verification_method = method
        # school_in_person satisfies BOTH initial and physical in one action
        if method == IDVerificationMethod.school_in_person:
            scr.initial_id_checked_date = date.today()
            scr.initial_id_checked_by = current_user.user_id
        await self._audit(scr, "id_verification_method", old, method, current_user)
        await self._recompute_status(scr)
        return scr

    async def record_initial_id_check(
        self,
        worker_id: UUID,
        *,
        checked_date: date,
        notes: str | None,
        current_user: CurrentUser,
    ) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        scr.initial_id_checked_date = checked_date
        scr.initial_id_checked_by = current_user.user_id
        scr.initial_id_notes = notes
        # school_in_person: also mark physical confirmed
        if scr.id_verification_method == IDVerificationMethod.school_in_person:
            scr.physical_id_confirmed = True
            scr.physical_id_confirmed_date = checked_date
            scr.physical_id_confirmed_by = current_user.user_id
        await self._audit(scr, "initial_id_checked_date", None, str(checked_date), current_user)
        await self._recompute_status(scr)
        return scr

    async def confirm_physical_id(
        self,
        worker_id: UUID,
        *,
        confirmed_date: date,
        location: str,
        current_user: CurrentUser,
    ) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        if scr.physical_id_confirmed:
            raise ConflictError("Physical ID has already been confirmed for this worker.")
        scr.physical_id_confirmed = True
        scr.physical_id_confirmed_date = confirmed_date
        scr.physical_id_confirmed_by = current_user.user_id
        scr.physical_id_confirmed_location = location
        await self._audit(scr, "physical_id_confirmed", "false", "true", current_user)
        await self._recompute_status(scr)
        return scr

    # ── DBS ──────────────────────────────────────────────────────────────────

    async def update_dbs(
        self,
        worker_id: UUID,
        *,
        certificate_number: str | None = None,
        issue_date: date | None = None,
        checked_date: date | None = None,
        application_status: DBSApplicationStatus | None = None,
        update_service_linked: bool | None = None,
        last_update_check_date: date | None = None,
        last_update_result: str | None = None,
        external_portal_reference: str | None = None,
        current_user: CurrentUser,
    ) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        if certificate_number is not None:
            scr.dbs_certificate_number = certificate_number
        if issue_date is not None:
            scr.dbs_issue_date = issue_date
        if checked_date is not None:
            scr.dbs_checked_date = checked_date
            scr.dbs_verified_by = current_user.user_id
        if application_status is not None:
            scr.dbs_application_status = application_status
        if update_service_linked is not None:
            scr.dbs_update_service_linked = update_service_linked
        if last_update_check_date is not None:
            scr.dbs_last_update_check_date = last_update_check_date
        if last_update_result is not None:
            scr.dbs_last_update_result = last_update_result
        if external_portal_reference is not None:
            scr.external_dbs_portal_reference = external_portal_reference
        await self._audit(scr, "dbs_fields_updated", None, "updated", current_user)
        await self._recompute_status(scr)
        return scr

    # ── RTW ──────────────────────────────────────────────────────────────────

    async def record_rtw_check(
        self,
        worker_id: UUID,
        *,
        checked_date: date,
        evidence_type: str,
        current_user: CurrentUser,
    ) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        scr.rtw_checked_date = checked_date
        scr.rtw_verified_by = current_user.user_id
        scr.rtw_evidence_type = evidence_type
        await self._audit(scr, "rtw_checked_date", None, str(checked_date), current_user)
        await self._recompute_status(scr)
        return scr

    # ── References ───────────────────────────────────────────────────────────

    async def advance_reference_status(
        self,
        worker_id: UUID,
        reference_number: int,
        new_status: ReferenceStatus,
        *,
        current_user: CurrentUser,
    ) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        now = datetime.now(UTC)
        if reference_number == 1:
            scr.reference_1_status = new_status
            if new_status == ReferenceStatus.verified:
                scr.reference_1_verified_date = now.date()
                scr.reference_1_verified_by = current_user.user_id
        elif reference_number == 2:
            scr.reference_2_status = new_status
            if new_status == ReferenceStatus.verified:
                scr.reference_2_verified_date = now.date()
                scr.reference_2_verified_by = current_user.user_id
        else:
            raise WorkflowError("reference_number must be 1 or 2")
        await self._audit(scr, f"reference_{reference_number}_status", None, new_status, current_user)
        await self._recompute_status(scr)
        return scr

    # ── Other checks ─────────────────────────────────────────────────────────

    async def record_barred_list_check(self, worker_id: UUID, *, checked_date: date, current_user: CurrentUser) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        scr.barred_list_checked_date = checked_date
        scr.barred_list_verified_by = current_user.user_id
        await self._audit(scr, "barred_list_checked_date", None, str(checked_date), current_user)
        return scr

    async def record_tra_check(self, worker_id: UUID, *, checked_date: date, current_user: CurrentUser) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        scr.tra_prohibition_checked_date = checked_date
        scr.tra_prohibition_verified_by = current_user.user_id
        await self._audit(scr, "tra_prohibition_checked_date", None, str(checked_date), current_user)
        return scr

    async def record_qualifications_check(self, worker_id: UUID, *, checked_date: date, current_user: CurrentUser) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        scr.qualifications_checked_date = checked_date
        scr.qualifications_verified_by = current_user.user_id
        await self._audit(scr, "qualifications_checked_date", None, str(checked_date), current_user)
        return scr

    # ── Status computation ────────────────────────────────────────────────────

    async def _recompute_status(self, scr: SCRRecord) -> None:
        """Derives SCR status from field completeness. Called after every mutation."""
        if scr.scr_status == SCRStatus.suspended:
            return  # suspension is manual; never auto-lifted

        new_status = self._derive_status(scr)
        if new_status != scr.scr_status:
            logger.info("scr_status_transition", worker_id=scr.worker_id, old=scr.scr_status, new=new_status)
            scr.scr_status = new_status

    @staticmethod
    def _derive_status(scr: SCRRecord) -> SCRStatus:
        # Must have: initial ID check, DBS check done or in_flight, RTW checked, references both verified
        digital_checks_complete = (
            scr.initial_id_checked_date is not None
            and scr.dbs_application_status in (DBSApplicationStatus.in_flight, DBSApplicationStatus.completed)
            and scr.rtw_checked_date is not None
            and scr.reference_1_status == ReferenceStatus.verified
            and scr.reference_2_status == ReferenceStatus.verified
        )
        if not digital_checks_complete:
            return SCRStatus.incomplete

        if scr.physical_id_confirmed:
            return SCRStatus.compliant

        # Digital checks done, physical ID still pending
        return SCRStatus.verified_pending_physical

    async def suspend(self, worker_id: UUID, *, current_user: CurrentUser) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        old = scr.scr_status
        scr.scr_status = SCRStatus.suspended
        await self._audit(scr, "scr_status", old, SCRStatus.suspended, current_user)
        return scr

    async def unsuspend(self, worker_id: UUID, *, current_user: CurrentUser) -> SCRRecord:
        scr = await self.get_by_worker_or_404(worker_id)
        if scr.scr_status != SCRStatus.suspended:
            raise WorkflowError("Worker is not currently suspended on the SCR.")
        await self._recompute_status(scr)
        await self._audit(scr, "scr_status", SCRStatus.suspended, scr.scr_status, current_user)
        return scr

    # ── Export ────────────────────────────────────────────────────────────────

    async def export_csv(self, trust_id: UUID) -> str:
        result = await self._session.execute(
            select(SCRRecord).where(SCRRecord.trust_id == trust_id)
        )
        records = result.scalars().all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "worker_id", "scr_status",
            "id_verification_method", "initial_id_checked_date",
            "physical_id_confirmed", "physical_id_confirmed_date", "physical_id_confirmed_location",
            "rtw_checked_date", "rtw_evidence_type",
            "dbs_application_status", "dbs_certificate_number", "dbs_issue_date", "dbs_checked_date",
            "dbs_update_service_linked", "dbs_last_update_check_date", "dbs_last_update_result",
            "barred_list_checked_date", "tra_prohibition_checked_date", "qualifications_checked_date",
            "reference_1_status", "reference_1_verified_date",
            "reference_2_status", "reference_2_verified_date",
            "overseas_checks_required",
        ])
        for r in records:
            writer.writerow([
                r.worker_id, r.scr_status.value,
                r.id_verification_method.value, r.initial_id_checked_date,
                r.physical_id_confirmed, r.physical_id_confirmed_date, r.physical_id_confirmed_location,
                r.rtw_checked_date, r.rtw_evidence_type,
                r.dbs_application_status.value, r.dbs_certificate_number, r.dbs_issue_date, r.dbs_checked_date,
                r.dbs_update_service_linked, r.dbs_last_update_check_date,
                r.dbs_last_update_result.value if r.dbs_last_update_result else "",
                r.barred_list_checked_date, r.tra_prohibition_checked_date, r.qualifications_checked_date,
                r.reference_1_status.value, r.reference_1_verified_date,
                r.reference_2_status.value, r.reference_2_verified_date,
                r.overseas_checks_required,
            ])
        return buf.getvalue()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _audit(
        self,
        scr: SCRRecord,
        field: str,
        old_value: object,
        new_value: object,
        current_user: CurrentUser,
    ) -> None:
        await audit.log(
            self._session,
            action=AuditAction.update,
            resource_type="scr_records",
            resource_id=scr.id,
            trust_id=scr.trust_id,
            user_id=current_user.user_id,
            worker_id=scr.worker_id,
            old_values={field: str(old_value) if old_value is not None else None},
            new_values={field: str(new_value) if new_value is not None else None},
        )

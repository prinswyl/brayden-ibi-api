"""Pydantic schemas for the SCR (Single Central Record) domain."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.enums import (
    DBSApplicationStatus,
    DBSUpdateResult,
    IDVerificationMethod,
    ReferenceStatus,
    SCRStatus,
)


class SCRRecordResponse(BaseModel):
    id: UUID
    worker_id: UUID
    scr_status: SCRStatus

    id_verification_method: IDVerificationMethod
    initial_id_checked_date: date | None
    initial_id_notes: str | None

    physical_id_confirmed: bool
    physical_id_confirmed_date: date | None
    physical_id_confirmed_location: str | None

    rtw_checked_date: date | None
    rtw_evidence_type: str | None

    dbs_application_status: DBSApplicationStatus
    dbs_certificate_number: str | None
    dbs_issue_date: date | None
    dbs_checked_date: date | None
    dbs_update_service_linked: bool
    dbs_last_update_check_date: date | None
    dbs_last_update_result: DBSUpdateResult
    external_dbs_portal_reference: str | None

    barred_list_checked_date: date | None
    tra_prohibition_checked_date: date | None
    qualifications_checked_date: date | None

    reference_1_status: ReferenceStatus
    reference_1_verified_date: date | None
    reference_2_status: ReferenceStatus
    reference_2_verified_date: date | None

    overseas_checks_required: bool
    overseas_checks_details: str | None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Request bodies ────────────────────────────────────────────────────────────

class SetIDVerificationMethodRequest(BaseModel):
    method: IDVerificationMethod


class RecordInitialIDCheckRequest(BaseModel):
    checked_date: date
    notes: str | None = None


class ConfirmPhysicalIDRequest(BaseModel):
    confirmed_date: date
    location: str = Field(..., min_length=2, max_length=200)


class UpdateDBSRequest(BaseModel):
    certificate_number: str | None = None
    issue_date: date | None = None
    checked_date: date | None = None
    application_status: DBSApplicationStatus | None = None
    update_service_linked: bool | None = None
    last_update_check_date: date | None = None
    last_update_result: DBSUpdateResult | None = None
    external_portal_reference: str | None = None


class RecordRTWCheckRequest(BaseModel):
    checked_date: date
    evidence_type: str = Field(..., min_length=2, max_length=100)


class AdvanceReferenceStatusRequest(BaseModel):
    status: ReferenceStatus


class RecordCheckRequest(BaseModel):
    checked_date: date


# ── Worker self-view ──────────────────────────────────────────────────────────

class SCRStatusSummary(BaseModel):
    """Lightweight SCR status shown to the worker themselves."""
    scr_status: SCRStatus
    physical_id_confirmed: bool
    dbs_application_status: DBSApplicationStatus
    rtw_checked_date: date | None
    reference_1_status: ReferenceStatus
    reference_2_status: ReferenceStatus

    model_config = {"from_attributes": True}

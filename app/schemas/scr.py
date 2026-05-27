"""Pydantic schemas for the SCR (Single Central Record) domain."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import (
    ComplianceStage,
    DBSApplicationStatus,
    DBSUpdateResult,
    IDVerificationMethod,
    OnboardingStatus,
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
    barred_list_not_applicable: bool
    tra_prohibition_checked_date: date | None
    tra_not_applicable: bool
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
    location: str | None = Field(None, max_length=200)


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
    checked_date: date | None = None
    not_applicable: bool = False


# ── SCR register (full cross-worker view) ────────────────────────────────────

class WorkerSCRRegisterRow(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    # Worker identity
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    onboarding_status: str
    compliance_stage: str
    first_shift_cleared: bool
    is_amber: bool
    compliance_expires_at: datetime | None

    # SCR fields — null when no SCR record exists yet
    scr_status: SCRStatus | None = None
    physical_id_confirmed: bool = False
    physical_id_confirmed_date: date | None = None
    physical_id_confirmed_location: str | None = None
    id_verification_method: IDVerificationMethod | None = None
    rtw_checked_date: date | None = None
    rtw_evidence_type: str | None = None
    dbs_application_status: DBSApplicationStatus | None = None
    dbs_certificate_number: str | None = None
    dbs_issue_date: date | None = None
    dbs_checked_date: date | None = None
    dbs_update_service_linked: bool = False
    barred_list_checked_date: date | None = None
    tra_prohibition_checked_date: date | None = None
    qualifications_checked_date: date | None = None
    reference_1_status: ReferenceStatus | None = None
    reference_1_verified_date: date | None = None
    reference_2_status: ReferenceStatus | None = None
    reference_2_verified_date: date | None = None
    overseas_checks_required: bool = False


class SCRRegisterResponse(BaseModel):
    items: list[WorkerSCRRegisterRow]
    total: int
    limit: int
    offset: int


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

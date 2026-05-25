"""Schemas for worker self-service endpoints (/api/v1/workers/me)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.shared.enums import SCRStatus


class WorkerSelfUpdateRequest(BaseModel):
    """Fields a worker is permitted to update on their own profile."""
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    preferred_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=30)
    date_of_birth: date | None = None
    ni_number: str | None = Field(None, max_length=20)
    home_address: str | None = None
    home_city: str | None = Field(None, max_length=100)
    home_county: str | None = Field(None, max_length=100)
    home_postcode: str | None = Field(None, max_length=10)
    teacher_reference_number: str | None = Field(None, max_length=20)
    emergency_contact_name: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, max_length=30)
    gender: str | None = Field(None, max_length=50)
    ethnicity: str | None = Field(None, max_length=100)
    disability_declared: bool | None = None
    overseas_checks_required: bool | None = None
    overseas_checks_details: str | None = None
    rtw_doc_type: str | None = Field(None, max_length=50)
    rtw_doc_number: str | None = Field(None, max_length=50)
    rtw_passport_number: str | None = Field(None, max_length=50)
    rtw_passport_issue_date: date | None = None
    rtw_passport_expiry_date: date | None = None
    rtw_document_storage_path: str | None = None


class WorkerMeResponse(BaseModel):
    """Worker's own profile view — includes SCR status summary."""
    user_id: UUID
    worker_id: UUID
    first_name: str
    last_name: str
    email: str
    preferred_name: str | None
    phone: str | None
    date_of_birth: date | None
    ni_number: str | None
    home_address: str | None
    home_city: str | None
    home_county: str | None
    home_postcode: str | None
    teacher_reference_number: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    gender: str | None
    ethnicity: str | None
    disability_declared: bool | None
    overseas_checks_required: bool
    overseas_checks_details: str | None
    rtw_doc_type: str | None
    rtw_doc_number: str | None
    rtw_passport_number: str | None
    rtw_passport_issue_date: date | None
    rtw_passport_expiry_date: date | None
    onboarding_status: str
    scr_status: SCRStatus | None
    agreement_signed: bool
    safeguarding_complete: bool


class WorkerSchoolPreferenceItem(BaseModel):
    rank: int = Field(..., ge=1, le=5)
    school_id: UUID


class WorkerSchoolPreferencesUpsert(BaseModel):
    preferences: list[WorkerSchoolPreferenceItem] = Field(..., max_length=5)


class WorkerSchoolPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    school_id: UUID
    school_name: str
    school_city: str | None
    school_postcode: str | None


class SignAgreementRequest(BaseModel):
    agreement_version: str


class WorkerReferenceRequest(BaseModel):
    reference_number: int = Field(..., ge=1, le=2)
    referee_name: str = Field(..., min_length=2, max_length=150)
    referee_job_title: str | None = Field(None, max_length=150)
    referee_organisation: str = Field(..., min_length=2, max_length=200)
    referee_email: str = Field(..., max_length=255)
    referee_phone: str | None = Field(None, max_length=30)
    relationship_to_worker: str = Field(..., min_length=2, max_length=100)
    is_current_or_most_recent_employer: bool
    worker_consent_given: bool = Field(..., description="Worker must tick consent to allow contact")


class WorkerReferenceResponse(BaseModel):
    id: UUID
    reference_number: int
    referee_name: str
    referee_job_title: str | None
    referee_organisation: str
    referee_email: str
    referee_phone: str | None
    relationship_to_worker: str
    is_current_or_most_recent_employer: bool
    worker_consent_given: bool
    worker_consent_given_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TrustSettingsResponse(BaseModel):
    dbs_portal_url: str | None
    dbs_portal_pin: str | None
    dbs_portal_name: str | None
    safeguarding_policy_url: str | None
    safeguarding_policy_storage_path: str | None
    code_of_conduct_url: str | None
    code_of_conduct_storage_path: str | None
    child_protection_policy_url: str | None
    child_protection_policy_storage_path: str | None
    dsl_name: str | None
    dsl_email: str | None
    dsl_phone: str | None
    casual_worker_agreement_version: str
    casual_worker_agreement_html: str | None

    model_config = {"from_attributes": True}


class TrustSettingsUpdateRequest(BaseModel):
    dbs_portal_url: str | None = None
    dbs_portal_pin: str | None = None
    dbs_portal_name: str | None = None
    safeguarding_policy_url: str | None = None
    safeguarding_policy_storage_path: str | None = None
    code_of_conduct_url: str | None = None
    code_of_conduct_storage_path: str | None = None
    child_protection_policy_url: str | None = None
    child_protection_policy_storage_path: str | None = None
    dsl_name: str | None = None
    dsl_email: str | None = None
    dsl_phone: str | None = None
    casual_worker_agreement_version: str | None = None
    casual_worker_agreement_html: str | None = None


class WorkerDbsLinkUpdateServiceRequest(BaseModel):
    """Worker links an existing Enhanced DBS certificate to the Update Service."""
    dbs_certificate_number: str = Field(..., max_length=10)
    dbs_certificate_name: str = Field(..., max_length=150, description="Full name exactly as stated on the DBS certificate")
    date_of_birth: date | None = None


class WorkerDbsStartApplicationRequest(BaseModel):
    """Worker records their chosen identity verification method for a fresh DBS application."""
    id_verification_method: str = Field(..., max_length=50)

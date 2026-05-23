"""
Canonical Python enums mirroring every PostgreSQL enum in the schema.
These are the single source of truth for enum values in application code.
"""

import enum


class TrustStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    trial = "trial"
    offboarded = "offboarded"


class UserStatus(str, enum.Enum):
    invited = "invited"
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class OnboardingStatus(str, enum.Enum):
    """Human-facing onboarding lifecycle status — shown on HR dashboards."""
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"
    expired = "expired"


class ComplianceStage(str, enum.Enum):
    """Internal compliance processing stage — used for workflow orchestration."""
    not_started = "not_started"
    awaiting_documents = "awaiting_documents"
    documents_received = "documents_received"
    dbs_check_pending = "dbs_check_pending"
    rtw_check_pending = "rtw_check_pending"
    under_review = "under_review"
    clearance_granted = "clearance_granted"
    clearance_denied = "clearance_denied"
    recheck_required = "recheck_required"


class ComplianceHealth(str, enum.Enum):
    """Computed aggregate compliance health — derived at read time, never stored."""
    not_started = "not_started"
    in_progress = "in_progress"
    amber = "amber"
    compliant = "compliant"
    non_compliant = "non_compliant"
    expired = "expired"


class DocumentType(str, enum.Enum):
    dbs_certificate = "dbs_certificate"
    right_to_work = "right_to_work"
    proof_of_identity = "proof_of_identity"
    teaching_certificate = "teaching_certificate"
    reference = "reference"
    medical_clearance = "medical_clearance"
    other = "other"


class DocumentStatus(str, enum.Enum):
    pending_upload = "pending_upload"
    uploaded = "uploaded"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    superseded = "superseded"


class DBSLevel(str, enum.Enum):
    basic = "basic"
    standard = "standard"
    enhanced = "enhanced"
    enhanced_barred = "enhanced_barred"


class DBSStatus(str, enum.Enum):
    not_started = "not_started"
    applied = "applied"
    pending = "pending"
    clear = "clear"
    flagged = "flagged"
    expired = "expired"


class RTWDocumentType(str, enum.Enum):
    uk_passport = "uk_passport"
    biometric_residence_permit = "biometric_residence_permit"
    share_code = "share_code"
    eu_settlement = "eu_settlement"
    other = "other"


class BookingStatus(str, enum.Enum):
    requested = "requested"
    offered = "offered"
    accepted = "accepted"
    confirmed = "confirmed"
    checked_in = "checked_in"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"
    rejected = "rejected"
    expired = "expired"


class TimesheetStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    correction_requested = "correction_requested"
    exported = "exported"


class DispatchMode(str, enum.Enum):
    directed = "directed"
    broadcast = "broadcast"


class BookingOfferStatus(str, enum.Enum):
    offered = "offered"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    withdrawn = "withdrawn"


class UrgencyLevel(str, enum.Enum):
    standard = "standard"
    urgent = "urgent"
    emergency = "emergency"


class PayFrequency(str, enum.Enum):
    weekly = "weekly"
    fortnightly = "fortnightly"
    monthly = "monthly"


class OnboardingNoteType(str, enum.Enum):
    manual = "manual"
    status_change = "status_change"
    document_action = "document_action"
    system = "system"
    hr_review = "hr_review"


class NoteVisibility(str, enum.Enum):
    internal = "internal"
    worker_visible = "worker_visible"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    approve = "approve"
    reject = "reject"
    login = "login"
    logout = "logout"
    export = "export"
    view = "view"
    upload = "upload"


# ── SCR / Compliance enums ─────────────────────────────────────────────────────

class SCRStatus(str, enum.Enum):
    """Ofsted-facing Single Central Record compliance status per worker."""
    incomplete = "incomplete"
    pending_review = "pending_review"
    verified_pending_physical = "verified_pending_physical"
    compliant = "compliant"
    suspended = "suspended"


class ReferenceStatus(str, enum.Enum):
    pending = "pending"
    requested = "requested"
    received_unverified = "received_unverified"
    verified = "verified"


class DBSApplicationStatus(str, enum.Enum):
    not_started = "not_started"
    in_flight = "in_flight"
    completed = "completed"


class DBSUpdateResult(str, enum.Enum):
    not_checked = "not_checked"
    up_to_date = "up_to_date"
    new_information = "new_information"
    no_result_found = "no_result_found"


class IDVerificationMethod(str, enum.Enum):
    """How the worker's identity was initially verified."""
    not_selected = "not_selected"
    third_party_digital = "third_party_digital"
    school_in_person = "school_in_person"
    school_video_call = "school_video_call"


class SafeguardingGate(str, enum.Enum):
    kcsie_read = "kcsie_read"
    policy_signed = "policy_signed"
    quiz_passed = "quiz_passed"

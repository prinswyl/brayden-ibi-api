"""
ORM models for the Single Central Record (SCR) compliance domain.

Covers:
  - SCRRecord       — Ofsted-exportable compliance row, one per worker
  - WorkerAgreement — click-signed Casual Worker Agreement audit record
  - WorkerReference — referee details submitted by worker + HR verification trail
  - WorkerSafeguardingInduction — three-gate induction progress tracker
  - SafeguardingQuizQuestion    — question bank (seeded in migration)
  - SafeguardingQuizAttempt     — per-attempt record
  - TrustSettings               — DBS portal URL/PIN, policy documents, DSL details
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin, UUIDMixin
from app.shared.enums import (
    DBSApplicationStatus,
    DBSUpdateResult,
    IDVerificationMethod,
    ReferenceStatus,
    SCRStatus,
)


class SCRRecord(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "scr_records"

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worker_profiles.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    scr_status: Mapped[SCRStatus] = mapped_column(
        PGEnum(SCRStatus, name="scr_status", create_type=False),
        nullable=False, default=SCRStatus.incomplete,
    )

    # Identity verification — initial check
    id_verification_method: Mapped[IDVerificationMethod] = mapped_column(
        PGEnum(IDVerificationMethod, name="id_verification_method", create_type=False),
        nullable=False, default=IDVerificationMethod.not_selected,
    )
    initial_id_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_id_checked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    initial_id_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Physical ID — KCSIE hard gate
    physical_id_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    physical_id_confirmed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    physical_id_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    physical_id_confirmed_location: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Right to Work
    rtw_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rtw_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rtw_evidence_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    # DBS risk assessment
    dbs_risk_assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dbs_barred_list_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # DBS
    dbs_application_status: Mapped[DBSApplicationStatus] = mapped_column(
        PGEnum(DBSApplicationStatus, name="dbs_application_status", create_type=False),
        nullable=False, default=DBSApplicationStatus.not_started,
    )
    dbs_certificate_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    dbs_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dbs_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dbs_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    dbs_update_service_linked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dbs_last_update_check_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dbs_last_update_result: Mapped[DBSUpdateResult] = mapped_column(
        PGEnum(DBSUpdateResult, name="dbs_update_result", create_type=False),
        nullable=False, default=DBSUpdateResult.not_checked,
    )
    external_dbs_portal_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Barred list
    barred_list_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    barred_list_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    barred_list_not_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # TRA prohibition
    tra_prohibition_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tra_prohibition_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tra_not_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Qualifications
    qualifications_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualifications_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # References
    reference_1_status: Mapped[ReferenceStatus] = mapped_column(
        PGEnum(ReferenceStatus, name="reference_status", create_type=False),
        nullable=False, default=ReferenceStatus.pending,
    )
    reference_1_verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_1_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reference_2_status: Mapped[ReferenceStatus] = mapped_column(
        PGEnum(ReferenceStatus, name="reference_status", create_type=False),
        nullable=False, default=ReferenceStatus.pending,
    )
    reference_2_verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_2_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Section 128 (management prohibition check — leadership roles only)
    section_128_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    section_128_checked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    section_128_not_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Overseas checks
    overseas_checks_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overseas_checks_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    overseas_check_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    overseas_checks_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    overseas_checks_verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class WorkerAgreement(UUIDMixin, TenantMixin, Base):
    __tablename__ = "worker_agreements"

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worker_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agreement_version: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(nullable=False)
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class WorkerReference(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "worker_references"

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worker_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    reference_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2

    # Referee details (submitted by worker)
    referee_name: Mapped[str] = mapped_column(Text, nullable=False)
    referee_job_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    referee_organisation: Mapped[str] = mapped_column(Text, nullable=False)
    referee_email: Mapped[str] = mapped_column(Text, nullable=False)
    referee_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship_to_worker: Mapped[str] = mapped_column(Text, nullable=False)
    is_current_or_most_recent_employer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    worker_consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    worker_consent_given_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # HR audit trail
    status: Mapped[ReferenceStatus] = mapped_column(
        PGEnum(ReferenceStatus, name="reference_status", create_type=False),
        nullable=False, default=ReferenceStatus.pending,
    )
    requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(nullable=True)
    received_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reference_document_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkerSafeguardingInduction(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "worker_safeguarding_inductions"

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worker_profiles.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # Gate 1 — KCSIE reading
    kcsie_read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    kcsie_scroll_depth_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kcsie_time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Gate 2 — Local policy sign
    policy_signed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    policy_version_signed: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gate 3 — Quiz
    quiz_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiz_passed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    quiz_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quiz_last_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class SafeguardingQuizQuestion(UUIDMixin, Base):
    __tablename__ = "safeguarding_quiz_questions"

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(Text, nullable=False)
    option_b: Mapped[str] = mapped_column(Text, nullable=False)
    option_c: Mapped[str] = mapped_column(Text, nullable=False)
    option_d: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[str] = mapped_column(Text, nullable=False)  # 'a', 'b', 'c', or 'd'
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class SafeguardingQuizAttempt(UUIDMixin, Base):
    __tablename__ = "safeguarding_quiz_attempts"

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("worker_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {question_id: chosen_option}
    attempted_at: Mapped[datetime] = mapped_column(nullable=False)


class TrustSettings(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "trust_settings"

    trust_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trusts.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    dbs_portal_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    dbs_portal_pin: Mapped[str | None] = mapped_column(Text, nullable=True)
    dbs_portal_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    safeguarding_policy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    safeguarding_policy_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_of_conduct_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_of_conduct_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    child_protection_policy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    child_protection_policy_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    dsl_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    dsl_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    dsl_phone: Mapped[str | None] = mapped_column(Text, nullable=True)

    casual_worker_agreement_version: Mapped[str] = mapped_column(Text, nullable=False, default="1.0")
    casual_worker_agreement_html: Mapped[str | None] = mapped_column(Text, nullable=True)

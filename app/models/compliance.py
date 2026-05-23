import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, TenantMixin, UUIDMixin
from app.shared.enums import (
    ComplianceStage,
    DBSLevel,
    DBSStatus,
    DocumentStatus,
    DocumentType,
    NoteVisibility,
    OnboardingNoteType,
    OnboardingStatus,
    RTWDocumentType,
)


class ComplianceDocument(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "compliance_documents"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(PGEnum(DocumentType, name="document_type", create_type=False), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DocumentStatus] = mapped_column(PGEnum(DocumentStatus, name="document_status", create_type=False), nullable=False, default=DocumentStatus.pending_upload)

    # Storage
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_bucket: Mapped[str] = mapped_column(Text, nullable=False, default="compliance-docs")
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(Text)

    # Versioning
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compliance_documents.id"), nullable=True
    )

    # Expiry
    expiry_date: Mapped[date | None] = mapped_column(Date)
    expiry_reminder_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Review
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text)

    # Upload tracking
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    worker: Mapped["WorkerProfile"] = relationship(  # noqa: F821
        "WorkerProfile", back_populates="compliance_documents", lazy="noload"
    )
    superseded_document: Mapped["ComplianceDocument | None"] = relationship(
        "ComplianceDocument", remote_side="ComplianceDocument.id", foreign_keys=[supersedes_id], lazy="noload"
    )


class DBSCheck(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "dbs_checks"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    dbs_level: Mapped[DBSLevel] = mapped_column(PGEnum(DBSLevel, name="dbs_level", create_type=False), nullable=False)
    certificate_number: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[DBSStatus] = mapped_column(PGEnum(DBSStatus, name="dbs_status", create_type=False), nullable=False, default=DBSStatus.not_started)
    on_update_service: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(Text)

    # Extended tracking fields (added migration 0006)
    application_status: Mapped[str] = mapped_column(
        PGEnum("not_started", "in_flight", "completed", name="dbs_application_status", create_type=False),
        nullable=False, default="not_started",
    )
    external_portal_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_update_check_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_update_result: Mapped[str] = mapped_column(
        PGEnum("not_checked", "up_to_date", "new_information", "no_result_found", name="dbs_update_result", create_type=False),
        nullable=False, default="not_checked",
    )

    worker: Mapped["WorkerProfile"] = relationship(  # noqa: F821
        "WorkerProfile", back_populates="dbs_checks", lazy="noload"
    )


class RTWCheck(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "right_to_work_checks"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    document_type: Mapped[RTWDocumentType] = mapped_column(PGEnum(RTWDocumentType, name="rtw_document_type", create_type=False), nullable=False)
    document_reference: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[DocumentStatus] = mapped_column(PGEnum(DocumentStatus, name="document_status", create_type=False), nullable=False, default=DocumentStatus.pending_upload)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    storage_path: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    worker: Mapped["WorkerProfile"] = relationship(  # noqa: F821
        "WorkerProfile", back_populates="rtw_checks", lazy="noload"
    )


class ComplianceStageHistory(UUIDMixin, TenantMixin, Base):
    __tablename__ = "compliance_stage_history"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    stage: Mapped[ComplianceStage] = mapped_column(PGEnum(ComplianceStage, name="compliance_stage", create_type=False), nullable=False)
    stage_entered_at: Mapped[datetime] = mapped_column(nullable=False)
    stage_completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class OnboardingNote(UUIDMixin, TenantMixin, Base):
    __tablename__ = "onboarding_notes"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    note_type: Mapped[OnboardingNoteType] = mapped_column(Text, nullable=False, default=OnboardingNoteType.manual)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[NoteVisibility] = mapped_column(Text, nullable=False, default=NoteVisibility.internal)
    previous_status: Mapped[OnboardingStatus | None] = mapped_column(
        PGEnum(OnboardingStatus, name="onboarding_status", create_type=False), nullable=True
    )
    new_status: Mapped[OnboardingStatus | None] = mapped_column(
        PGEnum(OnboardingStatus, name="onboarding_status", create_type=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    worker: Mapped["WorkerProfile"] = relationship(  # noqa: F821
        "WorkerProfile", back_populates="onboarding_notes", lazy="noload"
    )

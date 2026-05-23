import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, TenantMixin, UUIDMixin
from app.shared.enums import ComplianceStage, OnboardingStatus


class WorkerProfile(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "worker_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # PII — stored encrypted at application layer; only last4/partial stored here
    ni_number: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    preferred_name: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)
    ethnicity: Mapped[str | None] = mapped_column(Text)
    disability_declared: Mapped[bool | None] = mapped_column(Boolean)
    emergency_contact_name: Mapped[str | None] = mapped_column(Text)
    emergency_contact_phone: Mapped[str | None] = mapped_column(Text)
    bank_account_last4: Mapped[str | None] = mapped_column(Text)
    bank_sort_code: Mapped[str | None] = mapped_column(Text)

    # Onboarding lifecycle (human-facing)
    onboarding_status: Mapped[OnboardingStatus] = mapped_column(
        PGEnum(OnboardingStatus, name="onboarding_status", create_type=False),
        nullable=False, default=OnboardingStatus.draft,
    )
    # Internal processing stage
    compliance_stage: Mapped[ComplianceStage] = mapped_column(
        PGEnum(ComplianceStage, name="compliance_stage", create_type=False),
        nullable=False, default=ComplianceStage.not_started,
    )

    # Amber flag — explicitly set by HR, not derived
    is_amber: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Suspension tracking (columns, not just enum position)
    suspended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    suspension_reason: Mapped[str | None] = mapped_column(Text)
    suspended_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Earliest expiry across all required compliance documents
    compliance_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Physical first-shift DBS verification (trust-level flag)
    first_shift_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notes: Mapped[str | None] = mapped_column(Text)

    # Teacher Reference Number (for QTS / teaching staff)
    teacher_reference_number: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Overseas checks declaration
    overseas_checks_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overseas_checks_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Home location and travel radius
    home_postcode: Mapped[str | None] = mapped_column(Text)
    home_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    home_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    radius_km: Mapped[int] = mapped_column(Integer, nullable=False, default=25)

    # Relationships
    compliance_documents: Mapped[list["ComplianceDocument"]] = relationship(  # noqa: F821
        "ComplianceDocument", back_populates="worker", lazy="noload"
    )
    dbs_checks: Mapped[list["DBSCheck"]] = relationship(  # noqa: F821
        "DBSCheck", back_populates="worker", lazy="noload"
    )
    rtw_checks: Mapped[list["RTWCheck"]] = relationship(  # noqa: F821
        "RTWCheck", back_populates="worker", lazy="noload"
    )
    onboarding_notes: Mapped[list["OnboardingNote"]] = relationship(  # noqa: F821
        "OnboardingNote", back_populates="worker", lazy="noload"
    )
    first_shift_verifications: Mapped[list["FirstShiftVerification"]] = relationship(  # noqa: F821
        "FirstShiftVerification", back_populates="worker", lazy="noload"
    )


class WorkerRoleType(UUIDMixin, TenantMixin, Base):
    __tablename__ = "worker_role_types"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class WorkerRoleAssignment(UUIDMixin, TenantMixin, Base):
    __tablename__ = "worker_role_assignments"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    role_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_role_types.id"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, Text, Time
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin, UUIDMixin
from app.shared.enums import TimesheetStatus


class Timesheet(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "timesheets"

    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)

    actual_start_time: Mapped[time | None] = mapped_column(Time)
    actual_end_time: Mapped[time | None] = mapped_column(Time)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    gross_pay: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    status: Mapped[TimesheetStatus] = mapped_column(
        PGEnum(TimesheetStatus, name="timesheet_status", create_type=False),
        nullable=False,
        default=TimesheetStatus.draft,
    )

    worker_notes: Mapped[str | None] = mapped_column(Text)

    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    correction_requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    correction_requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Locked once approved — prevents further edits
    locked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    signed_by_worker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    signed_at_school: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    exported_at: Mapped[datetime | None] = mapped_column(nullable=True)
    export_reference: Mapped[str | None] = mapped_column(Text)

    corrections: Mapped[list["TimesheetCorrection"]] = relationship(
        "TimesheetCorrection", back_populates="timesheet", lazy="noload"
    )


class TimesheetCorrection(UUIDMixin, TenantMixin, Base):
    """Immutable record of each correction request against a timesheet."""
    __tablename__ = "timesheet_corrections"

    timesheet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("timesheets.id"), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    timesheet: Mapped["Timesheet"] = relationship("Timesheet", back_populates="corrections", lazy="noload")

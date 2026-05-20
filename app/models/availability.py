import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantMixin, UUIDMixin


class WorkerAvailability(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """Per-date availability — specific overrides and booking conflict detection."""
    __tablename__ = "availability"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    available_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    am_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pm_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text)


class WorkerAvailabilityPreferences(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """Recurring availability preferences — standing rules set by the worker."""
    __tablename__ = "worker_availability_preferences"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)

    # Bitmask: Mon=1 Tue=2 Wed=4 Thu=8 Fri=16 Sat=32 Sun=64  (default Mon–Fri = 31)
    available_days_mask: Mapped[int] = mapped_column(Integer, nullable=False, default=31)
    max_days_per_week: Mapped[int | None] = mapped_column(Integer)
    max_hours_per_week: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Arrays stored as PostgreSQL UUID[] columns
    preferred_school_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    preferred_role_type_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)

    radius_km: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    willing_to_travel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

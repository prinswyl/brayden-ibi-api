import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, UUIDMixin


class FirstShiftVerification(UUIDMixin, TenantMixin, Base):
    __tablename__ = "first_shift_verifications"

    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    verified_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    verification_date: Mapped[date] = mapped_column(Date, nullable=False)
    dbs_seen_and_matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    worker: Mapped["WorkerProfile"] = relationship(  # noqa: F821
        "WorkerProfile", back_populates="first_shift_verifications", lazy="noload"
    )

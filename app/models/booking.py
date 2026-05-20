import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, Text, Time
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, TenantMixin, UUIDMixin
from app.shared.enums import (
    BookingOfferStatus,
    BookingStatus,
    DispatchMode,
    UrgencyLevel,
)


class Booking(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "bookings"

    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=True)
    role_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_role_types.id"), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    dispatch_mode: Mapped[DispatchMode] = mapped_column(
        PGEnum(DispatchMode, name="dispatch_mode", create_type=False), nullable=False, default=DispatchMode.broadcast
    )
    urgency: Mapped[UrgencyLevel] = mapped_column(
        PGEnum(UrgencyLevel, name="urgency_level", create_type=False), nullable=False, default=UrgencyLevel.standard
    )
    status: Mapped[BookingStatus] = mapped_column(
        PGEnum(BookingStatus, name="booking_status", create_type=False), nullable=False, default=BookingStatus.requested
    )

    agreed_hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    offer_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    # Lifecycle timestamps
    offered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(nullable=True)
    checked_in_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    school_confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    school_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    # No-show
    no_show_reason: Mapped[str | None] = mapped_column(Text)

    # Rejection
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    # Expiry
    expired_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    offers: Mapped[list["BookingOffer"]] = relationship("BookingOffer", back_populates="booking", lazy="noload")
    status_history: Mapped[list["BookingStatusHistory"]] = relationship(
        "BookingStatusHistory", back_populates="booking", lazy="noload"
    )


class BookingOffer(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "booking_offers"

    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    status: Mapped[BookingOfferStatus] = mapped_column(
        PGEnum(BookingOfferStatus, name="booking_offer_status", create_type=False),
        nullable=False,
        default=BookingOfferStatus.offered,
    )
    offered_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="offers", lazy="noload")


class BookingStatusHistory(UUIDMixin, TenantMixin, Base):
    """Immutable state transition log — one row per status change."""
    __tablename__ = "booking_status_history"

    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False)
    from_status: Mapped[BookingStatus | None] = mapped_column(
        PGEnum(BookingStatus, name="booking_status", create_type=False), nullable=True
    )
    to_status: Mapped[BookingStatus] = mapped_column(
        PGEnum(BookingStatus, name="booking_status", create_type=False), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="status_history", lazy="noload")

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, TenantMixin, UUIDMixin


class School(UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin, Base):
    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    urn: Mapped[str | None] = mapped_column(Text)
    phase: Mapped[str | None] = mapped_column(Text)
    address_line_1: Mapped[str | None] = mapped_column(Text)
    address_line_2: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    postcode: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

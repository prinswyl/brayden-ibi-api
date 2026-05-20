from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.shared.enums import TrustStatus


class Trust(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "trusts"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    urn: Mapped[str | None] = mapped_column(Text, unique=True)
    companies_house_no: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TrustStatus] = mapped_column(PGEnum(TrustStatus, name="trust_status", create_type=False), nullable=False, default=TrustStatus.trial)
    trial_ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    subscription_tier: Mapped[str] = mapped_column(Text, nullable=False, default="starter")
    contact_email: Mapped[str] = mapped_column(Text, nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    address_line_1: Mapped[str | None] = mapped_column(Text)
    address_line_2: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    postcode: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, nullable=False, default="GB")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

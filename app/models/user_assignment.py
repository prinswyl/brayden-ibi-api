import uuid

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantMixin, UUIDMixin


class UserSchoolAssignment(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """
    Links a user to a role, optionally scoped to a specific school.

    Trust-wide roles (trust_admin, payroll_officer, hr_manager) have school_id = NULL.
    School-scoped roles (cover_supervisor, receptionist) require a school_id.
    """
    __tablename__ = "user_school_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "school_id", "role", name="uq_user_school_role"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

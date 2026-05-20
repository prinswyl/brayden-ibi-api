"""
Shared Pydantic schema base classes and response envelope types.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """
    Base for all API schemas.
    - Forbids extra fields (prevents mass-assignment vulnerabilities).
    - Uses enum values (not enum members) in JSON output.
    - Validates on assignment for correctness.
    """
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
    )


class ORMModel(BaseModel):
    """Base for schemas that are populated from ORM objects."""
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )


class TimestampedModel(ORMModel):
    """Adds created_at / updated_at to ORM-backed response schemas."""
    created_at: datetime
    updated_at: datetime


class TenantedModel(TimestampedModel):
    """Adds trust_id to tenant-scoped response schemas."""
    id: UUID
    trust_id: UUID


class MessageResponse(BaseModel):
    """Simple acknowledgement response."""
    message: str


class ErrorResponse(BaseModel):
    """Structured error response body (mirrors global exception handler)."""
    error: str
    message: str
    details: object = None

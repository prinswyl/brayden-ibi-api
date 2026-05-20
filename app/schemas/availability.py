from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AvailabilitySet(BaseModel):
    available_date: date
    is_available: bool
    am_available: bool = True
    pm_available: bool = True
    note: str | None = None


class AvailabilityBulkSet(BaseModel):
    dates: list[date] = Field(min_length=1, max_length=90)
    is_available: bool


class AvailabilityResponse(BaseModel):
    id: UUID
    worker_id: UUID
    available_date: date
    is_available: bool
    am_available: bool
    pm_available: bool
    note: str | None

    model_config = {"from_attributes": True}


class AvailabilityPreferencesUpdate(BaseModel):
    available_days_mask: int | None = Field(None, ge=0, le=127)
    max_days_per_week: int | None = Field(None, ge=1, le=7)
    max_hours_per_week: Decimal | None = Field(None, gt=0)
    preferred_school_ids: list[UUID] | None = None
    preferred_role_type_ids: list[UUID] | None = None
    radius_km: int | None = Field(None, ge=1, le=200)
    willing_to_travel: bool | None = None
    notes: str | None = None


class AvailabilityPreferencesResponse(BaseModel):
    id: UUID
    worker_id: UUID
    available_days_mask: int
    max_days_per_week: int | None
    max_hours_per_week: Decimal | None
    preferred_school_ids: list[UUID]
    preferred_role_type_ids: list[UUID]
    radius_km: int
    willing_to_travel: bool
    notes: str | None

    model_config = {"from_attributes": True}

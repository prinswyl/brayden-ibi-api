from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.enums import TimesheetStatus


class TimesheetSubmit(BaseModel):
    actual_start_time: time
    actual_end_time: time
    break_minutes: int = Field(default=0, ge=0, le=120)
    overtime_hours: Decimal = Field(default=Decimal("0"), ge=0)
    worker_notes: str | None = None


class TimesheetReject(BaseModel):
    reason: str = Field(min_length=1)


class TimesheetCorrectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class TimesheetResponse(BaseModel):
    id: UUID
    trust_id: UUID
    booking_id: UUID
    worker_id: UUID
    school_id: UUID
    shift_date: date
    actual_start_time: time | None
    actual_end_time: time | None
    break_minutes: int
    total_hours: Decimal | None
    overtime_hours: Decimal
    hourly_rate: Decimal | None
    gross_pay: Decimal | None
    status: TimesheetStatus
    worker_notes: str | None
    submitted_at: datetime | None
    approved_by: UUID | None
    approved_at: datetime | None
    rejected_by: UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    correction_requested_at: datetime | None
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimesheetCorrectionResponse(BaseModel):
    id: UUID
    timesheet_id: UUID
    requested_by: UUID
    reason: str
    old_values: dict | None
    resolved_at: datetime | None
    resolved_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TimesheetListResponse(BaseModel):
    items: list[TimesheetResponse]
    total: int
    offset: int
    limit: int

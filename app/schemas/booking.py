from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.shared.enums import BookingOfferStatus, BookingStatus, DispatchMode, UrgencyLevel


class BookingCreate(BaseModel):
    school_id: UUID
    role_type_id: UUID
    shift_date: date
    start_time: time
    end_time: time
    agreed_hourly_rate: Decimal = Field(gt=0)
    dispatch_mode: DispatchMode = DispatchMode.broadcast
    urgency: UrgencyLevel = UrgencyLevel.standard
    directed_worker_id: UUID | None = None
    reason: str | None = None
    notes: str | None = None
    offer_expires_at: datetime | None = None

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: time, info) -> time:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class BookingResponse(BaseModel):
    id: UUID
    trust_id: UUID
    school_id: UUID
    worker_id: UUID | None
    role_type_id: UUID
    requested_by: UUID
    shift_date: date
    start_time: time
    end_time: time
    dispatch_mode: DispatchMode
    urgency: UrgencyLevel
    status: BookingStatus
    agreed_hourly_rate: Decimal | None
    offer_expires_at: datetime | None
    reason: str | None
    notes: str | None
    offered_at: datetime | None
    accepted_at: datetime | None
    confirmed_at: datetime | None
    checked_in_at: datetime | None
    check_out_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    no_show_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingOfferResponse(BaseModel):
    id: UUID
    booking_id: UUID
    worker_id: UUID
    status: BookingOfferStatus
    offered_at: datetime
    expires_at: datetime | None
    responded_at: datetime | None
    decline_reason: str | None

    model_config = {"from_attributes": True}


class BookingStatusHistoryResponse(BaseModel):
    id: UUID
    booking_id: UUID
    from_status: BookingStatus | None
    to_status: BookingStatus
    actor_id: UUID | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AcceptOfferRequest(BaseModel):
    worker_id: UUID


class DeclineOfferRequest(BaseModel):
    worker_id: UUID
    reason: str | None = None


class CancelBookingRequest(BaseModel):
    reason: str | None = None


class DispatchOffersRequest(BaseModel):
    school_lat: Decimal | None = None
    school_lon: Decimal | None = None


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    total: int
    offset: int
    limit: int

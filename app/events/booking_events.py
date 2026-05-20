"""
Booking & Timesheet domain events.

V1: structured log only. Each event is a frozen dataclass dispatched after
state changes in service layer. The dispatch() function is the hook point
for future notification delivery (email, push, webhooks).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import structlog

from app.shared.enums import BookingStatus, TimesheetStatus

logger = structlog.get_logger(__name__)

BookingEvent = object  # type alias for documentation


@dataclass(frozen=True)
class BookingCreatedEvent:
    booking_id: UUID
    trust_id: UUID
    school_id: UUID
    role_type_id: UUID
    shift_date: str
    dispatch_mode: str
    requested_by: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class BookingOfferedEvent:
    booking_id: UUID
    trust_id: UUID
    worker_ids: list[UUID]
    shift_date: str
    offer_expires_at: datetime | None
    occurred_at: datetime


@dataclass(frozen=True)
class BookingAcceptedEvent:
    booking_id: UUID
    trust_id: UUID
    worker_id: UUID
    shift_date: str
    occurred_at: datetime


@dataclass(frozen=True)
class BookingConfirmedEvent:
    booking_id: UUID
    trust_id: UUID
    worker_id: UUID
    school_id: UUID
    confirmed_by: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class BookingCheckedInEvent:
    booking_id: UUID
    trust_id: UUID
    worker_id: UUID
    school_id: UUID
    checked_in_by: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class BookingCompletedEvent:
    booking_id: UUID
    trust_id: UUID
    worker_id: UUID
    school_id: UUID
    shift_date: str
    occurred_at: datetime


@dataclass(frozen=True)
class BookingCancelledEvent:
    booking_id: UUID
    trust_id: UUID
    cancelled_by: UUID
    reason: str | None
    from_status: str
    occurred_at: datetime


@dataclass(frozen=True)
class BookingNoShowEvent:
    booking_id: UUID
    trust_id: UUID
    worker_id: UUID
    school_id: UUID
    shift_date: str
    recorded_by: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class BookingExpiredEvent:
    booking_id: UUID
    trust_id: UUID
    shift_date: str
    occurred_at: datetime


@dataclass(frozen=True)
class BookingOfferDeclinedEvent:
    booking_id: UUID
    trust_id: UUID
    worker_id: UUID
    decline_reason: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class TimesheetSubmittedEvent:
    timesheet_id: UUID
    trust_id: UUID
    booking_id: UUID
    worker_id: UUID
    school_id: UUID
    shift_date: str
    total_hours: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class TimesheetApprovedEvent:
    timesheet_id: UUID
    trust_id: UUID
    worker_id: UUID
    school_id: UUID
    approved_by: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TimesheetRejectedEvent:
    timesheet_id: UUID
    trust_id: UUID
    worker_id: UUID
    rejected_by: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class TimesheetCorrectionRequestedEvent:
    timesheet_id: UUID
    trust_id: UUID
    worker_id: UUID
    requested_by: UUID
    reason: str
    occurred_at: datetime


async def dispatch(event: object) -> None:
    """
    Dispatch a booking or timesheet domain event.

    V1: structured log only.
    V2 hook: route to notification service, webhooks, push delivery.
    """
    event_data = {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                  for k, v in vars(event).items()}
    logger.info(
        "booking_event",
        event_type=type(event).__name__,
        **event_data,
    )

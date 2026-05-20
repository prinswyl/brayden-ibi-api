"""
Compliance event architecture.

Events are emitted by service layer methods after state changes. No delivery
mechanism is wired in V1 — dispatch() logs the event and is the hook point
for future notification delivery (email, push, webhooks, queues).

Usage:
    from app.events.compliance_events import OnboardingApprovedEvent, dispatch

    await dispatch(OnboardingApprovedEvent(
        trust_id=worker.trust_id,
        worker_id=worker.id,
        approved_by=current_user.user_id,
    ))
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ComplianceEvent:
    """Base class for all compliance domain events."""
    event_type: ClassVar[str]

    trust_id: uuid.UUID
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class OnboardingSubmittedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "onboarding.submitted"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    submitted_by: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=True)
class OnboardingApprovedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "onboarding.approved"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    approved_by: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=True)
class OnboardingRejectedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "onboarding.rejected"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    rejected_by: uuid.UUID = field(default_factory=uuid.uuid4)
    reason: str = ""


@dataclass(frozen=True)
class WorkerSuspendedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "worker.suspended"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    suspended_by: uuid.UUID = field(default_factory=uuid.uuid4)
    reason: str = ""


@dataclass(frozen=True)
class DocumentRejectedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "document.rejected"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_type: str = ""
    rejected_by: uuid.UUID = field(default_factory=uuid.uuid4)
    reason: str = ""


@dataclass(frozen=True)
class DocumentApprovedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "document.approved"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_type: str = ""
    approved_by: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=True)
class DocumentReuploadRequestedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "document.reupload_requested"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_type: str = ""
    requested_by: uuid.UUID = field(default_factory=uuid.uuid4)
    reason: str = ""


@dataclass(frozen=True)
class ComplianceExpiringEvent(ComplianceEvent):
    event_type: ClassVar[str] = "compliance.expiring"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    document_type: str = ""
    days_until_expiry: int = 0


@dataclass(frozen=True)
class FirstShiftVerifiedEvent(ComplianceEvent):
    event_type: ClassVar[str] = "first_shift.verified"
    worker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    school_id: uuid.UUID = field(default_factory=uuid.uuid4)
    verified_by: uuid.UUID = field(default_factory=uuid.uuid4)


async def dispatch(event: ComplianceEvent) -> None:
    """
    Dispatch a compliance event.

    V1: structured log only. Hook point for future delivery:
      - Email notifications
      - In-app notification records
      - Webhook delivery
      - Message queue publish (SQS/PubSub)
    """
    logger.info(
        "compliance_event",
        event_type=event.event_type,
        trust_id=str(event.trust_id),
        occurred_at=event.occurred_at.isoformat(),
        **{
            k: (str(v) if isinstance(v, uuid.UUID) else v)
            for k, v in vars(event).items()
            if k not in ("trust_id", "occurred_at")
        },
    )

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import APIModel, ORMModel


class VerifyFirstShiftRequest(APIModel):
    worker_id: UUID
    school_id: UUID
    dbs_seen_and_matched: bool
    verification_date: date | None = None
    notes: str | None = None


class FirstShiftVerificationResponse(ORMModel):
    id: UUID
    trust_id: UUID
    worker_id: UUID
    school_id: UUID
    verified_by_id: UUID
    verification_date: date
    dbs_seen_and_matched: bool
    notes: str | None
    created_at: datetime


class FirstShiftVerificationListResponse(ORMModel):
    items: list[FirstShiftVerificationResponse]
    total: int


class FirstShiftStatusResponse(ORMModel):
    worker_id: UUID
    school_id: UUID
    is_verified: bool
    verification: FirstShiftVerificationResponse | None

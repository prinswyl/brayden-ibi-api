from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.schemas.base import ORMModel
from app.schemas.compliance_document import DocumentResponse
from app.schemas.worker import WorkerProfileResponse


class DashboardSummaryResponse(ORMModel):
    pending_review_count: int
    amber_count: int
    expiring_within_30_days: int
    expiring_within_7_days: int
    onboarding_by_status: dict[str, int]
    recent_rejections: int


class ExpiringDocumentsResponse(ORMModel):
    items: list[DocumentResponse]
    total: int
    cutoff_date: date


class PendingReviewResponse(ORMModel):
    items: list[WorkerProfileResponse]
    total: int
    offset: int
    limit: int

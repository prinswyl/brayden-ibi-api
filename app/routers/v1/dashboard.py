"""
Compliance dashboard endpoints.

  GET /api/v1/compliance/dashboard                  — summary counts
  GET /api/v1/compliance/dashboard/pending-review   — workers pending HR review
  GET /api/v1/compliance/dashboard/under-review     — workers currently being reviewed
  GET /api/v1/compliance/dashboard/expiring-documents — documents expiring soon
  GET /api/v1/compliance/dashboard/review-queue     — documents awaiting HR review
"""

from datetime import datetime, UTC, timedelta

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.compliance_document import DocumentListResponse, DocumentResponse
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    ExpiringDocumentsResponse,
    PendingReviewResponse,
)
from app.schemas.worker import WorkerProfileResponse
from app.services.compliance_dashboard import ComplianceDashboardService
from app.services.hr_review import HRReviewService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/compliance/dashboard", tags=["Compliance Dashboard"])


@router.get(
    "",
    response_model=DashboardSummaryResponse,
    summary="Compliance dashboard summary counts",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    svc = ComplianceDashboardService(db)
    summary = await svc.get_dashboard_summary()
    return DashboardSummaryResponse(
        pending_review_count=summary.pending_review_count,
        amber_count=summary.amber_count,
        expiring_within_30_days=summary.expiring_within_30_days,
        expiring_within_7_days=summary.expiring_within_7_days,
        onboarding_by_status=summary.onboarding_by_status,
        recent_rejections=summary.recent_rejections,
    )


@router.get(
    "/pending-review",
    response_model=PendingReviewResponse,
    summary="Workers pending HR review",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def pending_review(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PendingReviewResponse:
    svc = ComplianceDashboardService(db)
    items, total = await svc.list_workers_pending_review(offset=offset, limit=limit)
    return PendingReviewResponse(
        items=[WorkerProfileResponse.model_validate(w) for w in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/under-review",
    response_model=PendingReviewResponse,
    summary="Workers currently under HR review",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def under_review(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PendingReviewResponse:
    svc = ComplianceDashboardService(db)
    items, total = await svc.list_workers_under_review(offset=offset, limit=limit)
    return PendingReviewResponse(
        items=[WorkerProfileResponse.model_validate(w) for w in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/expiring-documents",
    response_model=ExpiringDocumentsResponse,
    summary="Documents expiring within N days",
    dependencies=[Depends(require_permission("compliance_documents:read"))],
)
async def expiring_documents(
    days_ahead: int = Query(30, ge=1, le=365),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ExpiringDocumentsResponse:
    svc = ComplianceDashboardService(db)
    items, total = await svc.list_expiring_documents(
        days_ahead=days_ahead, offset=offset, limit=limit
    )
    cutoff = (datetime.now(UTC) + timedelta(days=days_ahead)).date()
    return ExpiringDocumentsResponse(
        items=[DocumentResponse.model_validate(d) for d in items],
        total=total,
        cutoff_date=cutoff,
    )


@router.get(
    "/review-queue",
    response_model=DocumentListResponse,
    summary="Documents awaiting HR review",
    dependencies=[Depends(require_permission("compliance_documents:read"))],
)
async def review_queue(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    svc = HRReviewService(db)
    items, total = await svc.get_pending_review_queue(offset=offset, limit=limit)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in items],
        total=total,
        offset=offset,
        limit=limit,
    )

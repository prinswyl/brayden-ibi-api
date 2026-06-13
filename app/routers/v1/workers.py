"""
Worker profile management endpoints.

  POST   /api/v1/workers                    — create worker profile (HR)
  GET    /api/v1/workers                    — list workers (HR/admin)
  GET    /api/v1/workers/{worker_id}        — get worker profile
  PATCH  /api/v1/workers/{worker_id}        — update worker profile
  GET    /api/v1/workers/{worker_id}/compliance-summary — aggregate health
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.worker import WorkerProfile
from app.schemas.worker import (
    WorkerComplianceSummaryResponse,
    WorkerProfileCreate,
    WorkerProfileListResponse,
    WorkerProfileResponse,
    WorkerProfileUpdate,
)
from app.services.compliance_dashboard import ComplianceDashboardService
from app.services.onboarding import OnboardingService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/workers", tags=["Workers"])


def _enrich(worker: WorkerProfile, user: User) -> WorkerProfileResponse:
    """Build a WorkerProfileResponse with name/email fields from the linked User."""
    resp = WorkerProfileResponse.model_validate(worker)
    resp.first_name = user.first_name
    resp.last_name = user.last_name
    resp.email = user.email
    return resp


@router.post(
    "",
    response_model=WorkerProfileResponse,
    status_code=201,
    summary="Create worker profile",
    dependencies=[Depends(require_permission("workers:create"))],
)
async def create_worker(
    body: WorkerProfileCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.create_worker_profile(
        user_id=body.user_id,
        trust_id=current_user.trust_id,
        current_user=current_user,
    )
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.get(
    "",
    response_model=WorkerProfileListResponse,
    summary="List workers",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def list_workers(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=500),
    onboarding_status: str | None = Query(None),
    compliance_stage: str | None = Query(None),
    first_shift_cleared: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileListResponse:
    from app.repositories.worker import WorkerRepository
    from app.shared.enums import ComplianceStage, OnboardingStatus
    repo = WorkerRepository(db)
    pairs, total = await repo.list_with_users(
        offset=offset,
        limit=limit,
        onboarding_status=OnboardingStatus(onboarding_status) if onboarding_status else None,
        compliance_stage=ComplianceStage(compliance_stage) if compliance_stage else None,
        first_shift_cleared=first_shift_cleared,
    )
    return WorkerProfileListResponse(
        items=[_enrich(w, u) for w, u in pairs],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{worker_id}",
    response_model=WorkerProfileResponse,
    summary="Get worker profile",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def get_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    from app.repositories.worker import WorkerRepository
    repo = WorkerRepository(db)
    row = await repo.get_with_user(worker_id)
    if row is None:
        from app.shared.exceptions import NotFoundError
        raise NotFoundError("WorkerProfile", str(worker_id))
    return _enrich(row[0], row[1])


@router.patch(
    "/{worker_id}",
    response_model=WorkerProfileResponse,
    summary="Update worker profile",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def update_worker(
    worker_id: UUID,
    body: WorkerProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    from app.repositories.worker import WorkerRepository
    repo = WorkerRepository(db)
    worker = await repo.get_by_id_or_404(worker_id)
    updates = body.model_dump(exclude_unset=True)
    worker = await repo.update(worker, **updates)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.get(
    "/{worker_id}/profile",
    response_model=None,
    summary="Full personal profile for HR/admin — includes DOB, NI, address, RTW details",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def get_worker_full_profile(
    worker_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.routers.v1.worker_self import get_me as _get_me
    from app.core.auth import CurrentUser as _CU
    # Build a synthetic CurrentUser scoped to the worker's own user_id so
    # the existing get_me logic resolves the correct profile.
    from app.repositories.worker import WorkerRepository
    repo = WorkerRepository(db)
    row = await repo.get_with_user(worker_id)
    if row is None:
        from app.shared.exceptions import NotFoundError
        raise NotFoundError("WorkerProfile", str(worker_id))
    worker, user = row
    # Construct a CurrentUser scoped to the worker so get_me resolves their profile
    worker_cu = _CU(
        user_id=user.id,
        trust_id=worker.trust_id,
        email=user.email,
        roles=[],
    )
    return await _get_me(current_user=worker_cu, db=db)


@router.get(
    "/{worker_id}/compliance-summary",
    response_model=WorkerComplianceSummaryResponse,
    summary="Worker aggregate compliance health",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def worker_compliance_summary(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkerComplianceSummaryResponse:
    svc = ComplianceDashboardService(db)
    summary = await svc.get_worker_compliance_summary(worker_id)
    return WorkerComplianceSummaryResponse(
        worker_id=summary.worker_id,
        onboarding_status=summary.onboarding_status,
        compliance_stage=summary.compliance_stage,
        compliance_health=summary.compliance_health,
        is_amber=summary.is_amber,
        compliance_expires_at=summary.compliance_expires_at,
        total_documents=summary.total_documents,
        approved_documents=summary.approved_documents,
        pending_documents=summary.pending_documents,
        rejected_documents=summary.rejected_documents,
        expiring_soon=summary.expiring_soon,
    )

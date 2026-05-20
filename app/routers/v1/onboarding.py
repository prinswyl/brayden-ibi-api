"""
Onboarding workflow endpoints.

  POST /api/v1/workers/{worker_id}/onboarding/submit
  POST /api/v1/workers/{worker_id}/onboarding/start-review
  POST /api/v1/workers/{worker_id}/onboarding/approve
  POST /api/v1/workers/{worker_id}/onboarding/reject
  POST /api/v1/workers/{worker_id}/onboarding/suspend
  POST /api/v1/workers/{worker_id}/onboarding/reinstate
  POST /api/v1/workers/{worker_id}/onboarding/set-amber
  POST /api/v1/workers/{worker_id}/onboarding/clear-amber
  GET  /api/v1/workers/{worker_id}/onboarding/notes
  POST /api/v1/workers/{worker_id}/onboarding/notes
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.onboarding import (
    AddNoteRequest,
    ApproveWorkerRequest,
    OnboardingNoteListResponse,
    OnboardingNoteResponse,
    RejectWorkerRequest,
    ReinstateWorkerRequest,
    SetAmberRequest,
    StartReviewRequest,
    SubmitForReviewRequest,
    SuspendWorkerRequest,
)
from app.schemas.worker import WorkerProfileResponse
from app.services.onboarding import OnboardingService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/workers/{worker_id}/onboarding", tags=["Onboarding"])


@router.post(
    "/submit",
    response_model=WorkerProfileResponse,
    summary="Submit worker profile for HR review",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def submit_for_review(
    worker_id: UUID,
    _: SubmitForReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.submit_for_review(worker_id, current_user=current_user)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.post(
    "/start-review",
    response_model=WorkerProfileResponse,
    summary="HR starts reviewing a submitted worker profile",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def start_review(
    worker_id: UUID,
    body: StartReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.start_review(worker_id, current_user=current_user, notes=body.notes)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.post(
    "/approve",
    response_model=WorkerProfileResponse,
    summary="HR approves worker — grants compliance clearance",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def approve_worker(
    worker_id: UUID,
    body: ApproveWorkerRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.approve_worker(worker_id, current_user=current_user, notes=body.notes)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.post(
    "/reject",
    response_model=WorkerProfileResponse,
    summary="HR rejects worker onboarding",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def reject_worker(
    worker_id: UUID,
    body: RejectWorkerRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.reject_worker(worker_id, reason=body.reason, current_user=current_user)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.post(
    "/suspend",
    response_model=WorkerProfileResponse,
    summary="Suspend a worker",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def suspend_worker(
    worker_id: UUID,
    body: SuspendWorkerRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.suspend_worker(worker_id, reason=body.reason, current_user=current_user)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.post(
    "/reinstate",
    response_model=WorkerProfileResponse,
    summary="Reinstate a suspended worker",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def reinstate_worker(
    worker_id: UUID,
    body: ReinstateWorkerRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.reinstate_worker(worker_id, current_user=current_user, notes=body.notes)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.post(
    "/set-amber",
    response_model=WorkerProfileResponse,
    summary="Flag worker as amber (conditionally deployable)",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def set_amber(
    worker_id: UUID,
    body: SetAmberRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.set_amber(worker_id, reason=body.reason, current_user=current_user)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.post(
    "/clear-amber",
    response_model=WorkerProfileResponse,
    summary="Clear the amber flag",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def clear_amber(
    worker_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    svc = OnboardingService(db)
    worker = await svc.clear_amber(worker_id, current_user=current_user)
    await db.commit()
    return WorkerProfileResponse.model_validate(worker)


@router.get(
    "/notes",
    response_model=OnboardingNoteListResponse,
    summary="List onboarding notes for a worker",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def list_notes(
    worker_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> OnboardingNoteListResponse:
    from app.repositories.onboarding_note import OnboardingNoteRepository
    repo = OnboardingNoteRepository(db)
    notes = await repo.list_for_worker(worker_id, offset=offset, limit=limit)
    return OnboardingNoteListResponse(
        items=[OnboardingNoteResponse.model_validate(n) for n in notes],
        total=len(notes),
    )


@router.post(
    "/notes",
    response_model=OnboardingNoteResponse,
    status_code=201,
    summary="Add a manual note to a worker's onboarding record",
    dependencies=[Depends(require_permission("workers:update"))],
)
async def add_note(
    worker_id: UUID,
    body: AddNoteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingNoteResponse:
    svc = OnboardingService(db)
    note = await svc.add_manual_note(
        worker_id,
        content=body.content,
        visibility=body.visibility,
        current_user=current_user,
    )
    await db.commit()
    return OnboardingNoteResponse.model_validate(note)

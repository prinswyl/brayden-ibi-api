"""
First-shift DBS verification endpoints.

  POST /api/v1/verification/first-shift              — record verification
  GET  /api/v1/verification/first-shift/status       — check status for worker+school
  GET  /api/v1/workers/{worker_id}/verifications     — list worker's verifications
  GET  /api/v1/schools/{school_id}/verifications     — list school's verifications
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.verification import (
    FirstShiftStatusResponse,
    FirstShiftVerificationListResponse,
    FirstShiftVerificationResponse,
    VerifyFirstShiftRequest,
)
from app.services.first_shift import FirstShiftService

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["First-Shift Verification"])


@router.post(
    "/verification/first-shift",
    response_model=FirstShiftVerificationResponse,
    status_code=201,
    summary="Record first-shift DBS verification",
    dependencies=[Depends(require_permission("first_shift:verify"))],
)
async def verify_first_shift(
    body: VerifyFirstShiftRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FirstShiftVerificationResponse:
    svc = FirstShiftService(db)
    verification = await svc.verify_first_shift(
        worker_id=body.worker_id,
        school_id=body.school_id,
        trust_id=current_user.trust_id,
        dbs_seen_and_matched=body.dbs_seen_and_matched,
        verification_date=body.verification_date,
        notes=body.notes,
        current_user=current_user,
    )
    await db.commit()
    return FirstShiftVerificationResponse.model_validate(verification)


@router.get(
    "/verification/first-shift/status",
    response_model=FirstShiftStatusResponse,
    summary="Check first-shift verification status for a worker at a school",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def get_verification_status(
    worker_id: UUID = Query(...),
    school_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> FirstShiftStatusResponse:
    svc = FirstShiftService(db)
    verification = await svc.get_verification_status(worker_id, school_id)
    return FirstShiftStatusResponse(
        worker_id=worker_id,
        school_id=school_id,
        is_verified=verification is not None,
        verification=FirstShiftVerificationResponse.model_validate(verification) if verification else None,
    )


@router.get(
    "/workers/{worker_id}/verifications",
    response_model=FirstShiftVerificationListResponse,
    summary="List all first-shift verifications for a worker",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def list_worker_verifications(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FirstShiftVerificationListResponse:
    svc = FirstShiftService(db)
    items = await svc.list_worker_verifications(worker_id)
    return FirstShiftVerificationListResponse(
        items=[FirstShiftVerificationResponse.model_validate(v) for v in items],
        total=len(items),
    )


@router.get(
    "/schools/{school_id}/verifications",
    response_model=FirstShiftVerificationListResponse,
    summary="List first-shift verifications at a school",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def list_school_verifications(
    school_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> FirstShiftVerificationListResponse:
    svc = FirstShiftService(db)
    items = await svc.list_school_verifications(school_id, offset=offset, limit=limit)
    return FirstShiftVerificationListResponse(
        items=[FirstShiftVerificationResponse.model_validate(v) for v in items],
        total=len(items),
    )

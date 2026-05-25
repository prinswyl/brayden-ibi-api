"""
HR-facing Single Central Record (SCR) endpoints.

  GET    /api/v1/workers/{worker_id}/scr
  PATCH  /api/v1/workers/{worker_id}/scr/id-verification
  POST   /api/v1/workers/{worker_id}/scr/initial-id-check
  POST   /api/v1/workers/{worker_id}/scr/physical-id
  POST   /api/v1/workers/{worker_id}/scr/dbs
  POST   /api/v1/workers/{worker_id}/scr/rtw
  POST   /api/v1/workers/{worker_id}/scr/references/{ref_num}/advance
  POST   /api/v1/workers/{worker_id}/scr/barred-list
  POST   /api/v1/workers/{worker_id}/scr/tra
  POST   /api/v1/workers/{worker_id}/scr/qualifications
  GET    /api/v1/scr/export
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.scr import (
    AdvanceReferenceStatusRequest,
    ConfirmPhysicalIDRequest,
    RecordCheckRequest,
    RecordInitialIDCheckRequest,
    RecordRTWCheckRequest,
    SCRRecordResponse,
    SCRRegisterResponse,
    SetIDVerificationMethodRequest,
    UpdateDBSRequest,
)
from app.services.scr import SCRService

router = APIRouter(tags=["SCR"])


@router.get(
    "/workers/{worker_id}/scr",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:read"))],
)
async def get_scr(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.get_or_create(worker_id, current_user.trust_id)
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.patch(
    "/workers/{worker_id}/scr/id-verification",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def set_id_verification_method(
    worker_id: UUID,
    body: SetIDVerificationMethodRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.set_id_verification_method(worker_id, body.method, current_user=current_user)
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/initial-id-check",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def record_initial_id_check(
    worker_id: UUID,
    body: RecordInitialIDCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.record_initial_id_check(
        worker_id, checked_date=body.checked_date, notes=body.notes, current_user=current_user
    )
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/physical-id",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
    summary="Record physical in-person ID verification (KCSIE mandatory gate)",
)
async def confirm_physical_id(
    worker_id: UUID,
    body: ConfirmPhysicalIDRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.confirm_physical_id(
        worker_id,
        confirmed_date=body.confirmed_date,
        location=body.location,
        current_user=current_user,
    )
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/dbs",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def update_dbs(
    worker_id: UUID,
    body: UpdateDBSRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.update_dbs(worker_id, **body.model_dump(exclude_none=True), current_user=current_user)
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/rtw",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def record_rtw(
    worker_id: UUID,
    body: RecordRTWCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.record_rtw_check(
        worker_id, checked_date=body.checked_date, evidence_type=body.evidence_type, current_user=current_user
    )
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/references/{reference_number}/advance",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def advance_reference(
    worker_id: UUID,
    reference_number: int,
    body: AdvanceReferenceStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.advance_reference_status(
        worker_id, reference_number, body.status, current_user=current_user
    )
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/barred-list",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def record_barred_list(
    worker_id: UUID,
    body: RecordCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.record_barred_list_check(worker_id, checked_date=body.checked_date, current_user=current_user)
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/tra",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def record_tra(
    worker_id: UUID,
    body: RecordCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.record_tra_check(worker_id, checked_date=body.checked_date, current_user=current_user)
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.post(
    "/workers/{worker_id}/scr/qualifications",
    response_model=SCRRecordResponse,
    dependencies=[Depends(require_permission("workers:update"))],
)
async def record_qualifications(
    worker_id: UUID,
    body: RecordCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    scr = await svc.record_qualifications_check(worker_id, checked_date=body.checked_date, current_user=current_user)
    await db.commit()
    return SCRRecordResponse.model_validate(scr)


@router.get(
    "/workers/{worker_id}/scr/references",
    dependencies=[Depends(require_permission("workers:read"))],
)
async def list_worker_references(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.scr import WorkerReference
    result = await db.execute(
        select(WorkerReference)
        .where(WorkerReference.worker_id == worker_id)
        .order_by(WorkerReference.reference_number)
    )
    from app.schemas.worker_self import WorkerReferenceResponse
    return [WorkerReferenceResponse.model_validate(r) for r in result.scalars().all()]


@router.get(
    "/scr/register",
    response_model=SCRRegisterResponse,
    dependencies=[Depends(require_permission("workers:read"))],
    summary="Full SCR register — all workers with their compliance checks",
)
async def get_scr_register(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    items, total = await svc.list_register(current_user.trust_id, limit=limit, offset=offset)
    return SCRRegisterResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/scr/export",
    dependencies=[Depends(require_permission("workers:read"))],
    summary="Export all SCR records as CSV for Ofsted/ISI audit",
)
async def export_scr(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = SCRService(db)
    csv_content = await svc.export_csv(current_user.trust_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scr_export.csv"},
    )

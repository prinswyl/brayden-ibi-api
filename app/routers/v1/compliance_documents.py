"""
Compliance document management endpoints.

  POST  /api/v1/workers/{worker_id}/documents            — record upload
  GET   /api/v1/workers/{worker_id}/documents            — list documents
  GET   /api/v1/workers/{worker_id}/documents/{doc_id}  — get document
  POST  /api/v1/workers/{worker_id}/documents/{doc_id}/approve
  POST  /api/v1/workers/{worker_id}/documents/{doc_id}/reject
  POST  /api/v1/workers/{worker_id}/documents/{doc_id}/request-reupload
  POST  /api/v1/workers/{worker_id}/documents/{doc_id}/override-status
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.compliance_document import (
    ApproveDocumentRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadRequest,
    OverrideDocumentStatusRequest,
    RejectDocumentRequest,
    ReuploadRequestBody,
)
from app.services.compliance_document import ComplianceDocumentService
from app.services.hr_review import HRReviewService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/workers/{worker_id}/documents", tags=["Compliance Documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=201,
    summary="Record a document upload",
    dependencies=[Depends(require_permission("compliance_documents:upload"))],
)
async def record_upload(
    worker_id: UUID,
    body: DocumentUploadRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    svc = ComplianceDocumentService(db)
    doc = await svc.record_upload(
        worker_id=worker_id,
        trust_id=current_user.trust_id,
        document_type=body.document_type,
        storage_path=body.storage_path,
        storage_bucket=body.storage_bucket,
        file_name=body.file_name,
        file_size_bytes=body.file_size_bytes,
        mime_type=body.mime_type,
        expiry_date=body.expiry_date,
        label=body.label,
        current_user=current_user,
    )
    await db.commit()
    return DocumentResponse.model_validate(doc)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List compliance documents for a worker",
    dependencies=[Depends(require_permission("compliance_documents:read"))],
)
async def list_documents(
    worker_id: UUID,
    include_superseded: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    svc = ComplianceDocumentService(db)
    items, total = await svc.list_worker_documents(
        worker_id,
        include_superseded=include_superseded,
        offset=offset,
        limit=limit,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a single compliance document",
    dependencies=[Depends(require_permission("compliance_documents:read"))],
)
async def get_document(
    worker_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    svc = ComplianceDocumentService(db)
    doc = await svc.get_document(document_id)
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/approve",
    response_model=DocumentResponse,
    summary="HR approves a compliance document",
    dependencies=[Depends(require_permission("compliance_documents:approve"))],
)
async def approve_document(
    worker_id: UUID,
    document_id: UUID,
    body: ApproveDocumentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    svc = HRReviewService(db)
    doc = await svc.approve_document(document_id, notes=body.notes, current_user=current_user)
    await db.commit()
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/reject",
    response_model=DocumentResponse,
    summary="HR rejects a compliance document",
    dependencies=[Depends(require_permission("compliance_documents:reject"))],
)
async def reject_document(
    worker_id: UUID,
    document_id: UUID,
    body: RejectDocumentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    svc = HRReviewService(db)
    doc = await svc.reject_document(document_id, reason=body.reason, current_user=current_user)
    await db.commit()
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/request-reupload",
    response_model=DocumentResponse,
    summary="HR requests worker to re-upload a document",
    dependencies=[Depends(require_permission("compliance_documents:reject"))],
)
async def request_reupload(
    worker_id: UUID,
    document_id: UUID,
    body: ReuploadRequestBody,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    svc = HRReviewService(db)
    doc = await svc.request_reupload(document_id, reason=body.reason, current_user=current_user)
    await db.commit()
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/override-status",
    response_model=DocumentResponse,
    summary="HR admin override — set any document status with mandatory justification",
    dependencies=[Depends(require_permission("compliance_documents:approve"))],
)
async def override_status(
    worker_id: UUID,
    document_id: UUID,
    body: OverrideDocumentStatusRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    svc = HRReviewService(db)
    doc = await svc.override_document_status(
        document_id,
        new_status=body.status,
        notes=body.notes,
        current_user=current_user,
    )
    await db.commit()
    return DocumentResponse.model_validate(doc)

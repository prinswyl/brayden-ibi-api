from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import APIModel, ORMModel, TenantedModel
from app.shared.enums import DocumentStatus, DocumentType


class DocumentUploadRequest(APIModel):
    """
    Records a document that has already been uploaded to Supabase Storage.
    The frontend obtains a presigned upload URL, uploads the file directly,
    then calls this endpoint with the resulting storage_path.
    """
    document_type: DocumentType
    storage_path: str = Field(..., min_length=1)
    storage_bucket: str = "compliance-docs"
    file_name: str = Field(..., min_length=1)
    file_size_bytes: int | None = None
    mime_type: str | None = None
    expiry_date: date | None = None
    label: str | None = None


class DocumentResponse(TenantedModel):
    worker_id: UUID
    document_type: DocumentType
    label: str | None
    status: DocumentStatus
    storage_path: str
    storage_bucket: str
    file_name: str
    file_size_bytes: int | None
    mime_type: str | None
    version_number: int
    supersedes_id: UUID | None
    expiry_date: date | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    uploaded_by: UUID
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(ORMModel):
    items: list[DocumentResponse]
    total: int
    offset: int
    limit: int


class ApproveDocumentRequest(APIModel):
    notes: str | None = None


class RejectDocumentRequest(APIModel):
    reason: str = Field(..., min_length=5)


class ReuploadRequestBody(APIModel):
    reason: str = Field(..., min_length=5)


class OverrideDocumentStatusRequest(APIModel):
    status: DocumentStatus
    notes: str = Field(..., min_length=10, description="Mandatory justification for override.")

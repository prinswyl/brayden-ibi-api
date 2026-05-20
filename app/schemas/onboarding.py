from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import APIModel, ORMModel
from app.shared.enums import NoteVisibility, OnboardingNoteType, OnboardingStatus


class SubmitForReviewRequest(APIModel):
    pass  # No body required — action is implicit


class StartReviewRequest(APIModel):
    notes: str | None = None


class ApproveWorkerRequest(APIModel):
    notes: str | None = None


class RejectWorkerRequest(APIModel):
    reason: str = Field(..., min_length=10, description="Must be at least 10 characters.")


class SuspendWorkerRequest(APIModel):
    reason: str = Field(..., min_length=10)


class ReinstateWorkerRequest(APIModel):
    notes: str | None = None


class SetAmberRequest(APIModel):
    reason: str = Field(..., min_length=5)


class AddNoteRequest(APIModel):
    content: str = Field(..., min_length=1, max_length=5000)
    visibility: NoteVisibility = NoteVisibility.internal


class OnboardingNoteResponse(ORMModel):
    id: UUID
    worker_id: UUID
    author_id: UUID
    note_type: OnboardingNoteType
    content: str
    visibility: NoteVisibility
    previous_status: OnboardingStatus | None
    new_status: OnboardingStatus | None
    created_at: datetime


class OnboardingNoteListResponse(ORMModel):
    items: list[OnboardingNoteResponse]
    total: int

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import APIModel, ORMModel, TenantedModel
from app.shared.enums import ComplianceHealth, ComplianceStage, OnboardingStatus


class WorkerProfileCreate(APIModel):
    user_id: UUID
    preferred_name: str | None = None
    gender: str | None = None
    ethnicity: str | None = None
    disability_declared: bool | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None


class WorkerProfileUpdate(APIModel):
    preferred_name: str | None = None
    gender: str | None = None
    ethnicity: str | None = None
    disability_declared: bool | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None


class WorkerProfileResponse(TenantedModel):
    user_id: UUID
    preferred_name: str | None
    gender: str | None
    ethnicity: str | None
    disability_declared: bool | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    onboarding_status: OnboardingStatus
    compliance_stage: ComplianceStage
    is_amber: bool
    suspended_at: datetime | None
    suspension_reason: str | None
    compliance_expires_at: datetime | None
    first_shift_cleared: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class WorkerProfileListResponse(ORMModel):
    items: list[WorkerProfileResponse]
    total: int
    offset: int
    limit: int


class WorkerComplianceSummaryResponse(ORMModel):
    worker_id: UUID
    onboarding_status: OnboardingStatus
    compliance_stage: ComplianceStage
    compliance_health: ComplianceHealth
    is_amber: bool
    compliance_expires_at: datetime | None
    total_documents: int
    approved_documents: int
    pending_documents: int
    rejected_documents: int
    expiring_soon: int

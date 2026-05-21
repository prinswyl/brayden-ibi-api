from __future__ import annotations

from uuid import UUID

from app.schemas.base import APIModel, ORMModel, TenantedModel


class SchoolCreateRequest(APIModel):
    name: str
    urn: str | None = None
    phase: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    postcode: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


class SchoolUpdateRequest(APIModel):
    name: str | None = None
    urn: str | None = None
    phase: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    postcode: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    is_active: bool | None = None


class SchoolResponse(TenantedModel):
    name: str
    urn: str | None
    phase: str | None
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    postcode: str | None
    contact_email: str | None
    contact_phone: str | None
    is_active: bool


class SchoolListResponse(ORMModel):
    items: list[SchoolResponse]
    total: int
    offset: int
    limit: int

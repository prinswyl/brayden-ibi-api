"""
Trust settings endpoints.

  GET   /api/v1/trust/info       — trust name + slug (for sharing signup link)
  GET   /api/v1/trust/settings   — read trust DBS portal config, policies, DSL
  PATCH /api/v1/trust/settings   — trust admin updates settings
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.models.trust import Trust
from app.schemas.worker_self import TrustSettingsResponse, TrustSettingsUpdateRequest
from app.services.trust_settings import TrustSettingsService

router = APIRouter(prefix="/trust", tags=["Trust Settings"])


class TrustInfoResponse(BaseModel):
    name: str
    slug: str


@router.get("/info", response_model=TrustInfoResponse)
async def get_trust_info(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the trust name and slug so admins can share the worker signup URL."""
    result = await db.execute(
        select(Trust).where(Trust.id == current_user.trust_id, Trust.deleted_at.is_(None))
    )
    trust = result.scalar_one_or_none()
    if not trust:
        from app.shared.exceptions import NotFoundError
        raise NotFoundError("Trust", str(current_user.trust_id))
    return TrustInfoResponse(name=trust.name, slug=trust.slug)


@router.get("/settings", response_model=TrustSettingsResponse)
async def get_trust_settings(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = TrustSettingsService(db)
    settings = await svc.get(current_user.trust_id)
    if not settings:
        from app.models.scr import TrustSettings
        return TrustSettingsResponse.model_validate(TrustSettings(
            trust_id=current_user.trust_id,
            casual_worker_agreement_version="1.0",
        ))
    return TrustSettingsResponse.model_validate(settings)


@router.patch(
    "/settings",
    response_model=TrustSettingsResponse,
    dependencies=[Depends(require_permission("trust:update"))],
)
async def update_trust_settings(
    body: TrustSettingsUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = TrustSettingsService(db)
    settings = await svc.upsert(current_user.trust_id, **body.model_dump(exclude_none=True))
    await db.commit()
    return TrustSettingsResponse.model_validate(settings)

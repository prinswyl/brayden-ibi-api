"""
Trust settings endpoints.

  GET   /api/v1/trust/settings   — read trust DBS portal config, policies, DSL
  PATCH /api/v1/trust/settings   — trust admin updates settings
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.schemas.worker_self import TrustSettingsResponse, TrustSettingsUpdateRequest
from app.services.trust_settings import TrustSettingsService

router = APIRouter(prefix="/trust/settings", tags=["Trust Settings"])


@router.get("", response_model=TrustSettingsResponse)
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
    "",
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

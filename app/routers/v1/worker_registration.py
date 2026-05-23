"""
Public worker self-registration endpoint.

No authentication required — this is called immediately after a worker
verifies their OTP for the first time, before their JWT carries a
trust_id or role claims.

POST /api/v1/auth/register-worker
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, Settings
from app.core.auth import validate_token
from app.core.dependencies import get_public_db
from app.services.worker_registration import WorkerRegistrationService
from app.shared.exceptions import InvalidTokenError

router = APIRouter(prefix="/auth", tags=["Auth"])


class WorkerRegisterRequest(BaseModel):
    first_name: str
    last_name: str
    trust_slug: str


class WorkerRegisterResponse(BaseModel):
    user_id: str
    message: str


@router.post(
    "/register-worker",
    response_model=WorkerRegisterResponse,
    status_code=201,
    summary="Self-register as a worker",
)
async def register_worker(
    body: WorkerRegisterRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_public_db),
    settings: Settings = Depends(get_settings),
) -> WorkerRegisterResponse:
    """
    Called by a worker immediately after OTP verification.
    The Bearer token is the fresh Supabase session token — it has a valid
    `sub` (user_id) and `email` but no trust_id yet.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidTokenError("Bearer token required.")

    token = authorization.removeprefix("Bearer ")

    # Validate the token signature and extract claims — trust_id will be None
    # here, which is expected for a brand-new self-registered user.
    try:
        claims = validate_token(token, settings)
    except Exception:
        raise InvalidTokenError("Invalid or expired token.")

    svc = WorkerRegistrationService(db)
    user = await svc.register(
        auth_user_id=claims.user_id,
        email=claims.email,
        first_name=body.first_name,
        last_name=body.last_name,
        trust_slug=body.trust_slug,
    )

    return WorkerRegisterResponse(
        user_id=str(user.id),
        message="Registration complete.",
    )

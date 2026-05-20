"""
Authentication utility endpoints.

  GET /api/v1/auth/me   — returns the current user's identity from the JWT.
                          Useful for frontend bootstrapping and debugging.

No login/logout endpoints here — authentication is handled entirely by
Supabase Auth. This router only exposes endpoints that consume a valid JWT.
"""

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.schemas.auth import CurrentUserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me", response_model=CurrentUserResponse, summary="Current user identity")
async def get_me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    """
    Returns the identity decoded from the Bearer token.
    Validates the token is current and the trust context is established.
    """
    return CurrentUserResponse(
        user_id=current_user.user_id,
        trust_id=current_user.trust_id,
        email=current_user.email,
        roles=current_user.roles,
        is_superadmin=current_user.is_superadmin,
    )

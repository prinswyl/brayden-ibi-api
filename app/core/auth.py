"""
JWT validation and current-user dependency.

Flow:
  1. Client sends: Authorization: Bearer <supabase_jwt>
  2. validate_token()   — verifies signature + claims locally (no network call)
  3. TokenClaims        — parsed claims extracted from the verified JWT
  4. get_current_user() — FastAPI dependency that validates the token and
                          returns a CurrentUser value object

The trust_id is read from the JWT custom claim "trust_id", which must be
injected by a Supabase Auth hook (see scripts/seed_system_roles.py for the
PostgreSQL function that does this).
"""

from dataclasses import dataclass, field
from uuid import UUID

import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import Settings, get_settings
from app.shared.constants import JWT_CLAIM_TRUST_ID, ROLE_PLATFORM_SUPERADMIN
from app.shared.exceptions import InvalidTokenError, TenantContextMissingError, TokenExpiredError

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Validated, parsed JWT claims. Immutable by design."""
    user_id: UUID
    trust_id: UUID | None
    email: str
    roles: list[str] = field(default_factory=list)
    school_ids: list[UUID] = field(default_factory=list)
    raw: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def is_superadmin(self) -> bool:
        return ROLE_PLATFORM_SUPERADMIN in self.roles


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Resolved user context attached to every authenticated request."""
    user_id: UUID
    trust_id: UUID
    email: str
    roles: list[str]
    school_ids: list[UUID] = field(default_factory=list)

    def has_role(self, *role_names: str) -> bool:
        return any(r in self.roles for r in role_names)

    @property
    def is_superadmin(self) -> bool:
        return ROLE_PLATFORM_SUPERADMIN in self.roles


def validate_token(token: str, settings: Settings) -> TokenClaims:
    """
    Validate a Supabase JWT and return its parsed claims.
    Raises InvalidTokenError or TokenExpiredError — never propagates jose internals.
    """
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
        )
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError as exc:
        logger.warning("JWT validation failed", reason=str(exc))
        raise InvalidTokenError()

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise InvalidTokenError("Token is missing a valid subject claim.")

    raw_trust_id = payload.get(JWT_CLAIM_TRUST_ID)
    trust_id: UUID | None = None
    if raw_trust_id:
        try:
            trust_id = UUID(str(raw_trust_id))
        except ValueError:
            raise InvalidTokenError("Token contains an invalid trust_id claim.")

    # Roles and school_ids may be stored in app_metadata or a top-level claim
    app_metadata: dict = payload.get("app_metadata") or {}
    roles: list[str] = app_metadata.get("roles") or payload.get("roles") or []
    raw_school_ids: list = app_metadata.get("school_ids") or []
    school_ids: list[UUID] = []
    for sid in raw_school_ids:
        try:
            school_ids.append(UUID(str(sid)))
        except (ValueError, AttributeError):
            pass

    return TokenClaims(
        user_id=user_id,
        trust_id=trust_id,
        email=payload.get("email", ""),
        roles=roles,
        school_ids=school_ids,
        raw=payload,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """
    FastAPI dependency: validates the Bearer token and returns a CurrentUser.
    Raises 401 if no/invalid token, 403 if trust_id is absent.
    """
    if credentials is None:
        logger.warning("No Bearer credentials in request — Authorization header missing or empty")
        raise InvalidTokenError("No Bearer token provided.")

    token_preview = credentials.credentials[:30] if credentials.credentials else "(empty)"
    logger.warning("Validating token", token_preview=token_preview, token_length=len(credentials.credentials or ""))
    claims = validate_token(credentials.credentials, settings)

    if claims.trust_id is None and not claims.is_superadmin:
        raise TenantContextMissingError(
            "The token does not contain a trust_id. "
            "Ensure the Supabase custom claims hook is configured."
        )

    # Superadmins must still supply a trust_id when operating within a tenant
    if claims.trust_id is None:
        raise TenantContextMissingError(
            "Superadmin requests must include a target trust_id claim."
        )

    structlog.contextvars.bind_contextvars(
        user_id=str(claims.user_id),
        trust_id=str(claims.trust_id),
    )

    return CurrentUser(
        user_id=claims.user_id,
        trust_id=claims.trust_id,
        email=claims.email,
        roles=claims.roles,
        school_ids=claims.school_ids,
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser | None:
    """
    Like get_current_user but returns None instead of raising for public routes.
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, settings)
    except Exception:
        return None

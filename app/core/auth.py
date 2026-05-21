"""
JWT validation and current-user dependency.

Flow:
  1. Client sends: Authorization: Bearer <supabase_jwt>
  2. validate_token()   — verifies signature + claims locally
  3. TokenClaims        — parsed claims extracted from the verified JWT
  4. get_current_user() — FastAPI dependency that validates the token and
                          returns a CurrentUser value object

The trust_id is read from the JWT custom claim "trust_id", which must be
injected by a Supabase Auth hook (see scripts/seed_system_roles.py for the
PostgreSQL function that does this).

Supports both HS256 (legacy Supabase projects) and ES256 (newer Supabase
projects that use asymmetric signing). ES256 keys are fetched from Supabase's
JWKS endpoint and cached in-process.
"""

from dataclasses import dataclass, field
from uuid import UUID

import httpx
import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwk as jose_jwk, jwt

from app.config import Settings, get_settings
from app.shared.constants import JWT_CLAIM_TRUST_ID, ROLE_PLATFORM_SUPERADMIN
from app.shared.exceptions import InvalidTokenError, TenantContextMissingError, TokenExpiredError

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

# Module-level JWKS cache — populated on first ES256 token, reused thereafter.
_jwks_cache: list[dict] | None = None


def _get_jwks_keys(supabase_url: str) -> list[dict]:
    global _jwks_cache
    if _jwks_cache is None:
        try:
            resp = httpx.get(
                f"{supabase_url}/auth/v1/.well-known/jwks.json",
                timeout=10,
            )
            resp.raise_for_status()
            _jwks_cache = resp.json().get("keys", [])
            logger.info("JWKS keys loaded", count=len(_jwks_cache))
        except Exception as exc:
            logger.warning("Failed to fetch JWKS", error=str(exc))
            _jwks_cache = []
    return _jwks_cache


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
    Supports HS256 (symmetric) and ES256 (asymmetric via JWKS).
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", settings.jwt_algorithm)

        if alg == "HS256":
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.jwt_audience,
            )
        else:
            kid = header.get("kid")
            keys = _get_jwks_keys(settings.supabase_url)
            payload = None
            last_exc: JWTError | None = None
            for key_data in keys:
                if kid and key_data.get("kid") != kid:
                    continue
                try:
                    public_key = jose_jwk.construct(key_data)
                    payload = jwt.decode(
                        token,
                        public_key,
                        algorithms=[alg],
                        audience=settings.jwt_audience,
                    )
                    break
                except ExpiredSignatureError:
                    raise
                except JWTError as exc:
                    last_exc = exc
            if payload is None:
                raise last_exc or JWTError("No matching JWKS key found for token")
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError as exc:
        logger.warning("JWT validation failed", reason=str(exc))
        raise InvalidTokenError()

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise InvalidTokenError("Token is missing a valid subject claim.")

    # trust_id, roles, and school_ids are injected into app_metadata by the
    # Supabase custom_access_token_hook function.
    app_metadata: dict = payload.get("app_metadata") or {}
    raw_trust_id = app_metadata.get(JWT_CLAIM_TRUST_ID) or payload.get(JWT_CLAIM_TRUST_ID)
    trust_id: UUID | None = None
    if raw_trust_id:
        try:
            trust_id = UUID(str(raw_trust_id))
        except ValueError:
            raise InvalidTokenError("Token contains an invalid trust_id claim.")

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
        raise InvalidTokenError("No Bearer token provided.")

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

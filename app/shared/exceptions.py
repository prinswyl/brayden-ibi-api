"""
Centralized exception hierarchy for Brayden IBI.

All domain exceptions inherit from BraydenIBIException so the global
exception handler in main.py can catch and serialize them uniformly.
"""

from http import HTTPStatus
from typing import Any


class BraydenIBIException(Exception):
    """Base exception — caught by the global handler and returned as JSON."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        details: Any = None,
        *,
        error_code: str | None = None,
    ) -> None:
        self.message = message
        self.details = details
        if error_code:
            self.error_code = error_code
        super().__init__(message)


# ── Auth / Identity ───────────────────────────────────────────────────────────

class AuthenticationError(BraydenIBIException):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "AUTHENTICATION_REQUIRED"

    def __init__(self, message: str = "Authentication is required.") -> None:
        super().__init__(message)


class InvalidTokenError(BraydenIBIException):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "INVALID_TOKEN"

    def __init__(self, message: str = "The provided token is invalid or has expired.") -> None:
        super().__init__(message)


class TokenExpiredError(BraydenIBIException):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "TOKEN_EXPIRED"

    def __init__(self, message: str = "The token has expired. Please log in again.") -> None:
        super().__init__(message)


# ── Tenant / Multi-tenancy ────────────────────────────────────────────────────

class TenantContextMissingError(BraydenIBIException):
    """Raised when a request reaches a tenant-scoped route without a valid trust context."""
    status_code = HTTPStatus.FORBIDDEN
    error_code = "TENANT_CONTEXT_MISSING"

    def __init__(self, message: str = "Tenant context could not be established.") -> None:
        super().__init__(message)


class TenantNotFoundError(BraydenIBIException):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "TENANT_NOT_FOUND"

    def __init__(self, trust_id: str | None = None) -> None:
        msg = f"Trust '{trust_id}' not found." if trust_id else "Trust not found."
        super().__init__(msg)


class TenantSuspendedError(BraydenIBIException):
    status_code = HTTPStatus.FORBIDDEN
    error_code = "TENANT_SUSPENDED"

    def __init__(self) -> None:
        super().__init__("This trust account has been suspended.")


# ── Authorisation ─────────────────────────────────────────────────────────────

class PermissionDeniedError(BraydenIBIException):
    status_code = HTTPStatus.FORBIDDEN
    error_code = "PERMISSION_DENIED"

    def __init__(self, permission: str | None = None) -> None:
        msg = (
            f"You do not have the required permission: '{permission}'."
            if permission
            else "You do not have permission to perform this action."
        )
        super().__init__(msg)


# ── Resource ─────────────────────────────────────────────────────────────────

class NotFoundError(BraydenIBIException):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "NOT_FOUND"

    def __init__(self, resource: str = "Resource", resource_id: str | None = None) -> None:
        msg = f"{resource} '{resource_id}' not found." if resource_id else f"{resource} not found."
        super().__init__(msg)


class ConflictError(BraydenIBIException):
    status_code = HTTPStatus.CONFLICT
    error_code = "CONFLICT"

    def __init__(self, message: str = "A conflict occurred with existing data.") -> None:
        super().__init__(message)


class ValidationError(BraydenIBIException):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation failed.", details: Any = None) -> None:
        super().__init__(message, details)


# ── Business Logic ────────────────────────────────────────────────────────────

class WorkflowError(BraydenIBIException):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "WORKFLOW_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ComplianceBlockedError(BraydenIBIException):
    """Raised when a booking or action is blocked due to missing compliance."""
    status_code = HTTPStatus.FORBIDDEN
    error_code = "COMPLIANCE_BLOCKED"

    def __init__(self, message: str = "This action is blocked due to outstanding compliance requirements.") -> None:
        super().__init__(message)

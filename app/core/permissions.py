"""
Permission and role-checking dependencies.

Use these as FastAPI dependency factories on individual routes:

    @router.get("/workers", dependencies=[Depends(require_permission("workers:read"))])
    async def list_workers(...):
        ...

    @router.delete("/trusts/{id}", dependencies=[Depends(require_role(ROLE_TRUST_ADMIN))])
    async def delete_trust(...):
        ...
"""

from collections.abc import Callable

from fastapi import Depends

from app.core.auth import CurrentUser, get_current_user
from app.shared.exceptions import PermissionDeniedError


def require_permission(*permissions: str) -> Callable:
    """
    Dependency factory that enforces one or more permission strings.
    The user must hold ALL listed permissions.

    Permission format: "<resource>:<action>"
    e.g. "compliance_documents:approve", "timesheets:export"

    Note: In Phase 1 permissions are stored as roles. A full RBAC permission
    table is implemented in the identity model — this dependency will be
    wired to it in the auth phase. For now it enforces role-level checks.
    """
    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        # Superadmins bypass all permission checks
        if current_user.is_superadmin:
            return current_user

        for permission in permissions:
            if not _user_has_permission(current_user, permission):
                raise PermissionDeniedError(permission)
        return current_user

    return _check


def require_role(*role_names: str) -> Callable:
    """
    Dependency factory that requires the user to hold at least one of the
    listed role names.
    """
    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.is_superadmin:
            return current_user
        if not current_user.has_role(*role_names):
            raise PermissionDeniedError(
                f"Required role(s): {', '.join(role_names)}"
            )
        return current_user

    return _check


def require_superadmin() -> Callable:
    """Dependency that restricts a route to platform superadmins only."""
    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.is_superadmin:
            raise PermissionDeniedError("Platform superadmin access required.")
        return current_user

    return _check


def _user_has_permission(user: CurrentUser, permission: str) -> bool:
    """
    Placeholder permission resolver.

    Phase 1: permission is derived from role membership.
    Phase 2: this will query the role_permissions table via a cached resolver.
    """
    from app.shared.constants import (
        ROLE_COVER_SUPERVISOR,
        ROLE_HR_MANAGER,
        ROLE_PAYROLL_OFFICER,
        ROLE_RECEPTIONIST,
        ROLE_SCHOOL_LEADER,
        ROLE_TRUST_ADMIN,
        ROLE_WORKER,
    )

    # Coarse role-to-permission mapping until the RBAC table is wired up
    role_permission_map: dict[str, set[str]] = {
        # trust_admin has wildcard — all permissions granted implicitly
        ROLE_TRUST_ADMIN: {"*"},
        ROLE_HR_MANAGER: {
            "workers:read", "workers:create", "workers:update",
            "compliance_documents:read", "compliance_documents:approve",
            "compliance_documents:reject", "compliance_documents:upload",
            "dbs_checks:read", "dbs_checks:update",
            "rtw_checks:read", "rtw_checks:update",
            "bookings:read", "timesheets:read",
        },
        # Cover supervisor — the operational role that manages day-to-day cover at school level.
        # Creates bookings, dispatches to workers, checks in/out, confirms hours before payroll.
        ROLE_COVER_SUPERVISOR: {
            "bookings:read", "bookings:create", "bookings:cancel",
            "timesheets:read", "timesheets:approve", "timesheets:reject",
            "workers:read",
            "availability:read",
        },
        # School leader — read-only visibility of cover plans; does not create or manage bookings.
        ROLE_SCHOOL_LEADER: {
            "bookings:read",
            "timesheets:read",
            "workers:read",
        },
        # Receptionist — records physical DBS sighting on a worker's first day at the school (SCR).
        ROLE_RECEPTIONIST: {
            "bookings:read",
            "first_shift:verify",
            "workers:update",  # allowed to confirm physical ID on SCR
        },
        ROLE_PAYROLL_OFFICER: {
            "timesheets:read", "timesheets:export",
            "payroll:read", "payroll:export", "workers:view_sensitive",
        },
        ROLE_WORKER: {
            "availability:read", "availability:write",
            "bookings:read", "timesheets:read", "timesheets:submit",
            "workers:self_update",
            "compliance_documents:read", "compliance_documents:self_upload",
            "onboarding:self_submit",
            "safeguarding:self_complete",
        },
    }

    for role in user.roles:
        granted = role_permission_map.get(role, set())
        if "*" in granted or permission in granted:
            return True
    return False

"""
User provisioning service.

Handles inviting new users into a trust, assigning them roles at specific
schools (or trust-wide), listing, and deactivating both users and individual
role assignments.

Trust-wide roles (trust_admin, hr_manager, payroll_officer) are stored with
school_id = NULL. School-scoped roles (cover_supervisor, receptionist,
school_leader) require a school_id.
"""

from uuid import UUID

import structlog

from app.core.auth import CurrentUser
from app.models.user import User
from app.models.user_assignment import UserSchoolAssignment
from app.repositories.user import UserRepository
from app.repositories.user_assignment import UserSchoolAssignmentRepository
from app.services.supabase_admin import SupabaseAdminService
from app.shared.constants import SYSTEM_ROLES
from app.shared.exceptions import ConflictError, NotFoundError, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

TRUST_WIDE_ROLES = {"trust_admin", "hr_manager", "payroll_officer"}
SCHOOL_SCOPED_ROLES = {"cover_supervisor", "school_leader", "receptionist"}


class UserProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)
        self._assignment_repo = UserSchoolAssignmentRepository(session)
        self._supabase = SupabaseAdminService()

    # ── Invite ─────────────────────────────────────────────────────────────────

    async def invite_user(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        role: str,
        school_id: UUID | None,
        current_user: CurrentUser,
    ) -> User:
        """
        Create a user record and send a Supabase Auth invite email.

        For school-scoped roles, school_id is required.
        For trust-wide roles, school_id must be None.
        """
        _validate_role_school_pair(role, school_id)

        existing = await self._user_repo.get_by_email(email)
        if existing:
            raise ConflictError(f"A user with email '{email}' already exists in this trust.")

        # Call Supabase invite FIRST so we get the auth user's UUID back.
        # public.users.id must equal auth.users.id for the custom claims hook
        # to find the row and inject trust_id into the JWT.
        auth_data = await self._supabase.invite_user_by_email(
            email,
            data={"first_name": first_name, "last_name": last_name},
        )
        auth_user_id = UUID(auth_data["id"])

        user = await self._user_repo.create(
            id=auth_user_id,
            trust_id=current_user.trust_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            invited_by=current_user.user_id,
        )

        await self._assignment_repo.create(
            trust_id=current_user.trust_id,
            user_id=user.id,
            school_id=school_id,
            role=role,
            assigned_by=current_user.user_id,
        )

        logger.info("user_invited", user_id=str(user.id), role=role, invited_by=str(current_user.user_id))
        return user

    # ── Role assignment ────────────────────────────────────────────────────────

    async def assign_role(
        self,
        *,
        user_id: UUID,
        role: str,
        school_id: UUID | None,
        current_user: CurrentUser,
    ) -> UserSchoolAssignment:
        """Add a role assignment to an existing user."""
        _validate_role_school_pair(role, school_id)

        user = await self._user_repo.get_by_id_or_404(user_id)

        existing = await self._assignment_repo.get_for_user_at_school(
            user.id, school_id, role
        )
        if existing and existing.is_active:
            raise ConflictError(
                f"User already holds role '{role}' "
                + (f"at school {school_id}." if school_id else "(trust-wide).")
            )

        if existing and not existing.is_active:
            # Reactivate the old assignment rather than creating a duplicate
            return await self._assignment_repo.update(
                existing,
                is_active=True,
                assigned_by=current_user.user_id,
            )

        assignment = await self._assignment_repo.create(
            trust_id=current_user.trust_id,
            user_id=user.id,
            school_id=school_id,
            role=role,
            assigned_by=current_user.user_id,
        )
        logger.info(
            "role_assigned",
            user_id=str(user_id),
            role=role,
            school_id=str(school_id) if school_id else None,
        )
        return assignment

    async def revoke_role(
        self,
        *,
        assignment_id: UUID,
        current_user: CurrentUser,
    ) -> UserSchoolAssignment:
        """Deactivate a specific role assignment."""
        assignment = await self._assignment_repo.get_by_id_or_404(assignment_id)
        if not assignment.is_active:
            raise ValidationError("Assignment is already inactive.")
        result = await self._assignment_repo.deactivate(assignment)
        logger.info("role_revoked", assignment_id=str(assignment_id), by=str(current_user.user_id))
        return result

    # ── List ───────────────────────────────────────────────────────────────────

    async def list_users(
        self,
        trust_id: UUID,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[User], int]:
        return await self._user_repo.list_for_trust(trust_id, offset=offset, limit=limit)

    async def get_user(self, user_id: UUID) -> User:
        return await self._user_repo.get_by_id_or_404(user_id)

    async def get_user_assignments(self, user_id: UUID) -> list[UserSchoolAssignment]:
        await self._user_repo.get_by_id_or_404(user_id)  # 404 if user not found
        return await self._assignment_repo.get_for_user(user_id)

    # ── Deactivate ─────────────────────────────────────────────────────────────

    async def deactivate_user(
        self, user_id: UUID, *, current_user: CurrentUser
    ) -> User:
        """Suspend a user and deactivate all their role assignments."""
        user = await self._user_repo.get_by_id_or_404(user_id)
        user = await self._user_repo.deactivate(user)

        active_assignments = await self._assignment_repo.get_for_user(user.id)
        for assignment in active_assignments:
            await self._assignment_repo.deactivate(assignment)

        logger.info("user_deactivated", user_id=str(user_id), by=str(current_user.user_id))
        return user


def _validate_role_school_pair(role: str, school_id: UUID | None) -> None:
    if role not in SYSTEM_ROLES:
        raise ValidationError(f"'{role}' is not a recognised system role.")
    if role in TRUST_WIDE_ROLES and school_id is not None:
        raise ValidationError(
            f"Role '{role}' is trust-wide and must not be scoped to a school."
        )
    if role in SCHOOL_SCOPED_ROLES and school_id is None:
        raise ValidationError(
            f"Role '{role}' is school-scoped and requires a school_id."
        )

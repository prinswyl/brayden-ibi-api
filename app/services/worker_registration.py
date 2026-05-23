"""
Worker self-registration service.

Called from the public POST /auth/register-worker endpoint. No JWT
trust_id claim is available at this point — the worker has just
verified their OTP and has a raw Supabase session with no app_metadata
yet. This service:

  1. Looks up the trust by slug.
  2. Creates the public.users row (must match auth.users.id).
  3. Creates the WorkerProfile row.
  4. Creates the worker role assignment (trust-wide, no school scope).
  5. Patches Supabase auth app_metadata so the next issued JWT contains
     trust_id + roles (consumed by the custom claims hook).
"""

from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trust import Trust
from app.models.user import User
from app.models.worker import WorkerProfile
from app.models.user_assignment import UserSchoolAssignment
from app.repositories.user import UserRepository
from app.repositories.user_assignment import UserSchoolAssignmentRepository
from app.services.supabase_admin import SupabaseAdminService
from app.shared.enums import OnboardingStatus
from app.shared.exceptions import ConflictError, NotFoundError

logger = structlog.get_logger(__name__)


class WorkerRegistrationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)
        self._assignment_repo = UserSchoolAssignmentRepository(session)
        self._supabase = SupabaseAdminService()

    async def register(
        self,
        *,
        auth_user_id: UUID,
        email: str,
        first_name: str,
        last_name: str,
        trust_slug: str,
    ) -> User:
        """
        Idempotent: if the user row already exists (e.g. double-submit),
        return it rather than raising.
        """
        # 1. Resolve trust by slug
        trust = await self._get_trust_by_slug(trust_slug)

        # Set RLS session context so INSERT policies accept this session
        await self._session.execute(
            text("SELECT set_config('app.current_trust_id', :v, true)").bindparams(v=str(trust.id))
        )
        await self._session.execute(
            text("SELECT set_config('app.current_user_id', :v, true)").bindparams(v=str(auth_user_id))
        )
        await self._session.execute(text("SELECT set_config('app.is_superadmin', 'false', true)"))

        # 2. Check for existing user (idempotent re-submit)
        existing = await self._user_repo.get_by_email(email)
        if existing:
            # Already registered — return without error so the frontend
            # can still redirect to /worker/onboard
            logger.info("worker_already_registered", user_id=str(existing.id))
            return existing

        # 3. Create public.users row — id must equal auth.users.id
        user = await self._user_repo.create(
            id=auth_user_id,
            trust_id=trust.id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            invited_by=None,
        )

        # 4. Create WorkerProfile
        worker_profile = WorkerProfile(
            trust_id=trust.id,
            user_id=user.id,
            onboarding_status=OnboardingStatus.draft,
        )
        self._session.add(worker_profile)

        # 5. Create worker role assignment (trust-wide, no school)
        await self._assignment_repo.create(
            trust_id=trust.id,
            user_id=user.id,
            school_id=None,
            role="worker",
            assigned_by=user.id,  # self-assigned
        )

        await self._session.flush()

        # 6. Patch Supabase app_metadata so the NEXT JWT carries trust_id + roles
        await self._supabase.update_user_metadata(
            auth_user_id,
            app_metadata={
                "trust_id": str(trust.id),
                "roles": ["worker"],
                "school_ids": [],
            },
        )

        logger.info(
            "worker_self_registered",
            user_id=str(user.id),
            trust_id=str(trust.id),
        )
        return user

    async def _get_trust_by_slug(self, slug: str) -> Trust:
        result = await self._session.execute(
            select(Trust).where(Trust.slug == slug, Trust.deleted_at.is_(None))
        )
        trust = result.scalar_one_or_none()
        if trust is None:
            raise NotFoundError(f"No trust found with slug '{slug}'.")
        return trust

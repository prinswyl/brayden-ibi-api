from uuid import UUID

from sqlalchemy import func, select

from app.models.user import User
from app.models.worker import WorkerProfile
from app.repositories.base import BaseRepository
from app.shared.enums import ComplianceStage, OnboardingStatus


class WorkerRepository(BaseRepository[WorkerProfile]):
    model = WorkerProfile

    async def get_by_user_id(self, user_id: UUID) -> WorkerProfile | None:
        result = await self.session.execute(
            select(WorkerProfile).where(
                WorkerProfile.user_id == user_id,
                WorkerProfile.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_with_user(self, worker_id: UUID) -> tuple[WorkerProfile, User] | None:
        result = await self.session.execute(
            select(WorkerProfile, User)
            .join(User, User.id == WorkerProfile.user_id)
            .where(WorkerProfile.id == worker_id, WorkerProfile.deleted_at.is_(None))
        )
        row = result.one_or_none()
        return (row[0], row[1]) if row else None

    async def list_with_users(
        self,
        *,
        offset: int = 0,
        limit: int = 25,
        onboarding_status: OnboardingStatus | None = None,
        compliance_stage: ComplianceStage | None = None,
        first_shift_cleared: bool | None = None,
    ) -> tuple[list[tuple[WorkerProfile, User]], int]:
        """Return (worker, user) pairs so callers can build enriched responses."""
        where = [WorkerProfile.deleted_at.is_(None)]
        if onboarding_status is not None:
            where.append(WorkerProfile.onboarding_status == onboarding_status)
        if compliance_stage is not None:
            where.append(WorkerProfile.compliance_stage == compliance_stage)
        if first_shift_cleared is not None:
            where.append(WorkerProfile.first_shift_cleared == first_shift_cleared)

        count = (await self.session.execute(
            select(func.count())
            .select_from(WorkerProfile)
            .where(*where)
        )).scalar_one()

        result = await self.session.execute(
            select(WorkerProfile, User)
            .join(User, User.id == WorkerProfile.user_id)
            .where(*where)
            .order_by(User.last_name, User.first_name)
            .offset(offset)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()], count

    async def list_by_onboarding_status(
        self,
        status: OnboardingStatus,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[WorkerProfile], int]:
        return await self.list_all(
            offset=offset, limit=limit, filters={"onboarding_status": status.value}
        )

    async def list_amber_workers(
        self, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[WorkerProfile], int]:
        return await self.list_all(offset=offset, limit=limit, filters={"is_amber": True})

    async def list_by_compliance_stage(
        self,
        stage: ComplianceStage,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[WorkerProfile], int]:
        return await self.list_all(
            offset=offset, limit=limit, filters={"compliance_stage": stage.value}
        )

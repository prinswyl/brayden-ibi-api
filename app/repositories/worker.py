from uuid import UUID

from sqlalchemy import select

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

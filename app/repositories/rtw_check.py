from uuid import UUID

from sqlalchemy import select

from app.models.compliance import RTWCheck
from app.repositories.base import BaseRepository
from app.shared.enums import DocumentStatus


class RTWCheckRepository(BaseRepository[RTWCheck]):
    model = RTWCheck

    async def get_active_for_worker(self, worker_id: UUID) -> RTWCheck | None:
        result = await self.session.execute(
            select(RTWCheck)
            .where(
                RTWCheck.worker_id == worker_id,
                RTWCheck.deleted_at.is_(None),
                RTWCheck.status.notin_([DocumentStatus.expired.value, DocumentStatus.rejected.value]),
            )
            .order_by(RTWCheck.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_worker(self, worker_id: UUID) -> list[RTWCheck]:
        result = await self.session.execute(
            select(RTWCheck)
            .where(RTWCheck.worker_id == worker_id, RTWCheck.deleted_at.is_(None))
            .order_by(RTWCheck.created_at.desc())
        )
        return list(result.scalars().all())

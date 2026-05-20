from uuid import UUID

from sqlalchemy import select

from app.models.compliance import DBSCheck
from app.repositories.base import BaseRepository
from app.shared.enums import DBSStatus


class DBSCheckRepository(BaseRepository[DBSCheck]):
    model = DBSCheck

    async def get_active_for_worker(self, worker_id: UUID) -> DBSCheck | None:
        result = await self.session.execute(
            select(DBSCheck)
            .where(
                DBSCheck.worker_id == worker_id,
                DBSCheck.deleted_at.is_(None),
                DBSCheck.status.notin_([DBSStatus.expired.value]),
            )
            .order_by(DBSCheck.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_worker(self, worker_id: UUID) -> list[DBSCheck]:
        result = await self.session.execute(
            select(DBSCheck)
            .where(DBSCheck.worker_id == worker_id, DBSCheck.deleted_at.is_(None))
            .order_by(DBSCheck.created_at.desc())
        )
        return list(result.scalars().all())

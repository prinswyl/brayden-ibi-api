from uuid import UUID

from sqlalchemy import func, select

from app.models.school import School
from app.repositories.base import BaseRepository


class SchoolRepository(BaseRepository[School]):
    model = School

    async def list_for_trust(
        self, trust_id: UUID, *, offset: int = 0, limit: int = 100, active_only: bool = True
    ) -> tuple[list[School], int]:
        base = select(School).where(
            School.trust_id == trust_id,
            School.deleted_at.is_(None),
        )
        if active_only:
            base = base.where(School.is_active.is_(True))

        count = (await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()

        result = await self.session.execute(
            base.order_by(School.name).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), count

    async def get_for_trust(self, school_id: UUID, trust_id: UUID) -> School | None:
        result = await self.session.execute(
            select(School).where(
                School.id == school_id,
                School.trust_id == trust_id,
                School.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

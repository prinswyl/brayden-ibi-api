from uuid import UUID

from sqlalchemy import select

from app.models.verification import FirstShiftVerification
from app.repositories.base import BaseRepository


class FirstShiftVerificationRepository(BaseRepository[FirstShiftVerification]):
    model = FirstShiftVerification

    async def get_for_worker_school(
        self, worker_id: UUID, school_id: UUID
    ) -> FirstShiftVerification | None:
        result = await self.session.execute(
            select(FirstShiftVerification).where(
                FirstShiftVerification.worker_id == worker_id,
                FirstShiftVerification.school_id == school_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_worker(self, worker_id: UUID) -> list[FirstShiftVerification]:
        result = await self.session.execute(
            select(FirstShiftVerification)
            .where(FirstShiftVerification.worker_id == worker_id)
            .order_by(FirstShiftVerification.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_school(
        self, school_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> list[FirstShiftVerification]:
        result = await self.session.execute(
            select(FirstShiftVerification)
            .where(FirstShiftVerification.school_id == school_id)
            .order_by(FirstShiftVerification.verification_date.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

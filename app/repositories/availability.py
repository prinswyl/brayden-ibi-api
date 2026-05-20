from datetime import date
from uuid import UUID

from sqlalchemy import and_, select

from app.models.availability import WorkerAvailability, WorkerAvailabilityPreferences
from app.repositories.base import BaseRepository


class AvailabilityRepository(BaseRepository[WorkerAvailability]):
    model = WorkerAvailability

    async def get_for_worker_date(self, worker_id: UUID, available_date: date) -> WorkerAvailability | None:
        stmt = select(WorkerAvailability).where(
            WorkerAvailability.worker_id == worker_id,
            WorkerAvailability.available_date == available_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_worker(
        self, worker_id: UUID, *, from_date: date | None = None, to_date: date | None = None
    ) -> list[WorkerAvailability]:
        stmt = select(WorkerAvailability).where(WorkerAvailability.worker_id == worker_id)
        if from_date:
            stmt = stmt.where(WorkerAvailability.available_date >= from_date)
        if to_date:
            stmt = stmt.where(WorkerAvailability.available_date <= to_date)
        stmt = stmt.order_by(WorkerAvailability.available_date)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self, worker_id: UUID, trust_id: UUID, available_date: date, **kwargs
    ) -> WorkerAvailability:
        existing = await self.get_for_worker_date(worker_id, available_date)
        if existing:
            return await self.update(existing, **kwargs)
        return await self.create(
            worker_id=worker_id,
            trust_id=trust_id,
            available_date=available_date,
            **kwargs,
        )


class WorkerAvailabilityPreferencesRepository(BaseRepository[WorkerAvailabilityPreferences]):
    model = WorkerAvailabilityPreferences

    async def get_for_worker(self, worker_id: UUID) -> WorkerAvailabilityPreferences | None:
        stmt = select(WorkerAvailabilityPreferences).where(
            WorkerAvailabilityPreferences.worker_id == worker_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, worker_id: UUID, trust_id: UUID, **kwargs) -> WorkerAvailabilityPreferences:
        existing = await self.get_for_worker(worker_id)
        if existing:
            return await self.update(existing, **kwargs)
        return await self.create(worker_id=worker_id, trust_id=trust_id, **kwargs)

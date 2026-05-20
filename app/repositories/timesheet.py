from datetime import date
from uuid import UUID

from sqlalchemy import select

from app.models.timesheet import Timesheet, TimesheetCorrection
from app.repositories.base import BaseRepository
from app.shared.enums import TimesheetStatus


class TimesheetRepository(BaseRepository[Timesheet]):
    model = Timesheet

    async def get_for_booking(self, booking_id: UUID) -> Timesheet | None:
        stmt = select(Timesheet).where(Timesheet.booking_id == booking_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_worker(
        self, worker_id: UUID, *, from_date: date | None = None, to_date: date | None = None
    ) -> list[Timesheet]:
        stmt = select(Timesheet).where(Timesheet.worker_id == worker_id)
        if from_date:
            stmt = stmt.where(Timesheet.shift_date >= from_date)
        if to_date:
            stmt = stmt.where(Timesheet.shift_date <= to_date)
        stmt = stmt.order_by(Timesheet.shift_date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_approval(self, school_id: UUID) -> list[Timesheet]:
        stmt = select(Timesheet).where(
            Timesheet.school_id == school_id,
            Timesheet.status == TimesheetStatus.submitted,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_status(self, status: TimesheetStatus, *, offset: int = 0, limit: int = 25) -> tuple[list[Timesheet], int]:
        from sqlalchemy import func
        stmt = select(Timesheet).where(Timesheet.status == status)
        count_stmt = select(func.count()).select_from(Timesheet).where(Timesheet.status == status)
        total = (await self.session.execute(count_stmt)).scalar_one()
        result = await self.session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all()), total


class TimesheetCorrectionRepository(BaseRepository[TimesheetCorrection]):
    model = TimesheetCorrection

    async def list_for_timesheet(self, timesheet_id: UUID) -> list[TimesheetCorrection]:
        stmt = (
            select(TimesheetCorrection)
            .where(TimesheetCorrection.timesheet_id == timesheet_id)
            .order_by(TimesheetCorrection.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

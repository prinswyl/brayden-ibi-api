"""
Booking dashboard service — operational queries for staffing operations.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.timesheet import Timesheet
from app.shared.enums import BookingStatus, TimesheetStatus


class BookingDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_summary(self, trust_id: UUID) -> dict:
        today = date.today()
        upcoming_window = today + timedelta(days=7)

        async def _count(status: BookingStatus) -> int:
            result = await self._session.execute(
                select(func.count()).select_from(Booking).where(
                    Booking.trust_id == trust_id,
                    Booking.status == status,
                    Booking.deleted_at.is_(None),
                )
            )
            return result.scalar_one()

        async def _count_timesheets(status: TimesheetStatus) -> int:
            result = await self._session.execute(
                select(func.count()).select_from(Timesheet).where(
                    Timesheet.trust_id == trust_id,
                    Timesheet.status == status,
                )
            )
            return result.scalar_one()

        # Open shifts (no worker assigned yet)
        open_shifts = await self._session.execute(
            select(func.count()).select_from(Booking).where(
                Booking.trust_id == trust_id,
                Booking.status.in_([BookingStatus.requested, BookingStatus.offered]),
                Booking.deleted_at.is_(None),
            )
        )

        # Active bookings (accepted or confirmed)
        active_bookings = await self._session.execute(
            select(func.count()).select_from(Booking).where(
                Booking.trust_id == trust_id,
                Booking.status.in_([BookingStatus.accepted, BookingStatus.confirmed, BookingStatus.checked_in]),
                Booking.deleted_at.is_(None),
            )
        )

        # Upcoming shifts this week
        upcoming = await self._session.execute(
            select(func.count()).select_from(Booking).where(
                Booking.trust_id == trust_id,
                Booking.shift_date >= today,
                Booking.shift_date <= upcoming_window,
                Booking.status.in_([BookingStatus.confirmed, BookingStatus.accepted]),
                Booking.deleted_at.is_(None),
            )
        )

        # No-shows this month
        month_start = today.replace(day=1)
        no_shows = await self._session.execute(
            select(func.count()).select_from(Booking).where(
                Booking.trust_id == trust_id,
                Booking.status == BookingStatus.no_show,
                Booking.shift_date >= month_start,
                Booking.deleted_at.is_(None),
            )
        )

        return {
            "open_shifts": open_shifts.scalar_one(),
            "active_bookings": active_bookings.scalar_one(),
            "upcoming_this_week": upcoming.scalar_one(),
            "no_shows_this_month": no_shows.scalar_one(),
            "pending_timesheet_approvals": await _count_timesheets(TimesheetStatus.submitted),
            "by_status": {
                status.value: await _count(status)
                for status in [
                    BookingStatus.requested, BookingStatus.offered,
                    BookingStatus.accepted, BookingStatus.confirmed,
                    BookingStatus.checked_in, BookingStatus.completed,
                    BookingStatus.cancelled, BookingStatus.no_show,
                ]
            },
        }

    async def get_open_shifts(
        self, trust_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[Booking], int]:
        stmt = (
            select(Booking)
            .where(
                Booking.trust_id == trust_id,
                Booking.status.in_([BookingStatus.requested, BookingStatus.offered]),
                Booking.deleted_at.is_(None),
            )
            .order_by(Booking.shift_date.asc())
        )
        count_stmt = select(func.count()).select_from(Booking).where(
            Booking.trust_id == trust_id,
            Booking.status.in_([BookingStatus.requested, BookingStatus.offered]),
            Booking.deleted_at.is_(None),
        )
        total = (await self._session.execute(count_stmt)).scalar_one()
        result = await self._session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def get_pending_timesheets(
        self, trust_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[Timesheet], int]:
        stmt = (
            select(Timesheet)
            .where(
                Timesheet.trust_id == trust_id,
                Timesheet.status == TimesheetStatus.submitted,
            )
            .order_by(Timesheet.submitted_at.asc())
        )
        count_stmt = select(func.count()).select_from(Timesheet).where(
            Timesheet.trust_id == trust_id,
            Timesheet.status == TimesheetStatus.submitted,
        )
        total = (await self._session.execute(count_stmt)).scalar_one()
        result = await self._session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def get_no_shows(
        self, trust_id: UUID, *, from_date: date | None = None, to_date: date | None = None,
        offset: int = 0, limit: int = 25,
    ) -> tuple[list[Booking], int]:
        stmt = select(Booking).where(
            Booking.trust_id == trust_id,
            Booking.status == BookingStatus.no_show,
            Booking.deleted_at.is_(None),
        )
        if from_date:
            stmt = stmt.where(Booking.shift_date >= from_date)
        if to_date:
            stmt = stmt.where(Booking.shift_date <= to_date)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()
        result = await self._session.execute(stmt.order_by(Booking.shift_date.desc()).offset(offset).limit(limit))
        return list(result.scalars().all()), total

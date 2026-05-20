"""
Worker availability service.

Manages per-date availability records and standing preferences.
Conflict detection prevents double-bookings at the availability layer.
"""

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.repositories.availability import AvailabilityRepository, WorkerAvailabilityPreferencesRepository
from app.repositories.booking import BookingRepository
from app.models.availability import WorkerAvailability, WorkerAvailabilityPreferences
from app.shared.exceptions import ConflictError, NotFoundError


class AvailabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self._avail = AvailabilityRepository(session)
        self._prefs = WorkerAvailabilityPreferencesRepository(session)
        self._bookings = BookingRepository(session)

    async def set_availability(
        self,
        worker_id: UUID,
        trust_id: UUID,
        available_date: date,
        *,
        is_available: bool,
        am_available: bool = True,
        pm_available: bool = True,
        note: str | None = None,
        current_user: CurrentUser,
    ) -> WorkerAvailability:
        # Workers cannot mark themselves unavailable on dates they have confirmed bookings
        if not is_available:
            active = await self._bookings.get_active_for_worker_on_date(worker_id, available_date)
            if active:
                raise ConflictError(
                    f"Worker has an active booking on {available_date} — cannot mark unavailable."
                )

        return await self._avail.upsert(
            worker_id=worker_id,
            trust_id=trust_id,
            available_date=available_date,
            is_available=is_available,
            am_available=am_available if is_available else False,
            pm_available=pm_available if is_available else False,
            note=note,
        )

    async def bulk_set_availability(
        self,
        worker_id: UUID,
        trust_id: UUID,
        dates: list[date],
        *,
        is_available: bool,
        current_user: CurrentUser,
    ) -> list[WorkerAvailability]:
        results = []
        for d in dates:
            record = await self.set_availability(
                worker_id, trust_id, d,
                is_available=is_available,
                current_user=current_user,
            )
            results.append(record)
        return results

    async def get_availability(
        self, worker_id: UUID, *, from_date: date | None = None, to_date: date | None = None
    ) -> list[WorkerAvailability]:
        return await self._avail.list_for_worker(worker_id, from_date=from_date, to_date=to_date)

    async def set_preferences(
        self,
        worker_id: UUID,
        trust_id: UUID,
        *,
        available_days_mask: int | None = None,
        max_days_per_week: int | None = None,
        max_hours_per_week: float | None = None,
        preferred_school_ids: list[UUID] | None = None,
        preferred_role_type_ids: list[UUID] | None = None,
        radius_km: int | None = None,
        willing_to_travel: bool | None = None,
        notes: str | None = None,
        current_user: CurrentUser,
    ) -> WorkerAvailabilityPreferences:
        kwargs = {k: v for k, v in {
            "available_days_mask": available_days_mask,
            "max_days_per_week": max_days_per_week,
            "max_hours_per_week": max_hours_per_week,
            "preferred_school_ids": preferred_school_ids,
            "preferred_role_type_ids": preferred_role_type_ids,
            "radius_km": radius_km,
            "willing_to_travel": willing_to_travel,
            "notes": notes,
        }.items() if v is not None}
        return await self._prefs.upsert(worker_id, trust_id, **kwargs)

    async def get_preferences(self, worker_id: UUID) -> WorkerAvailabilityPreferences | None:
        return await self._prefs.get_for_worker(worker_id)

    def is_day_available_by_preference(self, prefs: WorkerAvailabilityPreferences, shift_date: date) -> bool:
        """Check if a shift date falls on a worker's preferred working day."""
        # date.weekday(): Mon=0 ... Sun=6  →  bitmask: Mon=1 Tue=2 Wed=4 Thu=8 Fri=16 Sat=32 Sun=64
        bit = 1 << shift_date.weekday()
        return bool(prefs.available_days_mask & bit)

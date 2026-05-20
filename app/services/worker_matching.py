"""
Worker matching service.

Finds eligible workers for a given booking based on:
  - Compliance status (must be approved)
  - Role eligibility
  - Availability (not already booked, marked available)
  - Geographic radius
  - Trust/school restrictions

Distance is calculated using the haversine formula on lat/lng columns.
No PostGIS required for V1.
"""

import math
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import WorkerAvailability, WorkerAvailabilityPreferences
from app.models.worker import WorkerProfile, WorkerRoleAssignment
from app.repositories.availability import AvailabilityRepository, WorkerAvailabilityPreferencesRepository
from app.repositories.booking import BookingRepository
from app.shared.enums import OnboardingStatus


def _haversine_km(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
    """Return great-circle distance in km between two lat/lng points."""
    R = 6371.0
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlam = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class WorkerMatchingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._bookings = BookingRepository(session)
        self._avail = AvailabilityRepository(session)
        self._prefs = WorkerAvailabilityPreferencesRepository(session)

    async def find_eligible_workers(
        self,
        role_type_id: UUID,
        trust_id: UUID,
        shift_date: date,
        school_lat: Decimal | None = None,
        school_lon: Decimal | None = None,
    ) -> list[WorkerProfile]:
        """
        Return all workers eligible for a broadcast booking.

        Eligibility criteria (all must pass):
          1. Approved onboarding status
          2. Has the required role assignment
          3. Not already booked on shift_date
          4. Per-date availability is True (or no explicit record set)
          5. Within radius (if school and worker have coordinates)
        """
        # 1+2: Approved workers with the required role
        stmt = (
            select(WorkerProfile)
            .join(WorkerRoleAssignment, WorkerRoleAssignment.worker_id == WorkerProfile.id)
            .where(
                WorkerProfile.trust_id == trust_id,
                WorkerProfile.onboarding_status == OnboardingStatus.approved,
                WorkerProfile.deleted_at.is_(None),
                WorkerRoleAssignment.role_type_id == role_type_id,
            )
        )
        result = await self._session.execute(stmt)
        candidates: list[WorkerProfile] = list(result.scalars().unique().all())

        eligible: list[WorkerProfile] = []
        for worker in candidates:
            # 3: Not already booked
            conflicts = await self._bookings.get_active_for_worker_on_date(worker.id, shift_date)
            if conflicts:
                continue

            # 4: Per-date availability check
            avail = await self._avail.get_for_worker_date(worker.id, shift_date)
            if avail and not avail.is_available:
                continue

            # 5: Radius check
            if school_lat and school_lon and worker.home_latitude and worker.home_longitude:
                distance = _haversine_km(worker.home_latitude, worker.home_longitude, school_lat, school_lon)
                worker_radius = worker.radius_km
                # Also check preferences radius if set
                prefs = await self._prefs.get_for_worker(worker.id)
                if prefs:
                    worker_radius = min(worker_radius, prefs.radius_km)
                if distance > worker_radius:
                    continue

            eligible.append(worker)

        return eligible

    async def is_worker_eligible(
        self,
        worker_id: UUID,
        role_type_id: UUID,
        shift_date: date,
        school_lat: Decimal | None = None,
        school_lon: Decimal | None = None,
    ) -> tuple[bool, str]:
        """
        Check a specific worker's eligibility. Returns (eligible, reason).
        Used for directed bookings to surface validation errors.
        """
        # Fetch worker
        result = await self._session.execute(
            select(WorkerProfile).where(
                WorkerProfile.id == worker_id,
                WorkerProfile.deleted_at.is_(None),
            )
        )
        worker = result.scalar_one_or_none()
        if not worker:
            return False, "Worker not found."

        if worker.onboarding_status != OnboardingStatus.approved:
            return False, f"Worker is not approved (status: {worker.onboarding_status.value})."

        # Role check
        role_result = await self._session.execute(
            select(WorkerRoleAssignment).where(
                WorkerRoleAssignment.worker_id == worker_id,
                WorkerRoleAssignment.role_type_id == role_type_id,
            )
        )
        if not role_result.scalar_one_or_none():
            return False, "Worker does not have the required role assignment."

        # Conflict check
        conflicts = await self._bookings.get_active_for_worker_on_date(worker_id, shift_date)
        if conflicts:
            return False, f"Worker already has a booking on {shift_date}."

        # Availability check
        avail = await self._avail.get_for_worker_date(worker_id, shift_date)
        if avail and not avail.is_available:
            return False, f"Worker has marked themselves unavailable on {shift_date}."

        return True, "Eligible."

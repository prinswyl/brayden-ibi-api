from datetime import date
from uuid import UUID

from sqlalchemy import and_, select

from app.models.booking import Booking, BookingOffer, BookingStatusHistory
from app.repositories.base import BaseRepository
from app.shared.enums import BookingOfferStatus, BookingStatus


class BookingRepository(BaseRepository[Booking]):
    model = Booking

    async def get_by_school_and_date(self, school_id: UUID, shift_date: date) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(
                Booking.school_id == school_id,
                Booking.shift_date == shift_date,
                Booking.deleted_at.is_(None),
                Booking.status.notin_([BookingStatus.cancelled, BookingStatus.rejected, BookingStatus.expired]),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_for_worker_on_date(self, worker_id: UUID, shift_date: date) -> list[Booking]:
        """Returns bookings that would conflict with a new shift on the same date."""
        stmt = (
            select(Booking)
            .where(
                Booking.worker_id == worker_id,
                Booking.shift_date == shift_date,
                Booking.deleted_at.is_(None),
                Booking.status.notin_([BookingStatus.cancelled, BookingStatus.rejected, BookingStatus.expired, BookingStatus.no_show]),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_status(self, status: BookingStatus, *, offset: int = 0, limit: int = 25) -> tuple[list[Booking], int]:
        from sqlalchemy import func
        stmt = select(Booking).where(Booking.status == status, Booking.deleted_at.is_(None))
        count_stmt = select(func.count()).select_from(Booking).where(Booking.status == status, Booking.deleted_at.is_(None))
        total = (await self.session.execute(count_stmt)).scalar_one()
        result = await self.session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def list_open_for_role(self, role_type_id: UUID) -> list[Booking]:
        stmt = (
            select(Booking)
            .where(
                Booking.role_type_id == role_type_id,
                Booking.status.in_([BookingStatus.requested, BookingStatus.offered]),
                Booking.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def write_status_history(
        self,
        booking_id: UUID,
        trust_id: UUID,
        from_status: BookingStatus | None,
        to_status: BookingStatus,
        actor_id: UUID | None,
        reason: str | None = None,
    ) -> BookingStatusHistory:
        from datetime import UTC, datetime
        entry = BookingStatusHistory(
            booking_id=booking_id,
            trust_id=trust_id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            reason=reason,
            created_at=datetime.now(UTC),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry


class BookingOfferRepository(BaseRepository[BookingOffer]):
    model = BookingOffer

    async def get_for_booking_and_worker(self, booking_id: UUID, worker_id: UUID) -> BookingOffer | None:
        stmt = select(BookingOffer).where(
            BookingOffer.booking_id == booking_id,
            BookingOffer.worker_id == worker_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_booking(self, booking_id: UUID) -> list[BookingOffer]:
        stmt = select(BookingOffer).where(BookingOffer.booking_id == booking_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_for_worker(self, worker_id: UUID) -> list[BookingOffer]:
        stmt = select(BookingOffer).where(
            BookingOffer.worker_id == worker_id,
            BookingOffer.status == BookingOfferStatus.offered,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def expire_all_for_booking(self, booking_id: UUID) -> None:
        """Mark every non-terminal offer on a booking as expired."""
        from datetime import UTC, datetime
        stmt = select(BookingOffer).where(
            BookingOffer.booking_id == booking_id,
            BookingOffer.status == BookingOfferStatus.offered,
        )
        result = await self.session.execute(stmt)
        offers = list(result.scalars().all())
        now = datetime.now(UTC)
        for offer in offers:
            offer.status = BookingOfferStatus.expired
            offer.responded_at = now
        if offers:
            await self.session.flush()

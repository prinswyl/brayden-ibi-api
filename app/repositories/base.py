"""
Generic async repository base class.

Concrete repositories inherit from BaseRepository[ModelT] and gain
standard CRUD methods for free. RLS is already active on the session
(set by get_db dependency), so all queries are automatically tenant-scoped.

Example:

    class SchoolRepository(BaseRepository[School]):
        model = School

        async def find_by_urn(self, urn: str) -> School | None:
            result = await self.session.execute(
                select(School).where(School.urn == urn, School.deleted_at.is_(None))
            )
            return result.scalar_one_or_none()
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base, SoftDeleteMixin

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, record_id: UUID) -> ModelT | None:
        stmt = select(self.model).where(self.model.id == record_id)  # type: ignore[attr-defined]
        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_or_404(self, record_id: UUID) -> ModelT:
        from app.shared.exceptions import NotFoundError

        obj = await self.get_by_id(record_id)
        if obj is None:
            raise NotFoundError(self.model.__name__, str(record_id))
        return obj

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 25,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        """Return (items, total_count) with optional equality filters."""
        stmt = select(self.model)
        count_stmt = select(func.count()).select_from(self.model)

        if issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
            count_stmt = count_stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]

        if filters:
            for column_name, value in filters.items():
                col = getattr(self.model, column_name, None)
                if col is not None and value is not None:
                    stmt = stmt.where(col == value)
                    count_stmt = count_stmt.where(col == value)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, **kwargs: Any) -> ModelT:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()  # get DB-generated id/timestamps without committing
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelT, **kwargs: Any) -> ModelT:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def soft_delete(self, obj: ModelT) -> ModelT:
        if not isinstance(obj, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} does not support soft delete.")
        obj.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
        self.session.add(obj)
        await self.session.flush()
        return obj

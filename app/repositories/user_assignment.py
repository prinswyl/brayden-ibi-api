from uuid import UUID

from sqlalchemy import select

from app.models.user_assignment import UserSchoolAssignment
from app.repositories.base import BaseRepository


class UserSchoolAssignmentRepository(BaseRepository[UserSchoolAssignment]):
    model = UserSchoolAssignment

    async def get_for_user(self, user_id: UUID) -> list[UserSchoolAssignment]:
        result = await self.session.execute(
            select(UserSchoolAssignment).where(
                UserSchoolAssignment.user_id == user_id,
                UserSchoolAssignment.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def get_for_user_at_school(
        self, user_id: UUID, school_id: UUID | None, role: str
    ) -> UserSchoolAssignment | None:
        stmt = select(UserSchoolAssignment).where(
            UserSchoolAssignment.user_id == user_id,
            UserSchoolAssignment.role == role,
        )
        if school_id is None:
            stmt = stmt.where(UserSchoolAssignment.school_id.is_(None))
        else:
            stmt = stmt.where(UserSchoolAssignment.school_id == school_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_school(
        self, school_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[UserSchoolAssignment], int]:
        from sqlalchemy import func

        base_where = [
            UserSchoolAssignment.school_id == school_id,
            UserSchoolAssignment.is_active == True,  # noqa: E712
        ]
        count = (
            await self.session.execute(
                select(func.count())
                .select_from(UserSchoolAssignment)
                .where(*base_where)
            )
        ).scalar_one()
        result = await self.session.execute(
            select(UserSchoolAssignment).where(*base_where).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), count

    async def list_for_trust(
        self, trust_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[UserSchoolAssignment], int]:
        from sqlalchemy import func

        base_where = [
            UserSchoolAssignment.trust_id == trust_id,
            UserSchoolAssignment.is_active == True,  # noqa: E712
        ]
        count = (
            await self.session.execute(
                select(func.count())
                .select_from(UserSchoolAssignment)
                .where(*base_where)
            )
        ).scalar_one()
        result = await self.session.execute(
            select(UserSchoolAssignment).where(*base_where).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), count

    async def deactivate(self, assignment: UserSchoolAssignment) -> UserSchoolAssignment:
        return await self.update(assignment, is_active=False)

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.models.user import User
from app.repositories.base import BaseRepository
from app.shared.enums import UserStatus


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_for_trust(
        self, trust_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> tuple[list[User], int]:
        # Import here to avoid circular import at module load time
        from app.models.worker import WorkerProfile
        from sqlalchemy import exists

        # Exclude workers — a User with a WorkerProfile row is a casual bank worker,
        # not an internal staff member. Internal staff are invited via /users/invite.
        not_a_worker = ~exists().where(WorkerProfile.user_id == User.id)

        base_where = (
            User.trust_id == trust_id,
            User.deleted_at.is_(None),
            not_a_worker,
        )
        count = (await self.session.execute(
            select(func.count()).select_from(User).where(*base_where)
        )).scalar_one()
        result = await self.session.execute(
            select(User).where(*base_where).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), count

    async def activate(self, user: User) -> User:
        if user.status == UserStatus.invited:
            return await self.update(user, status=UserStatus.active)
        return user

    async def deactivate(self, user: User) -> User:
        return await self.update(user, status=UserStatus.suspended)

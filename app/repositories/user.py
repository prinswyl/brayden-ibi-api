from uuid import UUID

from sqlalchemy import select

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
        from sqlalchemy import func
        stmt = select(User).where(User.trust_id == trust_id, User.deleted_at.is_(None))
        count = (await self.session.execute(
            select(func.count()).select_from(User).where(User.trust_id == trust_id, User.deleted_at.is_(None))
        )).scalar_one()
        result = await self.session.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all()), count

    async def deactivate(self, user: User) -> User:
        return await self.update(user, status=UserStatus.suspended)

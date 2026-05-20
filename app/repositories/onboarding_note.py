from uuid import UUID

from sqlalchemy import select

from app.models.compliance import OnboardingNote
from app.repositories.base import BaseRepository
from app.shared.enums import NoteVisibility


class OnboardingNoteRepository(BaseRepository[OnboardingNote]):
    model = OnboardingNote

    async def list_for_worker(
        self,
        worker_id: UUID,
        *,
        visibility: NoteVisibility | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[OnboardingNote]:
        stmt = (
            select(OnboardingNote)
            .where(OnboardingNote.worker_id == worker_id)
            .order_by(OnboardingNote.created_at.desc())
        )
        if visibility is not None:
            stmt = stmt.where(OnboardingNote.visibility == visibility.value)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

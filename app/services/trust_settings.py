"""Trust settings service — manages DBS portal config, policy documents, and DSL details per trust."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scr import TrustSettings


class TrustSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, trust_id: UUID) -> TrustSettings | None:
        result = await self._session.execute(
            select(TrustSettings).where(TrustSettings.trust_id == trust_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, trust_id: UUID, **fields) -> TrustSettings:
        settings = await self.get(trust_id)
        if settings is None:
            settings = TrustSettings(trust_id=trust_id)
            self._session.add(settings)
        for key, value in fields.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        await self._session.flush()
        return settings

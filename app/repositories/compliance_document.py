from datetime import date
from uuid import UUID

from sqlalchemy import and_, select

from app.models.compliance import ComplianceDocument
from app.repositories.base import BaseRepository
from app.shared.enums import DocumentStatus, DocumentType


class ComplianceDocumentRepository(BaseRepository[ComplianceDocument]):
    model = ComplianceDocument

    async def list_for_worker(
        self,
        worker_id: UUID,
        *,
        include_superseded: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ComplianceDocument], int]:
        filters: dict = {"worker_id": str(worker_id)}
        if not include_superseded:
            # Handled in list_all via filters — superseded needs a custom clause
            items, total = await self.list_all(offset=offset, limit=limit, filters=filters)
            active = [d for d in items if d.status != DocumentStatus.superseded]
            return active, len(active)
        return await self.list_all(offset=offset, limit=limit, filters=filters)

    async def list_by_status(
        self,
        status: DocumentStatus,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[ComplianceDocument], int]:
        return await self.list_all(
            offset=offset, limit=limit, filters={"status": status.value}
        )

    async def get_latest_by_type(
        self, worker_id: UUID, document_type: DocumentType
    ) -> ComplianceDocument | None:
        result = await self.session.execute(
            select(ComplianceDocument)
            .where(
                ComplianceDocument.worker_id == worker_id,
                ComplianceDocument.document_type == document_type.value,
                ComplianceDocument.deleted_at.is_(None),
                ComplianceDocument.status != DocumentStatus.superseded.value,
            )
            .order_by(ComplianceDocument.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_expiring_before(
        self, cutoff_date: date, *, offset: int = 0, limit: int = 100
    ) -> tuple[list[ComplianceDocument], int]:
        from sqlalchemy import func

        stmt = (
            select(ComplianceDocument)
            .where(
                ComplianceDocument.expiry_date <= cutoff_date,
                ComplianceDocument.expiry_date.is_not(None),
                ComplianceDocument.status == DocumentStatus.approved.value,
                ComplianceDocument.deleted_at.is_(None),
            )
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(ComplianceDocument)
            .where(
                ComplianceDocument.expiry_date <= cutoff_date,
                ComplianceDocument.expiry_date.is_not(None),
                ComplianceDocument.status == DocumentStatus.approved.value,
                ComplianceDocument.deleted_at.is_(None),
            )
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

"""
Audit log writer service.

All writes to the audit_logs table go through this module.
The table is append-only: no UPDATE or DELETE is ever issued against it.

Usage:

    await audit.log(
        session=db,
        actor=current_user,
        action=AuditAction.approve,
        resource_type="compliance_documents",
        resource_id=document_id,
        new_values={"status": "approved"},
    )
"""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.enums import AuditAction

logger = structlog.get_logger(__name__)


async def log(
    session: AsyncSession,
    *,
    action: AuditAction,
    resource_type: str,
    trust_id: UUID | None = None,
    user_id: UUID | None = None,
    resource_id: UUID | None = None,
    school_id: UUID | None = None,
    worker_id: UUID | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session_id: str | None = None,
) -> None:
    """
    Insert an immutable audit log record.

    This uses a raw INSERT rather than the ORM to guarantee the audit row
    is written regardless of the ORM session's unit-of-work state, and to
    make it absolutely explicit that no UPDATE path exists.
    """
    import json

    def _json(v: dict | None) -> str | None:
        return json.dumps(v) if v is not None else None

    stmt = text("""
        INSERT INTO audit_logs (
            trust_id, user_id, action, resource_type, resource_id,
            school_id, worker_id, old_values, new_values,
            metadata, ip_address, user_agent, session_id, created_at
        ) VALUES (
            :trust_id, :user_id, :action, :resource_type, :resource_id,
            :school_id, :worker_id, CAST(:old_values AS jsonb), CAST(:new_values AS jsonb),
            CAST(:metadata AS jsonb), CAST(:ip_address AS inet), :user_agent, :session_id, now()
        )
    """)

    await session.execute(
        stmt,
        {
            "trust_id": str(trust_id) if trust_id else None,
            "user_id": str(user_id) if user_id else None,
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "school_id": str(school_id) if school_id else None,
            "worker_id": str(worker_id) if worker_id else None,
            "old_values": _json(old_values),
            "new_values": _json(new_values),
            "metadata": _json(metadata),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
        },
    )

    logger.debug(
        "audit_event",
        action=action.value,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        user_id=str(user_id) if user_id else None,
        trust_id=str(trust_id) if trust_id else None,
    )

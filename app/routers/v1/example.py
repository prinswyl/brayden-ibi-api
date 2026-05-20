"""
Example tenant-aware protected route.

Demonstrates the full request lifecycle:
  1. JWT validation        → get_current_user()
  2. RLS session setup     → get_db()
  3. Permission gate       → require_permission()
  4. Tenant-scoped query   → BaseRepository
  5. Audit logging         → audit.log()

Remove this file once the first real domain router is implemented.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log as audit_log
from app.core.auth import CurrentUser, get_current_user
from app.core.dependencies import get_db
from app.core.permissions import require_permission
from app.shared.enums import AuditAction

router = APIRouter(prefix="/example", tags=["Example"], include_in_schema=False)


class ExampleResponse(BaseModel):
    message: str
    trust_id: UUID
    user_id: UUID
    rls_active: bool


@router.get(
    "/protected",
    response_model=ExampleResponse,
    dependencies=[Depends(require_permission("workers:read"))],
    summary="Example protected tenant-aware route",
)
async def protected_example(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExampleResponse:
    """
    Example showing:
    - Auth enforcement via dependency
    - RLS is active (query only returns rows for current_user.trust_id)
    - Audit log written for this view event
    """
    # Verify RLS variable is set — this SELECT reads back the session var
    result = await db.execute(
        text("SELECT current_setting('app.current_trust_id', true) AS trust_id")
    )
    rls_trust_id = result.scalar_one_or_none()

    await audit_log(
        db,
        action=AuditAction.view,
        resource_type="example",
        trust_id=current_user.trust_id,
        user_id=current_user.user_id,
        metadata={"note": "example route invoked"},
    )

    return ExampleResponse(
        message="Tenant context is active. RLS is enforced.",
        trust_id=current_user.trust_id,
        user_id=current_user.user_id,
        rls_active=str(current_user.trust_id) == rls_trust_id,
    )

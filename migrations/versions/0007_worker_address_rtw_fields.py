"""Add full address and RTW document fields to worker_profiles

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Full home address (previously only postcode was stored)
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS home_address TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS home_city TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS home_county TEXT")

    # Right-to-work document details (self-declared by worker during onboarding)
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS rtw_doc_type TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS rtw_doc_number TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS rtw_passport_number TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS rtw_passport_issue_date DATE")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS rtw_passport_expiry_date DATE")

    # Storage paths for worker-uploaded compliance documents
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS rtw_document_storage_path TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS qualification_storage_paths JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS qualification_storage_paths")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS rtw_document_storage_path")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS rtw_passport_expiry_date")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS rtw_passport_issue_date")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS rtw_passport_number")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS rtw_doc_number")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS rtw_doc_type")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS home_county")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS home_city")
    op.execute("ALTER TABLE worker_profiles DROP COLUMN IF EXISTS home_address")

"""Add bank_name and bank_account_name to worker_profiles

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "worker_profiles",
        sa.Column("bank_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "worker_profiles",
        sa.Column("bank_account_name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("worker_profiles", "bank_account_name")
    op.drop_column("worker_profiles", "bank_name")

"""Add barred_list_not_applicable and tra_not_applicable to scr_records

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scr_records",
        sa.Column(
            "barred_list_not_applicable",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "scr_records",
        sa.Column(
            "tra_not_applicable",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("scr_records", "tra_not_applicable")
    op.drop_column("scr_records", "barred_list_not_applicable")

"""Add casual_worker_agreement_html to trust_settings

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trust_settings",
        sa.Column("casual_worker_agreement_html", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trust_settings", "casual_worker_agreement_html")

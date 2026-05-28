"""Add dbs_risk_assessment_not_applicable flag to scr_records

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scr_records",
        sa.Column("dbs_risk_assessment_not_applicable", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("scr_records", "dbs_risk_assessment_not_applicable")

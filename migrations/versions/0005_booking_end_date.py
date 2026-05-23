"""Add end_date to bookings for multi-day block bookings

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS guards against re-running on a DB that already has the column
    op.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS end_date DATE")
    op.execute("UPDATE bookings SET end_date = shift_date WHERE end_date IS NULL")


def downgrade() -> None:
    op.drop_column("bookings", "end_date")

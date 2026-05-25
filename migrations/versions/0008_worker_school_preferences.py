"""Add worker school preferences table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS worker_school_preferences (
            id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            worker_id   UUID         NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            trust_id    UUID         NOT NULL REFERENCES trusts(id),
            school_id   UUID         NOT NULL REFERENCES schools(id),
            rank        INTEGER      NOT NULL CHECK (rank BETWEEN 1 AND 5),
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            UNIQUE (worker_id, rank),
            UNIQUE (worker_id, school_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_wsp_worker ON worker_school_preferences(worker_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS worker_school_preferences")

"""Full SCR field set — title, employment start, qualifications, DBS risk, Section 128, overseas evidence

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users — honorific title
    op.add_column("users", sa.Column("title", sa.Text(), nullable=True))

    # worker_profiles — HR-set employment date + worker-declared qualifications
    op.add_column("worker_profiles", sa.Column("employment_start_date", sa.Date(), nullable=True))
    op.add_column("worker_profiles", sa.Column("qualification_type", sa.Text(), nullable=True))
    op.add_column("worker_profiles", sa.Column("qualification_date", sa.Date(), nullable=True))

    # scr_records — DBS risk assessment, barred list inclusion flag, Section 128, overseas evidence
    op.add_column("scr_records", sa.Column("dbs_risk_assessment_date", sa.Date(), nullable=True))
    op.add_column("scr_records", sa.Column("dbs_barred_list_included", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("scr_records", sa.Column("section_128_checked_date", sa.Date(), nullable=True))
    op.add_column("scr_records", sa.Column("section_128_checked_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("scr_records", sa.Column("section_128_not_applicable", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("scr_records", sa.Column("overseas_check_evidence", sa.Text(), nullable=True))

    # FK for section_128_checked_by
    op.create_foreign_key(
        "fk_scr_section128_checked_by",
        "scr_records", "users",
        ["section_128_checked_by"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_scr_section128_checked_by", "scr_records", type_="foreignkey")
    op.drop_column("scr_records", "overseas_check_evidence")
    op.drop_column("scr_records", "section_128_not_applicable")
    op.drop_column("scr_records", "section_128_checked_by")
    op.drop_column("scr_records", "section_128_checked_date")
    op.drop_column("scr_records", "dbs_barred_list_included")
    op.drop_column("scr_records", "dbs_risk_assessment_date")
    op.drop_column("worker_profiles", "qualification_date")
    op.drop_column("worker_profiles", "qualification_type")
    op.drop_column("worker_profiles", "employment_start_date")
    op.drop_column("users", "title")

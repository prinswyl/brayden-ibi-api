"""Compliance Vault V1 — separate onboarding lifecycle from compliance processing states

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Step 1: drop the old onboarding_status history table (no data yet) ────
    # We'll recreate it as compliance_stage_history with the new enum.
    op.execute("DROP TABLE IF EXISTS onboarding_status")

    # ── Step 2: new human-facing onboarding lifecycle enum ────────────────────
    op.execute("""
        CREATE TYPE onboarding_status AS ENUM (
            'draft',
            'submitted',
            'under_review',
            'approved',
            'rejected',
            'suspended',
            'expired'
        )
    """)

    # ── Step 3: new internal compliance processing stage enum ─────────────────
    op.execute("""
        CREATE TYPE compliance_stage AS ENUM (
            'not_started',
            'awaiting_documents',
            'documents_received',
            'dbs_check_pending',
            'rtw_check_pending',
            'under_review',
            'clearance_granted',
            'clearance_denied',
            'recheck_required'
        )
    """)

    # ── Step 4: add 'superseded' to document_status enum ─────────────────────
    # ALTER TYPE ADD VALUE cannot be executed inside a transaction in PG < 12.
    # Supabase runs PG 15+ so this is safe. The new value is not used within
    # this same transaction, which is the only restriction.
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'superseded' AFTER 'expired'")

    # ── Step 5: alter worker_profiles ─────────────────────────────────────────
    # Drop the overloaded onboarding_stage column; replace with two focused columns.
    op.execute("ALTER TABLE worker_profiles DROP COLUMN onboarding_stage")

    op.execute("""
        ALTER TABLE worker_profiles
            ADD COLUMN onboarding_status   onboarding_status   NOT NULL DEFAULT 'draft',
            ADD COLUMN compliance_stage    compliance_stage    NOT NULL DEFAULT 'not_started',
            ADD COLUMN is_amber            BOOLEAN             NOT NULL DEFAULT false,
            ADD COLUMN suspended_at        TIMESTAMPTZ,
            ADD COLUMN suspension_reason   TEXT,
            ADD COLUMN suspended_by_id     UUID REFERENCES users(id),
            ADD COLUMN compliance_expires_at TIMESTAMPTZ
    """)

    # ── Step 6: drop the now-unused old enum ─────────────────────────────────
    op.execute("DROP TYPE onboarding_stage")

    # ── Step 7: compliance_documents — add versioning support ─────────────────
    op.execute("""
        ALTER TABLE compliance_documents
            ADD COLUMN version_number  INT  NOT NULL DEFAULT 1,
            ADD COLUMN supersedes_id   UUID REFERENCES compliance_documents(id)
    """)

    # ── Step 8: create compliance_stage_history ───────────────────────────────
    # Records every compliance_stage transition for audit / processing visibility.
    op.execute("""
        CREATE TABLE compliance_stage_history (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id        UUID         NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id       UUID         NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            stage           compliance_stage NOT NULL,
            stage_entered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            stage_completed_at TIMESTAMPTZ,
            completed_by    UUID         REFERENCES users(id),
            notes           TEXT,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)

    # ── Step 9: create onboarding_notes ──────────────────────────────────────
    # Human-readable notes on the onboarding lifecycle: status changes, HR
    # comments, re-upload requests, and manual annotations.
    op.execute("""
        CREATE TABLE onboarding_notes (
            id               UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id         UUID             NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id        UUID             NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            author_id        UUID             NOT NULL REFERENCES users(id),
            note_type        TEXT             NOT NULL DEFAULT 'manual',
            content          TEXT             NOT NULL,
            visibility       TEXT             NOT NULL DEFAULT 'internal',
            previous_status  onboarding_status,
            new_status       onboarding_status,
            created_at       TIMESTAMPTZ      NOT NULL DEFAULT now()
        )
    """)

    # ── Step 10: create first_shift_verifications ─────────────────────────────
    # Physical DBS verification performed by a receptionist/admin on the
    # worker's first shift at a given school. Once set, it is permanent.
    op.execute("""
        CREATE TABLE first_shift_verifications (
            id                  UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id            UUID    NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id           UUID    NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            school_id           UUID    NOT NULL REFERENCES schools(id) ON DELETE RESTRICT,
            verified_by_id      UUID    NOT NULL REFERENCES users(id),
            verification_date   DATE    NOT NULL DEFAULT CURRENT_DATE,
            dbs_seen_and_matched BOOLEAN NOT NULL DEFAULT false,
            notes               TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (worker_id, school_id)
        )
    """)

    # ── Step 11: indexes ──────────────────────────────────────────────────────
    op.execute("CREATE INDEX ix_wp_onboarding_status ON worker_profiles (trust_id, onboarding_status)")
    op.execute("CREATE INDEX ix_wp_compliance_stage ON worker_profiles (trust_id, compliance_stage)")
    op.execute("CREATE INDEX ix_wp_is_amber ON worker_profiles (trust_id, is_amber) WHERE is_amber = true")
    op.execute("""
        CREATE INDEX ix_wp_compliance_expires
        ON worker_profiles (trust_id, compliance_expires_at)
        WHERE compliance_expires_at IS NOT NULL
    """)
    op.execute("CREATE INDEX ix_compliance_docs_worker ON compliance_documents (trust_id, worker_id, status)")
    op.execute("CREATE INDEX ix_compliance_docs_expiry ON compliance_documents (trust_id, expiry_date) WHERE expiry_date IS NOT NULL AND deleted_at IS NULL")
    op.execute("CREATE INDEX ix_onboarding_notes_worker ON onboarding_notes (trust_id, worker_id, created_at DESC)")
    op.execute("CREATE INDEX ix_first_shift_worker ON first_shift_verifications (trust_id, worker_id)")
    op.execute("CREATE INDEX ix_first_shift_school ON first_shift_verifications (trust_id, school_id)")
    op.execute("CREATE INDEX ix_compliance_stage_history_worker ON compliance_stage_history (trust_id, worker_id)")

    # ── Step 12: RLS on new tables ────────────────────────────────────────────
    for table in ("compliance_stage_history", "onboarding_notes", "first_shift_verifications"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (trust_id::text = current_setting('app.current_trust_id', true))
        """)
        op.execute(f"""
            CREATE POLICY superadmin_bypass ON {table}
            AS PERMISSIVE FOR ALL TO PUBLIC
            USING (current_setting('app.is_superadmin', true) = 'true')
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS first_shift_verifications")
    op.execute("DROP TABLE IF EXISTS onboarding_notes")
    op.execute("DROP TABLE IF EXISTS compliance_stage_history")

    op.execute("""
        ALTER TABLE compliance_documents
            DROP COLUMN IF EXISTS version_number,
            DROP COLUMN IF EXISTS supersedes_id
    """)

    op.execute("""
        ALTER TABLE worker_profiles
            DROP COLUMN IF EXISTS onboarding_status,
            DROP COLUMN IF EXISTS compliance_stage,
            DROP COLUMN IF EXISTS is_amber,
            DROP COLUMN IF EXISTS suspended_at,
            DROP COLUMN IF EXISTS suspension_reason,
            DROP COLUMN IF EXISTS suspended_by_id,
            DROP COLUMN IF EXISTS compliance_expires_at
    """)

    # Restore the original column and type
    op.execute("""
        CREATE TYPE onboarding_stage AS ENUM (
            'registered', 'documents_submitted', 'dbs_pending',
            'rtw_pending', 'compliance_review', 'approved', 'rejected', 'suspended'
        )
    """)
    op.execute("ALTER TABLE worker_profiles ADD COLUMN onboarding_stage onboarding_stage NOT NULL DEFAULT 'registered'")

    op.execute("DROP TYPE IF EXISTS compliance_stage")
    op.execute("DROP TYPE IF EXISTS onboarding_status")

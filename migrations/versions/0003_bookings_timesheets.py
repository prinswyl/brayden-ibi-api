"""Bookings & Timesheets domain — schema expansion

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New enums ─────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE dispatch_mode AS ENUM ('directed', 'broadcast')")
    op.execute("CREATE TYPE booking_offer_status AS ENUM ('offered', 'accepted', 'declined', 'expired', 'withdrawn')")
    op.execute("CREATE TYPE urgency_level AS ENUM ('standard', 'urgent', 'emergency')")

    # Extend existing enums (ADD VALUE IF NOT EXISTS is safe and non-transactional)
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'checked_in'")
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'rejected'")
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'expired'")
    op.execute("ALTER TYPE timesheet_status ADD VALUE IF NOT EXISTS 'correction_requested'")

    # ── Extend schools — geographic coordinates ───────────────────────────────
    op.execute("ALTER TABLE schools ADD COLUMN IF NOT EXISTS latitude NUMERIC(9,6)")
    op.execute("ALTER TABLE schools ADD COLUMN IF NOT EXISTS longitude NUMERIC(9,6)")

    # ── Extend worker_profiles — home location + radius ──────────────────────
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS home_postcode TEXT")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS home_latitude NUMERIC(9,6)")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS home_longitude NUMERIC(9,6)")
    op.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS radius_km INTEGER NOT NULL DEFAULT 25")

    # ── Extend bookings ───────────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE bookings
            ADD COLUMN IF NOT EXISTS dispatch_mode dispatch_mode NOT NULL DEFAULT 'broadcast',
            ADD COLUMN IF NOT EXISTS urgency urgency_level NOT NULL DEFAULT 'standard',
            ADD COLUMN IF NOT EXISTS agreed_hourly_rate NUMERIC(8,4),
            ADD COLUMN IF NOT EXISTS offer_expires_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS checked_in_by UUID REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS check_out_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS no_show_reason TEXT,
            ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
            ADD COLUMN IF NOT EXISTS expired_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS school_confirmed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS school_confirmed_by UUID REFERENCES users(id)
    """)

    # ── Extend timesheets ─────────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE timesheets
            ADD COLUMN IF NOT EXISTS worker_notes TEXT,
            ADD COLUMN IF NOT EXISTS overtime_hours NUMERIC(5,2) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS correction_requested_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS correction_requested_by UUID REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ
    """)

    # ── New table: booking_offers ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE booking_offers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            status booking_offer_status NOT NULL DEFAULT 'offered',
            offered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            responded_at TIMESTAMPTZ,
            decline_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (booking_id, worker_id)
        )
    """)
    # Enforce: only one accepted offer per booking (first-accept-wins guarantee)
    op.execute("""
        CREATE UNIQUE INDEX idx_booking_offers_one_accepted
        ON booking_offers(booking_id)
        WHERE status = 'accepted'
    """)

    # ── New table: booking_status_history ─────────────────────────────────────
    op.execute("""
        CREATE TABLE booking_status_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
            from_status booking_status,
            to_status booking_status NOT NULL,
            actor_id UUID REFERENCES users(id),
            reason TEXT,
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ── New table: worker_availability_preferences ────────────────────────────
    op.execute("""
        CREATE TABLE worker_availability_preferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            available_days_mask INTEGER NOT NULL DEFAULT 31,
            max_days_per_week INTEGER,
            max_hours_per_week NUMERIC(5,2),
            preferred_school_ids UUID[] NOT NULL DEFAULT '{}',
            preferred_role_type_ids UUID[] NOT NULL DEFAULT '{}',
            radius_km INTEGER NOT NULL DEFAULT 25,
            willing_to_travel BOOLEAN NOT NULL DEFAULT true,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (worker_id)
        )
    """)

    # ── New table: timesheet_corrections ─────────────────────────────────────
    op.execute("""
        CREATE TABLE timesheet_corrections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            timesheet_id UUID NOT NULL REFERENCES timesheets(id) ON DELETE CASCADE,
            requested_by UUID NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            old_values JSONB,
            resolved_at TIMESTAMPTZ,
            resolved_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.execute("CREATE INDEX idx_booking_offers_booking ON booking_offers(booking_id)")
    op.execute("CREATE INDEX idx_booking_offers_worker_status ON booking_offers(worker_id, status)")
    op.execute("CREATE INDEX idx_booking_offers_expires ON booking_offers(expires_at) WHERE status = 'offered'")
    op.execute("CREATE INDEX idx_booking_status_history_booking ON booking_status_history(booking_id, created_at)")
    op.execute("CREATE INDEX idx_worker_avail_prefs_worker ON worker_availability_preferences(worker_id)")
    op.execute("CREATE INDEX idx_timesheet_corrections_timesheet ON timesheet_corrections(timesheet_id)")
    op.execute("CREATE INDEX idx_bookings_dispatch ON bookings(trust_id, dispatch_mode, status)")
    op.execute("CREATE INDEX idx_bookings_offer_expires ON bookings(offer_expires_at) WHERE status = 'offered'")
    op.execute("CREATE INDEX idx_schools_location ON schools(latitude, longitude) WHERE latitude IS NOT NULL")

    # ── RLS for new tables ────────────────────────────────────────────────────
    new_tables = [
        "booking_offers",
        "booking_status_history",
        "worker_availability_preferences",
        "timesheet_corrections",
    ]
    for table in new_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (trust_id = current_setting('app.current_trust_id', true)::uuid)
        """)
        op.execute(f"""
            CREATE POLICY superadmin_bypass ON {table}
            USING (current_setting('app.is_superadmin', true) = 'true')
        """)


def downgrade() -> None:
    for table in [
        "timesheet_corrections",
        "worker_availability_preferences",
        "booking_status_history",
        "booking_offers",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    for col_spec in [
        ("timesheets", "worker_notes"),
        ("timesheets", "overtime_hours"),
        ("timesheets", "correction_requested_at"),
        ("timesheets", "correction_requested_by"),
        ("timesheets", "locked_at"),
        ("bookings", "dispatch_mode"),
        ("bookings", "urgency"),
        ("bookings", "agreed_hourly_rate"),
        ("bookings", "offer_expires_at"),
        ("bookings", "checked_in_at"),
        ("bookings", "checked_in_by"),
        ("bookings", "check_out_at"),
        ("bookings", "completed_at"),
        ("bookings", "no_show_reason"),
        ("bookings", "rejected_at"),
        ("bookings", "rejected_by"),
        ("bookings", "rejection_reason"),
        ("bookings", "expired_at"),
        ("bookings", "school_confirmed_at"),
        ("bookings", "school_confirmed_by"),
        ("worker_profiles", "home_postcode"),
        ("worker_profiles", "home_latitude"),
        ("worker_profiles", "home_longitude"),
        ("worker_profiles", "radius_km"),
        ("schools", "latitude"),
        ("schools", "longitude"),
    ]:
        op.execute(f"ALTER TABLE {col_spec[0]} DROP COLUMN IF EXISTS {col_spec[1]}")

    op.execute("DROP TYPE IF EXISTS urgency_level")
    op.execute("DROP TYPE IF EXISTS booking_offer_status")
    op.execute("DROP TYPE IF EXISTS dispatch_mode")

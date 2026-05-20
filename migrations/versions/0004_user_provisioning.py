"""User provisioning — school assignments and custom claims update

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── user_school_assignments ───────────────────────────────────────────────
    # Links a user to one or more schools with a specific role at each school.
    # Trust-wide roles (trust_admin, payroll_officer, hr_manager) have school_id = NULL.
    # School-scoped roles (cover_supervisor, receptionist) must have a school_id.
    op.execute("""
        CREATE TABLE user_school_assignments (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id    UUID NOT NULL REFERENCES trusts(id),
            user_id     UUID NOT NULL REFERENCES users(id),
            school_id   UUID REFERENCES schools(id),
            role        TEXT NOT NULL,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            assigned_by UUID REFERENCES users(id),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- A user can only hold a given role at a given school once
            CONSTRAINT uq_user_school_role UNIQUE (user_id, school_id, role)
        )
    """)

    op.execute("CREATE INDEX idx_user_school_assignments_trust  ON user_school_assignments(trust_id)")
    op.execute("CREATE INDEX idx_user_school_assignments_user   ON user_school_assignments(user_id)")
    op.execute("CREATE INDEX idx_user_school_assignments_school ON user_school_assignments(school_id) WHERE school_id IS NOT NULL")

    # ── RLS ──────────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE user_school_assignments ENABLE ROW LEVEL SECURITY")

    # Trust admins manage all assignments in their trust
    op.execute("""
        CREATE POLICY user_school_assignments_trust_isolation
        ON user_school_assignments
        USING (trust_id = current_setting('app.current_trust_id', true)::uuid)
    """)

    # ── Updated Supabase custom claims hook ───────────────────────────────────
    # This PostgreSQL function is called by Supabase on every token refresh.
    # It injects trust_id, roles, and school_ids into app_metadata so the JWT
    # contains the full user context without extra DB calls on each request.
    op.execute("""
        CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
        RETURNS jsonb
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
            claims        jsonb;
            user_id       uuid;
            v_trust_id    uuid;
            v_roles       text[];
            v_school_ids  uuid[];
        BEGIN
            user_id := (event->>'user_id')::uuid;
            claims  := event->'claims';

            -- Look up the user's trust and roles from user_school_assignments
            SELECT
                u.trust_id,
                ARRAY_AGG(DISTINCT a.role ORDER BY a.role)   AS roles,
                ARRAY_AGG(DISTINCT a.school_id)               AS school_ids
            INTO v_trust_id, v_roles, v_school_ids
            FROM users u
            LEFT JOIN user_school_assignments a
                   ON a.user_id = u.id AND a.is_active = true
            WHERE u.id = user_id
            GROUP BY u.trust_id;

            -- Fallback: user exists in users table but has no assignments yet
            IF v_trust_id IS NULL THEN
                SELECT trust_id INTO v_trust_id FROM users WHERE id = user_id;
            END IF;

            -- Remove NULL from school_ids array (trust-wide roles have school_id = NULL)
            v_school_ids := ARRAY_REMOVE(v_school_ids, NULL);

            claims := jsonb_set(claims, '{trust_id}',    to_jsonb(v_trust_id::text));
            claims := jsonb_set(claims, '{app_metadata}', COALESCE(claims->'app_metadata', '{}'::jsonb)
                || jsonb_build_object(
                    'trust_id',   v_trust_id::text,
                    'roles',      COALESCE(to_jsonb(v_roles), '[]'::jsonb),
                    'school_ids', COALESCE(to_jsonb(v_school_ids), '[]'::jsonb)
                )
            );

            RETURN jsonb_set(event, '{claims}', claims);
        END;
        $$;
    """)

    op.execute("""
        GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_school_assignments CASCADE")
    op.execute("DROP FUNCTION IF EXISTS public.custom_access_token_hook CASCADE")

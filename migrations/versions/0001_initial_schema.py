"""Initial schema — full Brayden IBI PostgreSQL schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE trust_status AS ENUM ('active', 'suspended', 'trial', 'offboarded')")
    op.execute("CREATE TYPE user_status AS ENUM ('invited', 'active', 'suspended', 'deleted')")
    op.execute("CREATE TYPE onboarding_stage AS ENUM ('registered', 'documents_submitted', 'dbs_pending', 'rtw_pending', 'compliance_review', 'approved', 'rejected', 'suspended')")
    op.execute("CREATE TYPE document_type AS ENUM ('dbs_certificate', 'right_to_work', 'proof_of_identity', 'teaching_certificate', 'reference', 'medical_clearance', 'other')")
    op.execute("CREATE TYPE document_status AS ENUM ('pending_upload', 'uploaded', 'under_review', 'approved', 'rejected', 'expired')")
    op.execute("CREATE TYPE dbs_level AS ENUM ('basic', 'standard', 'enhanced', 'enhanced_barred')")
    op.execute("CREATE TYPE dbs_status AS ENUM ('not_started', 'applied', 'pending', 'clear', 'flagged', 'expired')")
    op.execute("CREATE TYPE rtw_document_type AS ENUM ('uk_passport', 'biometric_residence_permit', 'share_code', 'eu_settlement', 'other')")
    op.execute("CREATE TYPE booking_status AS ENUM ('requested', 'offered', 'accepted', 'confirmed', 'completed', 'cancelled', 'no_show')")
    op.execute("CREATE TYPE timesheet_status AS ENUM ('draft', 'submitted', 'approved', 'rejected', 'exported')")
    op.execute("CREATE TYPE pay_frequency AS ENUM ('weekly', 'fortnightly', 'monthly')")
    op.execute("CREATE TYPE audit_action AS ENUM ('create', 'update', 'delete', 'approve', 'reject', 'login', 'logout', 'export', 'view', 'upload')")

    # ── Core Tenant Layer ─────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE trusts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            urn TEXT UNIQUE,
            companies_house_no TEXT,
            status trust_status NOT NULL DEFAULT 'trial',
            trial_ends_at TIMESTAMPTZ,
            subscription_tier TEXT NOT NULL DEFAULT 'starter',
            contact_email TEXT NOT NULL,
            contact_phone TEXT,
            address_line_1 TEXT,
            address_line_2 TEXT,
            city TEXT,
            postcode TEXT,
            country TEXT NOT NULL DEFAULT 'GB',
            settings JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE trust_branding (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL UNIQUE REFERENCES trusts(id) ON DELETE CASCADE,
            primary_color TEXT NOT NULL DEFAULT '#1a56db',
            secondary_color TEXT NOT NULL DEFAULT '#e1effe',
            logo_storage_path TEXT,
            favicon_storage_path TEXT,
            portal_title TEXT,
            custom_domain TEXT UNIQUE,
            email_from_name TEXT,
            email_reply_to TEXT,
            footer_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE schools (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            name TEXT NOT NULL,
            urn TEXT,
            phase TEXT,
            address_line_1 TEXT,
            address_line_2 TEXT,
            city TEXT,
            postcode TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            settings JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
    """)

    # ── Identity Layer ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            email TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT,
            status user_status NOT NULL DEFAULT 'invited',
            avatar_storage_path TEXT,
            last_login_at TIMESTAMPTZ,
            invited_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            UNIQUE (trust_id, email)
        )
    """)

    op.execute("""
        CREATE TABLE roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID REFERENCES trusts(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            is_system BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (trust_id, name)
        )
    """)

    op.execute("""
        CREATE TABLE permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT,
            UNIQUE (resource, action)
        )
    """)

    op.execute("""
        CREATE TABLE role_permissions (
            role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        )
    """)

    op.execute("""
        CREATE TABLE user_trust_roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
            granted_by UUID REFERENCES users(id),
            granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            UNIQUE (trust_id, user_id, role_id)
        )
    """)

    op.execute("""
        CREATE TABLE user_school_roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE CASCADE,
            school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
            granted_by UUID REFERENCES users(id),
            granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            UNIQUE (school_id, user_id, role_id)
        )
    """)

    # ── Worker & Compliance Layer ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE worker_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            ni_number TEXT,
            date_of_birth DATE,
            preferred_name TEXT,
            gender TEXT,
            ethnicity TEXT,
            disability_declared BOOLEAN,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            bank_account_last4 TEXT,
            bank_sort_code TEXT,
            onboarding_stage onboarding_stage NOT NULL DEFAULT 'registered',
            first_shift_cleared BOOLEAN NOT NULL DEFAULT false,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            UNIQUE (trust_id, user_id)
        )
    """)

    op.execute("""
        CREATE TABLE worker_role_types (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            category TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (trust_id, name)
        )
    """)

    op.execute("""
        CREATE TABLE worker_role_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE CASCADE,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            role_type_id UUID NOT NULL REFERENCES worker_role_types(id) ON DELETE RESTRICT,
            is_primary BOOLEAN NOT NULL DEFAULT false,
            verified_at TIMESTAMPTZ,
            verified_by UUID REFERENCES users(id),
            UNIQUE (worker_id, role_type_id)
        )
    """)

    op.execute("""
        CREATE TABLE dbs_checks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            dbs_level dbs_level NOT NULL,
            certificate_number TEXT,
            issue_date DATE,
            expiry_date DATE,
            status dbs_status NOT NULL DEFAULT 'not_started',
            on_update_service BOOLEAN NOT NULL DEFAULT false,
            last_checked_at TIMESTAMPTZ,
            checked_by UUID REFERENCES users(id),
            notes TEXT,
            storage_path TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE right_to_work_checks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            document_type rtw_document_type NOT NULL,
            document_reference TEXT,
            issue_date DATE,
            expiry_date DATE,
            status document_status NOT NULL DEFAULT 'pending_upload',
            verified_by UUID REFERENCES users(id),
            verified_at TIMESTAMPTZ,
            follow_up_date DATE,
            storage_path TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE compliance_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            document_type document_type NOT NULL,
            label TEXT,
            status document_status NOT NULL DEFAULT 'pending_upload',
            storage_path TEXT NOT NULL,
            storage_bucket TEXT NOT NULL DEFAULT 'compliance-docs',
            file_name TEXT NOT NULL,
            file_size_bytes BIGINT,
            mime_type TEXT,
            expiry_date DATE,
            expiry_reminder_sent_at TIMESTAMPTZ,
            reviewed_by UUID REFERENCES users(id),
            reviewed_at TIMESTAMPTZ,
            review_notes TEXT,
            uploaded_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE onboarding_status (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            stage onboarding_stage NOT NULL,
            stage_entered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            stage_completed_at TIMESTAMPTZ,
            completed_by UUID REFERENCES users(id),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (trust_id, worker_id, stage)
        )
    """)

    op.execute("""
        CREATE TABLE school_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
            assigned_by UUID REFERENCES users(id),
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true,
            notes TEXT,
            UNIQUE (worker_id, school_id)
        )
    """)

    # ── Booking & Scheduling Layer ────────────────────────────────────────────
    op.execute("""
        CREATE TABLE availability (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            available_date DATE NOT NULL,
            is_available BOOLEAN NOT NULL DEFAULT true,
            am_available BOOLEAN NOT NULL DEFAULT true,
            pm_available BOOLEAN NOT NULL DEFAULT true,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (worker_id, available_date)
        )
    """)

    op.execute("""
        CREATE TABLE bookings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            school_id UUID NOT NULL REFERENCES schools(id) ON DELETE RESTRICT,
            worker_id UUID REFERENCES worker_profiles(id),
            role_type_id UUID NOT NULL REFERENCES worker_role_types(id),
            requested_by UUID NOT NULL REFERENCES users(id),
            shift_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            status booking_status NOT NULL DEFAULT 'requested',
            reason TEXT,
            notes TEXT,
            offered_at TIMESTAMPTZ,
            accepted_at TIMESTAMPTZ,
            confirmed_at TIMESTAMPTZ,
            cancelled_at TIMESTAMPTZ,
            cancelled_by UUID REFERENCES users(id),
            cancellation_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
    """)

    # ── Timesheets & Payroll Layer ────────────────────────────────────────────
    op.execute("""
        CREATE TABLE timesheets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE RESTRICT,
            school_id UUID NOT NULL REFERENCES schools(id) ON DELETE RESTRICT,
            shift_date DATE NOT NULL,
            actual_start_time TIME,
            actual_end_time TIME,
            break_minutes INTEGER NOT NULL DEFAULT 0,
            total_hours NUMERIC(5,2),
            hourly_rate NUMERIC(8,4),
            gross_pay NUMERIC(10,2),
            status timesheet_status NOT NULL DEFAULT 'draft',
            submitted_at TIMESTAMPTZ,
            approved_by UUID REFERENCES users(id),
            approved_at TIMESTAMPTZ,
            rejected_by UUID REFERENCES users(id),
            rejected_at TIMESTAMPTZ,
            rejection_reason TEXT,
            exported_at TIMESTAMPTZ,
            export_reference TEXT,
            signed_by_worker BOOLEAN NOT NULL DEFAULT false,
            signed_at_school BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE payroll_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
            pay_frequency pay_frequency NOT NULL DEFAULT 'weekly',
            base_hourly_rate NUMERIC(8,4) NOT NULL,
            pension_enrolled BOOLEAN NOT NULL DEFAULT false,
            pension_threshold_met BOOLEAN NOT NULL DEFAULT false,
            auto_enrolment_date DATE,
            umbrella_company TEXT,
            is_paye BOOLEAN NOT NULL DEFAULT true,
            notes TEXT,
            effective_from DATE NOT NULL,
            effective_to DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (trust_id, worker_id, effective_from)
        )
    """)

    op.execute("""
        CREATE TABLE payroll_exports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID NOT NULL REFERENCES trusts(id) ON DELETE RESTRICT,
            export_reference TEXT NOT NULL UNIQUE,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            pay_frequency pay_frequency NOT NULL,
            total_workers INTEGER NOT NULL DEFAULT 0,
            total_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
            total_gross_pay NUMERIC(12,2) NOT NULL DEFAULT 0,
            exported_by UUID NOT NULL REFERENCES users(id),
            exported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            storage_path TEXT,
            notes TEXT
        )
    """)

    # ── Audit Log ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trust_id UUID REFERENCES trusts(id),
            user_id UUID REFERENCES users(id),
            action audit_action NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id UUID,
            school_id UUID REFERENCES schools(id),
            worker_id UUID REFERENCES worker_profiles(id),
            old_values JSONB,
            new_values JSONB,
            metadata JSONB,
            ip_address INET,
            user_agent TEXT,
            session_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.execute("CREATE INDEX idx_schools_trust_id ON schools(trust_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_users_trust_id ON users(trust_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_worker_profiles_trust_id ON worker_profiles(trust_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_bookings_trust_id ON bookings(trust_id) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_schools_urn ON schools(urn)")
    op.execute("CREATE INDEX idx_users_email ON users(email)")
    op.execute("CREATE INDEX idx_worker_profiles_user_id ON worker_profiles(user_id)")
    op.execute("CREATE INDEX idx_dbs_checks_worker_id ON dbs_checks(worker_id)")
    op.execute("CREATE INDEX idx_dbs_checks_status_expiry ON dbs_checks(status, expiry_date)")
    op.execute("CREATE INDEX idx_rtw_checks_worker_id ON right_to_work_checks(worker_id)")
    op.execute("CREATE INDEX idx_rtw_follow_up ON right_to_work_checks(follow_up_date) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_compliance_docs_worker ON compliance_documents(worker_id, document_type) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_compliance_docs_expiry ON compliance_documents(expiry_date) WHERE deleted_at IS NULL")
    op.execute("CREATE INDEX idx_bookings_shift_date ON bookings(school_id, shift_date)")
    op.execute("CREATE INDEX idx_bookings_worker_status ON bookings(worker_id, status)")
    op.execute("CREATE INDEX idx_timesheets_worker ON timesheets(worker_id, shift_date)")
    op.execute("CREATE INDEX idx_timesheets_export ON timesheets(trust_id, status, shift_date)")
    op.execute("CREATE INDEX idx_availability_worker_date ON availability(worker_id, available_date)")
    op.execute("CREATE INDEX idx_onboarding_trust_stage ON onboarding_status(trust_id, stage)")
    op.execute("CREATE INDEX idx_audit_trust_time ON audit_logs(trust_id, created_at)")
    op.execute("CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id)")
    op.execute("CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at)")
    op.execute("CREATE INDEX idx_audit_worker ON audit_logs(worker_id, created_at)")

    # ── Row Level Security ────────────────────────────────────────────────────
    rls_tables = [
        "schools", "users", "user_trust_roles", "user_school_roles",
        "worker_profiles", "worker_role_types", "worker_role_assignments",
        "dbs_checks", "right_to_work_checks", "compliance_documents",
        "onboarding_status", "school_assignments",
        "availability", "bookings",
        "timesheets", "payroll_profiles", "payroll_exports",
        "trust_branding", "audit_logs",
    ]
    for table in rls_tables:
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

    # audit_logs has nullable trust_id — widen the isolation policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_logs")
    op.execute("""
        CREATE POLICY tenant_isolation ON audit_logs
        USING (
            trust_id IS NULL
            OR trust_id = current_setting('app.current_trust_id', true)::uuid
        )
    """)

    # ── Supabase Custom Claims Hook ───────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
        RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER AS $$
        DECLARE
            claims jsonb;
            user_trust_id uuid;
            user_roles text[];
        BEGIN
            claims := event->'claims';
            SELECT u.trust_id,
                   ARRAY(SELECT r.name FROM user_trust_roles utr
                         JOIN roles r ON r.id = utr.role_id
                         WHERE utr.user_id = (event->>'user_id')::uuid
                           AND (utr.expires_at IS NULL OR utr.expires_at > now()))
            INTO user_trust_id, user_roles
            FROM users u
            WHERE u.id = (event->>'user_id')::uuid AND u.deleted_at IS NULL;

            IF user_trust_id IS NOT NULL THEN
                claims := jsonb_set(claims, '{trust_id}', to_jsonb(user_trust_id::text));
            END IF;
            IF user_roles IS NOT NULL AND array_length(user_roles, 1) > 0 THEN
                claims := jsonb_set(claims, '{app_metadata,roles}', to_jsonb(user_roles));
            END IF;
            RETURN jsonb_set(event, '{claims}', claims);
        END;
        $$
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.custom_access_token_hook")

    for table in [
        "audit_logs", "payroll_exports", "payroll_profiles", "timesheets",
        "bookings", "availability", "school_assignments", "onboarding_status",
        "compliance_documents", "right_to_work_checks", "dbs_checks",
        "worker_role_assignments", "worker_role_types", "worker_profiles",
        "user_school_roles", "user_trust_roles", "role_permissions",
        "permissions", "roles", "users", "schools", "trust_branding", "trusts",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    for enum_name in [
        "trust_status", "user_status", "onboarding_stage", "document_type",
        "document_status", "dbs_level", "dbs_status", "rtw_document_type",
        "booking_status", "timesheet_status", "pay_frequency", "audit_action",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

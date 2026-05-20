"""
Platform-wide constants. Keep numeric/string literals out of business logic.
"""

# PostgreSQL session variables used for RLS
PG_VAR_TRUST_ID = "app.current_trust_id"
PG_VAR_USER_ID = "app.current_user_id"
PG_VAR_IS_SUPERADMIN = "app.is_superadmin"

# System role names (seeded, never deleted)
ROLE_PLATFORM_SUPERADMIN = "platform_superadmin"
ROLE_TRUST_ADMIN = "trust_admin"
ROLE_HR_MANAGER = "hr_manager"
ROLE_COVER_SUPERVISOR = "cover_supervisor"
ROLE_SCHOOL_LEADER = "school_leader"      # read-only visibility; does not manage cover day-to-day
ROLE_RECEPTIONIST = "receptionist"
ROLE_PAYROLL_OFFICER = "payroll_officer"
ROLE_WORKER = "worker"

SYSTEM_ROLES = (
    ROLE_PLATFORM_SUPERADMIN,
    ROLE_TRUST_ADMIN,
    ROLE_HR_MANAGER,
    ROLE_COVER_SUPERVISOR,
    ROLE_SCHOOL_LEADER,
    ROLE_RECEPTIONIST,
    ROLE_PAYROLL_OFFICER,
    ROLE_WORKER,
)

# Supabase JWT custom claim key for trust_id
JWT_CLAIM_TRUST_ID = "trust_id"
JWT_CLAIM_APP_METADATA = "app_metadata"
JWT_CLAIM_USER_METADATA = "user_metadata"

# Pagination
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

# Storage
STORAGE_BUCKET_COMPLIANCE = "compliance-docs"
STORAGE_BUCKET_PAYROLL = "payroll-exports"
STORAGE_BUCKET_ASSETS = "trust-assets"
STORAGE_BUCKET_AVATARS = "worker-avatars"

# Allowed MIME types for compliance document uploads
ALLOWED_DOCUMENT_MIME_TYPES = frozenset({
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
})

MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Health check paths — excluded from auth middleware
PUBLIC_PATHS = frozenset({
    "/api/v1/health",
    "/api/v1/health/db",
    "/api/v1/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
})

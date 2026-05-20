"""
Seed script: system roles, permissions, and role-permission mappings.

Run once after the initial Alembic migration:
    python scripts/seed_system_roles.py

Safe to re-run — uses INSERT ... ON CONFLICT DO NOTHING.
"""

import asyncio
import sys
from pathlib import Path

# Allow running from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings

SYSTEM_ROLES = [
    ("platform_superadmin", "Platform Superadmin", "Full platform access. Bypasses all RLS.", True),
    ("trust_admin", "Trust Administrator", "Full access within their trust.", True),
    ("hr_manager", "HR Manager", "Worker onboarding, compliance management.", True),
    ("school_leader", "School Leader", "Booking and timesheet management for their school.", True),
    ("receptionist", "Receptionist", "View bookings, submit timesheets.", True),
    ("payroll_officer", "Payroll Officer", "Timesheet export and payroll data access.", True),
    ("worker", "Supply Worker", "Own profile, availability, and booking visibility.", True),
]

PERMISSIONS = [
    # Workers
    ("workers", "read"),
    ("workers", "create"),
    ("workers", "update"),
    ("workers", "view_sensitive"),
    # Compliance
    ("compliance_documents", "read"),
    ("compliance_documents", "upload"),
    ("compliance_documents", "approve"),
    ("compliance_documents", "reject"),
    ("dbs_checks", "read"),
    ("dbs_checks", "update"),
    ("rtw_checks", "read"),
    ("rtw_checks", "update"),
    # Availability
    ("availability", "read"),
    ("availability", "write"),
    # Bookings
    ("bookings", "read"),
    ("bookings", "create"),
    ("bookings", "cancel"),
    # Timesheets
    ("timesheets", "read"),
    ("timesheets", "submit"),
    ("timesheets", "approve"),
    ("timesheets", "reject"),
    ("timesheets", "export"),
    # Payroll
    ("payroll", "read"),
    ("payroll", "export"),
    # Schools
    ("schools", "read"),
    ("schools", "manage"),
    # Audit
    ("audit_logs", "read"),
]

# Role → permissions (role_name → list of (resource, action) tuples)
ROLE_PERMISSIONS: dict[str, list[tuple[str, str]]] = {
    "trust_admin": [p for p in PERMISSIONS],  # all
    "hr_manager": [
        ("workers", "read"), ("workers", "create"), ("workers", "update"),
        ("compliance_documents", "read"), ("compliance_documents", "approve"),
        ("compliance_documents", "reject"), ("compliance_documents", "upload"),
        ("dbs_checks", "read"), ("dbs_checks", "update"),
        ("rtw_checks", "read"), ("rtw_checks", "update"),
        ("bookings", "read"), ("bookings", "create"),
        ("timesheets", "read"), ("availability", "read"),
        ("schools", "read"),
    ],
    "school_leader": [
        ("bookings", "read"), ("bookings", "create"), ("bookings", "cancel"),
        ("timesheets", "read"), ("timesheets", "approve"), ("timesheets", "reject"),
        ("workers", "read"), ("schools", "read"),
    ],
    "receptionist": [
        ("bookings", "read"), ("timesheets", "read"), ("timesheets", "submit"),
    ],
    "payroll_officer": [
        ("timesheets", "read"), ("timesheets", "export"),
        ("payroll", "read"), ("payroll", "export"),
        ("workers", "read"), ("workers", "view_sensitive"),
    ],
    "worker": [
        ("availability", "read"), ("availability", "write"),
        ("bookings", "read"), ("timesheets", "read"), ("timesheets", "submit"),
        ("compliance_documents", "upload"),
    ],
}


async def seed(session: AsyncSession) -> None:
    print("Seeding system roles...")
    for name, display_name, description, is_system in SYSTEM_ROLES:
        await session.execute(
            text("""
                INSERT INTO roles (name, display_name, description, is_system)
                VALUES (:name, :display_name, :description, :is_system)
                ON CONFLICT (trust_id, name) DO NOTHING
            """),
            {
                "name": name,
                "display_name": display_name,
                "description": description,
                "is_system": is_system,
            },
        )

    print(f"Seeding {len(PERMISSIONS)} permissions...")
    for resource, action in PERMISSIONS:
        await session.execute(
            text("""
                INSERT INTO permissions (resource, action)
                VALUES (:resource, :action)
                ON CONFLICT (resource, action) DO NOTHING
            """),
            {"resource": resource, "action": action},
        )

    print("Seeding role-permission mappings...")
    for role_name, perms in ROLE_PERMISSIONS.items():
        for resource, action in perms:
            await session.execute(
                text("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM roles r, permissions p
                    WHERE r.name = :role_name
                      AND r.trust_id IS NULL
                      AND p.resource = :resource
                      AND p.action = :action
                    ON CONFLICT DO NOTHING
                """),
                {"role_name": role_name, "resource": resource, "action": action},
            )

    await session.commit()
    print("Seed complete.")


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        # Bypass RLS for seeding — requires superadmin Postgres role or
        # running as the database owner.
        await session.execute(text("SET app.is_superadmin = 'true'"))
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

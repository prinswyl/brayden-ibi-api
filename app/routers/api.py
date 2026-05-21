"""
Central API router aggregator.

All versioned sub-routers are registered here and mounted under the
configured api_v1_prefix (default: /api/v1).

Adding a new domain router:
  1. Import the router from its module.
  2. Call api_router.include_router(...) with an appropriate prefix and tags.
"""

from fastapi import APIRouter

from app.config import get_settings
from app.routers.v1 import auth, example, health
from app.routers.v1 import (
    workers,
    onboarding,
    compliance_documents,
    verification,
    dashboard,
    availability,
    bookings,
    attendance,
    timesheets,
    shifts_dashboard,
    users,
    schools,
)

settings = get_settings()

api_router = APIRouter(prefix=settings.api_v1_prefix)

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(example.router)

# Compliance Vault V1
api_router.include_router(workers.router)
api_router.include_router(onboarding.router)
api_router.include_router(compliance_documents.router)
api_router.include_router(verification.router)
api_router.include_router(dashboard.router)

# Bookings & Timesheets
api_router.include_router(availability.router)
api_router.include_router(bookings.router)
api_router.include_router(attendance.router)
api_router.include_router(timesheets.router)
api_router.include_router(shifts_dashboard.router)

# User Provisioning
api_router.include_router(users.router)
api_router.include_router(schools.router)

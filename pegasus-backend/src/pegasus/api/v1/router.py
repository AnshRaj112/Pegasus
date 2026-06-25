# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T11:38:03Z
# --- END GENERATED FILE METADATA ---

from fastapi import APIRouter

from pegasus.api.v1.admin_auth import router as admin_auth_router
from pegasus.api.v1.admin_cloud_connections import router as admin_cloud_connections_router
from pegasus.api.v1.health import router as health_router
from pegasus.api.v1.validation import router as validation_router
from pegasus.api.v1.validation_history import router as validation_history_router

router = APIRouter()
router.include_router(health_router)
router.include_router(admin_auth_router)
router.include_router(admin_cloud_connections_router)
router.include_router(validation_router)
router.include_router(validation_history_router)

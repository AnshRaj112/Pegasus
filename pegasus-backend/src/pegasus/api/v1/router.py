# --- BEGIN GENERATED FILE METADATA ---
<<<<<<< HEAD
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
=======
# Authors: github-actions[bot]
# Last edited: 2026-06-05T09:31:09Z
>>>>>>> 94051c3720b8bad458bdf77183420f7b053658d8
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

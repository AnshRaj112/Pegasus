from fastapi import APIRouter

from pegasus.api.v1.health import router as health_router
from pegasus.api.v1.validation import router as validation_router

router = APIRouter()
router.include_router(health_router)
router.include_router(validation_router)

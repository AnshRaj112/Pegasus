# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:01:15Z
# --- END GENERATED FILE METADATA ---

from fastapi import APIRouter

from pegasus import __version__
from pegasus.core.config import get_settings
from pegasus.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name.lower(),
        version=__version__,
        environment=settings.environment,
    )

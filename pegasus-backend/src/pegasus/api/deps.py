# --- BEGIN GENERATED FILE METADATA ---
<<<<<<< HEAD
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
=======
# Authors: github-actions[bot]
# Last edited: 2026-06-05T09:31:09Z
>>>>>>> 94051c3720b8bad458bdf77183420f7b053658d8
# --- END GENERATED FILE METADATA ---

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pegasus.core.config import Settings, get_settings
from pegasus.core.database import get_db
from pegasus.services.validation_service import ValidationService


def get_app_settings() -> Settings:
    return get_settings()


def get_validation_service(settings: Annotated[Settings, Depends(get_app_settings)]) -> ValidationService:
    return ValidationService(settings=settings)


DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
ValidationServiceDep = Annotated[ValidationService, Depends(get_validation_service)]

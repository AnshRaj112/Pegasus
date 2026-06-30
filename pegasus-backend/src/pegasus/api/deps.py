# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:21:03Z
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

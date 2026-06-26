# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:32:35Z
# --- END GENERATED FILE METADATA ---

"""Schemas for admin-managed cloud connections."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CloudConnectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    provider: str = Field(default="google-cloud-storage")
    bucket: str = Field(
        default="",
        description="Default GCS bucket; leave empty to browse any accessible bucket at validation time.",
    )
    project_id: str | None = None
    credentials_json: str = Field(min_length=2)
    active: bool = True


class CloudConnectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    provider: str | None = None
    bucket: str | None = None
    project_id: str | None = None
    credentials_json: str | None = Field(default=None, min_length=2)
    active: bool | None = None


class CloudConnectionResponse(BaseModel):
    id: UUID
    name: str
    provider: str
    bucket: str
    project_id: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


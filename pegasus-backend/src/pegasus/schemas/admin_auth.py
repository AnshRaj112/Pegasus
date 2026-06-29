# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-28T11:56:30Z
# --- END GENERATED FILE METADATA ---

"""Request/response models for admin auth."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AdminSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AdminAuthUserResponse(BaseModel):
    email: str


class AdminSessionStatusResponse(BaseModel):
    email: str
    expires_at: datetime

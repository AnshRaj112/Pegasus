# --- BEGIN GENERATED FILE METADATA ---
<<<<<<< HEAD
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
=======
# Authors: github-actions[bot]
# Last edited: 2026-06-05T09:31:09Z
>>>>>>> 94051c3720b8bad458bdf77183420f7b053658d8
# --- END GENERATED FILE METADATA ---

"""Request/response models for admin auth."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AdminAuthUserResponse(BaseModel):
    email: str

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:51:18Z
# --- END GENERATED FILE METADATA ---

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Liveness indicator")
    service: str
    version: str
    environment: str

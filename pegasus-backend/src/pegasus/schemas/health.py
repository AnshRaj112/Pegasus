# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T05:26:24Z
# --- END GENERATED FILE METADATA ---

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Liveness indicator")
    service: str
    version: str
    environment: str

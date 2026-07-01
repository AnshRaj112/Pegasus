# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T08:46:25Z
# --- END GENERATED FILE METADATA ---

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Liveness indicator")
    service: str
    version: str
    environment: str

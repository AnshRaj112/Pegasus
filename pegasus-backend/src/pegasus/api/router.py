# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T09:36:09Z
# --- END GENERATED FILE METADATA ---

from fastapi import APIRouter

from pegasus.api.v1.router import router as v1_router

api_router = APIRouter()
api_router.include_router(v1_router)

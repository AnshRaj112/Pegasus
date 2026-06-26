# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T07:47:43Z
# --- END GENERATED FILE METADATA ---

from fastapi import APIRouter

from pegasus.api.v1.router import router as v1_router

api_router = APIRouter()
api_router.include_router(v1_router)

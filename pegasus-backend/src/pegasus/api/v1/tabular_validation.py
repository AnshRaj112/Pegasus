"""Category-1 tabular validation API (cleared for rebuild)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/validate/tabular", tags=["validation-tabular"])

_NOT_IMPLEMENTED_DETAIL = (
    "Tabular validation has been removed for rebuild. "
    "Endpoints will return once new validation rules are implemented."
)


@router.post("/run", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def run_tabular_pipeline() -> None:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED_DETAIL)

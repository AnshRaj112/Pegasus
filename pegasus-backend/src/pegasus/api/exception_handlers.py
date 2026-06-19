# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-19T09:47:48Z
# --- END GENERATED FILE METADATA ---

"""Map domain exceptions to HTTP responses."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pegasus.services.exceptions import ValidationBadRequestError, ValidationUnprocessableError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers for service-layer validation errors."""

    @app.exception_handler(ValidationBadRequestError)
    async def _bad_request(_request: Request, exc: ValidationBadRequestError) -> JSONResponse:
        logger.info("Validation bad request: %s", exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValidationUnprocessableError)
    async def _unprocessable(_request: Request, exc: ValidationUnprocessableError) -> JSONResponse:
        logger.info("Validation unprocessable: %s", exc)
        return JSONResponse(status_code=422, content={"detail": str(exc)})

"""CSV validation endpoint (UID-based comparison)."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from pegasus.api.deps import AppSettings, ValidationServiceDep
from pegasus.core.database import AsyncSessionLocal
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.schemas.validation import (
    MismatchSampleRow,
    ValidateResponse,
    ValidationSummary,
    build_mismatch_counts,
)
from pegasus.services.exceptions import ValidationBadRequestError
from pegasus.services.validation_service import ValidationRunResult

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validation"])

_DEFAULT_UPLOAD_SUFFIX = ".csv"


async def _spool_upload_to_temp(
    upload: UploadFile,
    *,
    max_bytes: int,
    label: str,
) -> Path:
    """Stream upload to a temp file; enforce size limit."""
    suffix = Path(upload.filename or _DEFAULT_UPLOAD_SUFFIX).suffix or _DEFAULT_UPLOAD_SUFFIX
    fd, path_str = tempfile.mkstemp(prefix=f"pegasus_{label}_", suffix=suffix)
    path = Path(path_str)
    total = 0
    committed = False
    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"{label} exceeds maximum upload size of {max_bytes} bytes",
                )
            os.write(fd, chunk)
        if total == 0:
            raise ValidationBadRequestError(f"{label} is empty")
        committed = True
        return path
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        if not committed:
            path.unlink(missing_ok=True)


@router.post(
    "/validate",
    response_model=ValidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare two CSV files by UID",
    responses={
        400: {"description": "Invalid files, delimiter, or missing uid column"},
        413: {"description": "Upload exceeds configured size limit"},
        422: {"description": "Comparison cannot run (e.g. duplicate UIDs)"},
    },
)
async def validate_csv_files(
    settings: AppSettings,
    validation_service: ValidationServiceDep,
    source_file: Annotated[UploadFile, File(description="Expected / golden CSV")],
    target_file: Annotated[UploadFile, File(description="Actual / candidate CSV")],
    uid_column: Annotated[str, Form(description="Column name to join on (must exist in both files)")],
    delimiter: Annotated[
        str,
        Form(
            description=(
                "Field separator. Use 'auto' (default) to infer, "
                "'tab'/'\\t' for tab, or provide explicit separator "
                "(single-char via Polars; multi-char via pandas fallback)."
            )
        ),
    ] = "auto",
) -> ValidateResponse:
    """Accept two CSV uploads and return mismatch summary plus sample rows."""
    max_bytes = settings.validation_max_upload_bytes
    sample_limit = settings.validation_mismatch_sample_limit

    source_path: Path | None = None
    target_path: Path | None = None
    run_id: uuid.UUID | None = None
    run_result: ValidationRunResult | None = None

    try:
        source_path = await _spool_upload_to_temp(source_file, max_bytes=max_bytes, label="source")
        target_path = await _spool_upload_to_temp(target_file, max_bytes=max_bytes, label="target")

        if settings.enable_validation_persistence:
            try:
                async with AsyncSessionLocal() as session:
                    run_orm = await ValidationRunRepository.create_running(
                        session,
                        source_filename=source_file.filename,
                        target_filename=target_file.filename,
                        uid_column=uid_column.strip(),
                        delimiter=delimiter,
                    )
                    await session.commit()
                    run_id = run_orm.id
            except Exception as exc:
                logger.exception("Failed to create validation run record: %s", exc)
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not persist validation run; check database connectivity",
                ) from exc

        try:
            run_result = await validation_service.validate_csv_pair(
                source_path=source_path,
                target_path=target_path,
                uid_column=uid_column,
                delimiter=delimiter,
            )
        except Exception as exc:
            if run_id is not None:
                try:
                    async with AsyncSessionLocal() as session:
                        await ValidationRunRepository.mark_failed(session, run_id, detail=repr(exc))
                        await session.commit()
                except Exception as persist_exc:
                    logger.error("Failed to record validation failure in database: %s", persist_exc)
            raise

        if settings.enable_validation_persistence and run_id is not None and run_result is not None:
            try:
                async with AsyncSessionLocal() as session:
                    await ValidationRunRepository.complete_success(session, run_id, run_result)
                    await session.commit()
            except Exception as exc:
                logger.exception("Failed to persist validation results: %s", exc)
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Validation succeeded but results could not be saved; check database logs",
                ) from exc

    finally:
        for p in (source_path, target_path):
            if p is not None:
                try:
                    p.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Failed to remove temp upload %s: %s", p, exc)

    assert run_result is not None
    mismatches = run_result.report.mismatches
    # Stable sampling: sort first so one mismatch column type doesn't dominate
    # truncated previews when sample_limit is small.
    if sample_limit > 0 and mismatches.height > 0:
        sample_df = (
            mismatches.sort(
                by=["uid", "mismatch_type", "column_name"],
                nulls_last=True,
            ).head(sample_limit)
        )
    else:
        sample_df = mismatches.slice(0, 0)
    samples = [MismatchSampleRow.model_validate(row) for row in sample_df.to_dicts()]

    counts_model = build_mismatch_counts(run_result.report.summary)
    total_records = mismatches.height
    summary = ValidationSummary(
        source_row_count=run_result.source_row_count,
        target_row_count=run_result.target_row_count,
        compared_column_count=run_result.compared_column_count,
        total_mismatch_records=total_records,
        is_match=total_records == 0,
    )

    return ValidateResponse(
        summary=summary,
        mismatch_counts=counts_model,
        mismatch_samples=samples,
        run_id=run_id,
    )

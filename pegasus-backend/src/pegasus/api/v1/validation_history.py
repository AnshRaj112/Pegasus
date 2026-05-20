"""Persisted validation history (mappings, reports, durations)."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from pegasus.api.deps import AppSettings
from pegasus.core.database import AsyncSessionLocal
from pegasus.core.file_pair import compute_file_pair_key
from pegasus.models.enums import ValidationRunStatus
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.validation.delimiter_tokens import normalize_delimiter_for_storage
from pegasus.schemas.validation import ColumnMapping, ColumnMappingFormatCheck, FooterValidationResult, MismatchCounts
from pegasus.schemas.validation_history import (
    SaveDraftRequest,
    ValidationDurations,
    ValidationHistoryDetail,
    ValidationHistoryListResponse,
    ValidationHistoryMismatchRow,
    ValidationHistoryMismatchesResponse,
    ValidationHistorySummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validation-history"])


def _require_persistence(settings: AppSettings) -> None:
    if not settings.enable_validation_persistence:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Validation history requires PEGASUS_ENABLE_VALIDATION_PERSISTENCE=true and a migrated database",
        )


def _durations_from_run(run) -> ValidationDurations:
    return ValidationDurations(
        upload_seconds=run.upload_duration_seconds,
        validation_seconds=run.validation_duration_seconds,
        total_seconds=run.total_duration_seconds,
    )


def _mismatch_counts_from_run(run) -> MismatchCounts:
    return MismatchCounts(
        missing_in_target=run.missing_in_target_count,
        extra_in_target=run.extra_in_target_count,
        value_mismatch=run.value_mismatch_count,
    )


def _summary_from_run(run) -> ValidationHistorySummary:
    mappings = run.column_mappings if isinstance(run.column_mappings, list) else []
    return ValidationHistorySummary(
        run_id=run.id,
        status=run.status.value if isinstance(run.status, ValidationRunStatus) else str(run.status),
        source_path=run.source_path,
        target_path=run.target_path,
        source_filename=run.source_filename,
        target_filename=run.target_filename,
        uid_column=run.uid_column,
        delimiter=run.delimiter,
        is_match=run.is_match,
        mismatch_counts=_mismatch_counts_from_run(run),
        mapping_count=len(mappings),
        durations=_durations_from_run(run),
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _detail_from_run(run) -> ValidationHistoryDetail:
    base = _summary_from_run(run)
    raw_mappings = run.column_mappings if isinstance(run.column_mappings, list) else []
    compared = run.compared_columns if isinstance(run.compared_columns, list) else []
    format_checks_raw = run.mapping_format_checks if isinstance(run.mapping_format_checks, list) else []
    footer_raw = run.footer_validation if isinstance(run.footer_validation, dict) else None
    return ValidationHistoryDetail(
        **base.model_dump(),
        column_mappings=[ColumnMapping.model_validate(m) for m in raw_mappings],
        compared_columns=[str(c) for c in compared],
        mapping_format_checks=[ColumnMappingFormatCheck.model_validate(c) for c in format_checks_raw],
        footer_validation=FooterValidationResult.model_validate(footer_raw) if footer_raw else None,
        validate_header_formats=bool(run.validate_header_formats),
        validate_footers=bool(run.validate_footers),
        source_row_count=run.source_row_count,
        target_row_count=run.target_row_count,
        compared_column_count=run.compared_column_count,
        error_detail=run.error_detail,
    )


@router.get(
    "/validate/history",
    response_model=ValidationHistoryListResponse,
    summary="List persisted validation runs (newest first)",
)
async def list_validation_history(
    settings: AppSettings,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_path: Annotated[str | None, Query(description="Filter to runs for this source file path")] = None,
    target_path: Annotated[str | None, Query(description="Filter to runs for this target file path")] = None,
) -> ValidationHistoryListResponse:
    _require_persistence(settings)
    pair_key = None
    if source_path and target_path:
        pair_key = compute_file_pair_key(source_path, target_path)
        if pair_key is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid source_path or target_path")

    try:
        async with AsyncSessionLocal() as session:
            total = await ValidationRunRepository.count_runs(session, file_pair_key=pair_key)
            runs = await ValidationRunRepository.list_recent(
                session,
                limit=limit,
                offset=offset,
                file_pair_key=pair_key,
            )
    except Exception as exc:
        logger.exception("Failed to list validation history: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load validation history; check database connectivity",
        ) from exc

    return ValidationHistoryListResponse(
        items=[_summary_from_run(r) for r in runs],
        total=total,
        file_pair_key=pair_key,
    )


@router.get(
    "/validate/history/{run_id}",
    response_model=ValidationHistoryDetail,
    summary="Get one persisted validation run (mapping + report summary)",
)
async def get_validation_history_run(
    settings: AppSettings,
    run_id: uuid.UUID,
) -> ValidationHistoryDetail:
    _require_persistence(settings)
    try:
        async with AsyncSessionLocal() as session:
            run = await ValidationRunRepository.get_run(session, run_id)
    except Exception as exc:
        logger.exception("Failed to load validation run %s: %s", run_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load validation run; check database connectivity",
        ) from exc

    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown run_id")
    return _detail_from_run(run)


@router.get(
    "/validate/history/{run_id}/mismatches",
    response_model=ValidationHistoryMismatchesResponse,
    summary="Paginated mismatch rows for a persisted validation run",
)
async def list_validation_history_mismatches(
    settings: AppSettings,
    run_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=5000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ValidationHistoryMismatchesResponse:
    _require_persistence(settings)
    try:
        async with AsyncSessionLocal() as session:
            run = await ValidationRunRepository.get_run(session, run_id)
            if run is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown run_id")
            rows, total = await ValidationRunRepository.list_mismatches(
                session,
                run_id,
                limit=limit,
                offset=offset,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load mismatches for run %s: %s", run_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load mismatch rows; check database connectivity",
        ) from exc

    return ValidationHistoryMismatchesResponse(
        run_id=run_id,
        items=[
            ValidationHistoryMismatchRow(
                uid=r.uid,
                mismatch_type=r.mismatch_type,
                column_name=r.column_name,
                source_value=r.source_value,
                target_value=r.target_value,
                row_detail=r.row_detail,
            )
            for r in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.delete(
    "/validate/history/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a persisted validation run",
)
async def delete_validation_history_run(
    settings: AppSettings,
    run_id: uuid.UUID,
) -> None:
    _require_persistence(settings)
    try:
        async with AsyncSessionLocal() as session:
            deleted = await ValidationRunRepository.delete_run(session, run_id)
            if not deleted:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown run_id")
            await session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete validation run %s: %s", run_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete validation run; check database connectivity",
        ) from exc


@router.delete(
    "/validate/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete persisted validation runs (either all history or for a specific file pair)",
)
async def delete_validation_history(
    settings: AppSettings,
    source_path: Annotated[str | None, Query(description="Source file path to delete history for")] = None,
    target_path: Annotated[str | None, Query(description="Target file path to delete history for")] = None,
    all_history: Annotated[bool, Query(alias="all", description="Set to true to delete all history")] = False,
) -> None:
    _require_persistence(settings)
    if not all_history and (not source_path or not target_path):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'all=true' or both 'source_path' and 'target_path' parameters",
        )
    try:
        async with AsyncSessionLocal() as session:
            if all_history:
                count = await ValidationRunRepository.delete_all_runs(session)
            else:
                count = await ValidationRunRepository.delete_runs_by_file_pair(session, source_path, target_path)
            
            if not all_history and count == 0:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No history found for the specified file pair")
            await session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete validation history: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not delete validation history; check database connectivity",
        ) from exc


@router.post(
    "/validate/history/draft",
    response_model=ValidationHistoryDetail,
    summary="Save a mapping draft without running validation",
)
async def save_validation_draft(
    settings: AppSettings,
    body: SaveDraftRequest,
) -> ValidationHistoryDetail:
    _require_persistence(settings)
    
    # Resolve the paths to absolute paths
    from pathlib import Path
    from pegasus.api.v1.validation import resolve_local_csv_path
    
    try:
        source_path = resolve_local_csv_path(body.source_path, settings)
        target_path = resolve_local_csv_path(body.target_path, settings)
    except HTTPException:
        # Fallback if local paths are disabled or files don't exist yet, we still save them as-is
        source_path = Path(body.source_path)
        target_path = Path(body.target_path)
        
    try:
        async with AsyncSessionLocal() as session:
            from pegasus.models import ValidationRun
            from pegasus.models.enums import ValidationRunStatus
            
            src = str(source_path)
            tgt = str(target_path)
            pair_key = compute_file_pair_key(src, tgt) if src and tgt else None
            
            run = ValidationRun(
                status=ValidationRunStatus.PENDING,
                source_filename=source_path.name,
                target_filename=target_path.name,
                source_path=src,
                target_path=tgt,
                file_pair_key=pair_key,
                uid_column=body.uid_column.strip(),
                delimiter=normalize_delimiter_for_storage(body.delimiter),
                column_mappings=[m.model_dump() for m in body.column_mappings],
                validate_header_formats=body.validate_header_formats,
                validate_footers=body.validate_footers,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return _detail_from_run(run)
    except Exception as exc:
        logger.exception("Failed to save draft mapping: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not save draft mapping; check database connectivity",
        ) from exc




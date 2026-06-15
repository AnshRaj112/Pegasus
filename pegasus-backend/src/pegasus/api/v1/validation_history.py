# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:08:54Z
# --- END GENERATED FILE METADATA ---

"""Persisted validation history (mappings, reports, durations)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta
from sqlalchemy import select
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from pegasus.api.deps import AppSettings
from pegasus.core.database import AsyncSessionLocal
from pegasus.core.file_pair import compute_file_pair_key
from pegasus.core.local_paths import (
    compute_file_pair_key_for_settings,
    to_display_path,
)
from pegasus.models import ValidationEntity
from pegasus.models.enums import ValidationRunStatus
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.services.entity_inference_service import (
    EntityDefinition,
    infer_entity_from_filenames,
    normalize_entity_name,
)
from pegasus.core.delimiter_tokens import normalize_delimiter_for_storage
from pegasus.schemas.validation import ColumnMapping, ColumnMappingFormatCheck, FooterValidationResult, MismatchCounts
from pegasus.schemas.validation_history import (
    SaveDraftRequest,
    ValidationEntityCreateRequest,
    ValidationEntityInsight,
    ValidationEntityInsightsResponse,
    ValidationEntityRecord,
    ValidationEntityRunDetail,
    ValidationDailyStatRow,
    ValidationDailyStatsResponse,
    ValidationDailyTotals,
    ValidationDurations,
    ValidationHistoryDetail,
    ValidationHistoryListResponse,
    ValidationHistoryMismatchRow,
    ValidationHistoryMismatchesResponse,
    ValidationHistorySummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validation-history"])


async def _list_entity_definitions(session) -> list[EntityDefinition]:
    rows = list((await session.scalars(select(ValidationEntity))).all())
    return [
        EntityDefinition(
            name=row.name,
            display_name=row.display_name,
            aliases=list(row.aliases or []),
        )
        for row in rows
    ]


def _entity_table_missing(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "validation_entities" in text
        and (
            "undefinedtableerror" in text
            or "undefined table" in text
            or 'relation "validation_entities" does not exist' in text
            or "relation 'validation_entities' does not exist" in text
        )
    )


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


def _summary_from_run(run, settings: AppSettings) -> ValidationHistorySummary:
    mappings = run.column_mappings if isinstance(run.column_mappings, list) else []
    source_path = to_display_path(run.source_path, settings) if run.source_path else None
    target_path = to_display_path(run.target_path, settings) if run.target_path else None
    return ValidationHistorySummary(
        run_id=run.id,
        status=run.status.value if isinstance(run.status, ValidationRunStatus) else str(run.status),
        source_path=source_path,
        target_path=target_path,
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


def _detail_from_run(run, settings: AppSettings) -> ValidationHistoryDetail:
    base = _summary_from_run(run, settings)
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
        pair_key = compute_file_pair_key_for_settings(source_path, target_path, settings)
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
        items=[_summary_from_run(r, settings) for r in runs],
        total=total,
        file_pair_key=pair_key,
    )


@router.get(
    "/validate/history/daily-stats",
    response_model=ValidationDailyStatsResponse,
    summary="Daily passed/failed counts from persisted validation runs",
)
async def validation_history_daily_stats(
    settings: AppSettings,
    days: Annotated[int, Query(ge=1, le=366)] = 30,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> ValidationDailyStatsResponse:
    _require_persistence(settings)
    today = datetime.now(UTC).date()
    if date_from is not None and date_to is not None:
        start_d, end_d = date_from, date_to
    else:
        end_d = today
        start_d = end_d - timedelta(days=days - 1)
    if start_d > end_d:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="'from' must be before or equal to 'to'")

    start_dt = datetime.combine(start_d, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end_d, time.min, tzinfo=UTC) + timedelta(days=1)

    try:
        async with AsyncSessionLocal() as session:
            # If the range is one day or less, return hourly buckets instead of daily.
            if (end_dt - start_dt) <= timedelta(days=1):
                raw = await ValidationRunRepository.hourly_completed_stats(session, start=start_dt, end=end_dt)
                # Build mapping by hour (datetime)
                by_bucket: dict[datetime, tuple[int, int]] = {b: (p, f) for b, p, f in raw}
                items: list[ValidationDailyStatRow] = []
                total_passed = total_failed = 0
                cur = start_dt
                while cur < end_dt:
                    p, f = by_bucket.get(cur, (0, 0))
                    items.append(ValidationDailyStatRow(date=cur, passed=p, failed=f, total=p + f))
                    total_passed += p
                    total_failed += f
                    cur += timedelta(hours=1)
            else:
                raw = await ValidationRunRepository.daily_completed_stats(session, start=start_dt, end=end_dt)
                by_day: dict[date, tuple[int, int]] = {}
                for bucket, p, f in raw:
                    d = bucket.date() if hasattr(bucket, "date") else bucket
                    by_day[d] = (p, f)
                items = []
                total_passed = total_failed = 0
                d = start_d
                while d <= end_d:
                    p, f = by_day.get(d, (0, 0))
                    # normalize to midnight UTC
                    dt = datetime.combine(d, time.min, tzinfo=UTC)
                    items.append(ValidationDailyStatRow(date=dt, passed=p, failed=f, total=p + f))
                    total_passed += p
                    total_failed += f
                    d += timedelta(days=1)
    except Exception as exc:
        logger.exception("Failed to load daily validation stats: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load validation stats; check database connectivity",
        ) from exc

    return ValidationDailyStatsResponse(
        items=items,
        totals=ValidationDailyTotals(
            passed=total_passed,
            failed=total_failed,
            total=total_passed + total_failed,
        ),
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
    return _detail_from_run(run, settings)


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
    mismatch_type: Annotated[
        str | None,
        Query(description="Filter by missing_in_target | extra_in_target | value_mismatch"),
    ] = None,
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
                mismatch_type=mismatch_type,
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
                pair_key = compute_file_pair_key_for_settings(source_path, target_path, settings)
                count = await ValidationRunRepository.delete_runs_by_file_pair_key(session, pair_key)
            
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
            
            src_display = to_display_path(source_path, settings)
            tgt_display = to_display_path(target_path, settings)
            pair_key = compute_file_pair_key_for_settings(
                str(source_path),
                str(target_path),
                settings,
            )
            
            run = ValidationRun(
                status=ValidationRunStatus.PENDING,
                source_filename=source_path.name,
                target_filename=target_path.name,
                source_path=src_display,
                target_path=tgt_display,
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
            return _detail_from_run(run, settings)
    except Exception as exc:
        logger.exception("Failed to save draft mapping: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not save draft mapping; check database connectivity",
        ) from exc


@router.post(
    "/validate/history/entities",
    response_model=ValidationEntityRecord,
    summary="Create or update an entity used for filename inference",
)
async def create_validation_entity(
    settings: AppSettings,
    body: ValidationEntityCreateRequest,
) -> ValidationEntityRecord:
    _require_persistence(settings)
    normalized_name = normalize_entity_name(body.display_name)
    if not normalized_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="display_name does not contain a valid entity name")
    clean_aliases = sorted({normalize_entity_name(a) for a in body.aliases if normalize_entity_name(a)})
    clean_aliases = [a for a in clean_aliases if a != normalized_name]
    try:
        async with AsyncSessionLocal() as session:
            existing = await session.scalar(select(ValidationEntity).where(ValidationEntity.name == normalized_name))
            if existing is not None:
                merged = sorted(set(list(existing.aliases or []) + clean_aliases))
                existing.display_name = body.display_name.strip()
                existing.aliases = merged
                await session.commit()
                await session.refresh(existing)
                row = existing
            else:
                row = ValidationEntity(
                    name=normalized_name,
                    display_name=body.display_name.strip(),
                    aliases=clean_aliases,
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
    except Exception as exc:
        if _entity_table_missing(exc):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Entity registry is not migrated yet. Run backend database migration and try again.",
            ) from exc
        logger.exception("Failed to create/update validation entity: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not persist entity definition; check database connectivity",
        ) from exc
    return ValidationEntityRecord(
        name=row.name,
        display_name=row.display_name,
        aliases=list(row.aliases or []),
        created_at=row.created_at,
    )


@router.get(
    "/validate/history/entities/insights",
    response_model=ValidationEntityInsightsResponse,
    summary="Infer entities from filenames and summarize pass/fail over recent runs",
)
async def list_validation_entity_insights(
    settings: AppSettings,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ValidationEntityInsightsResponse:
    _require_persistence(settings)
    try:
        async with AsyncSessionLocal() as session:
            try:
                entities = await _list_entity_definitions(session)
            except Exception as exc:
                if _entity_table_missing(exc):
                    logger.warning(
                        "validation_entities table missing; falling back to filename-only inference"
                    )
                    await session.rollback()
                    entities = []
                else:
                    raise
            runs = await ValidationRunRepository.list_recent(session, limit=limit, offset=0)
    except Exception as exc:
        logger.exception("Failed to compute entity insights: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load entity insights; check database connectivity",
        ) from exc

    buckets: dict[str, ValidationEntityInsight] = {}
    for run in runs:
        inference = infer_entity_from_filenames(run.source_filename, run.target_filename, entities)
        key = inference.inferred_entity
        if key not in buckets:
            buckets[key] = ValidationEntityInsight(
                inferred_entity=inference.inferred_entity,
                display_name=inference.display_name,
                confidence=inference.confidence,
                matched_existing_entity=inference.matched_existing,
                needs_confirmation=not inference.matched_existing,
                candidate_tokens=inference.candidate_tokens,
                success_count=0,
                failed_count=0,
                total_count=0,
                details=[],
            )
        item = buckets[key]
        is_success = run.is_match is True and run.status == ValidationRunStatus.COMPLETED
        if is_success:
            item.success_count += 1
        else:
            item.failed_count += 1
        item.total_count += 1
        item.details.append(
            ValidationEntityRunDetail(
                run_id=run.id,
                status=run.status.value if isinstance(run.status, ValidationRunStatus) else str(run.status),
                source_filename=run.source_filename,
                target_filename=run.target_filename,
                completed_at=run.completed_at,
                is_match=run.is_match,
                mismatch_counts=_mismatch_counts_from_run(run),
            )
        )

    return ValidationEntityInsightsResponse(
        limit=limit,
        entities=sorted(
            list(buckets.values()),
            key=lambda x: (x.needs_confirmation, -x.total_count, x.display_name.lower()),
        ),
    )




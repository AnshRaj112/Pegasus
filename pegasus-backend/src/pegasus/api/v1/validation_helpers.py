# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T11:38:03Z
# --- END GENERATED FILE METADATA ---

"""Shared helpers for validation API endpoints and job polling."""

from __future__ import annotations

import gc
import logging
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

from pegasus.core.config import Settings
from pegasus.core.database import AsyncSessionLocal
from pegasus.core.json_util import loads_str
from pegasus.models.enums import ValidationRunStatus
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.schemas.validation import (
    ColumnMappingFormatCheck,
    FooterValidationResult,
    MismatchSampleGroups,
    ValidateResponse,
    ValidationDurations,
    ValidationJobDetailResponse,
    ValidationSummary,
    ValidationTestMode,
    build_mismatch_counts,
    parse_stored_footer_blob,
)
from pegasus.services.validation_results import ValidationRunDurations, ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame

from pegasus.validation.test_mode_policy import (
    clamp_snippet_limit,
    effective_run_is_match,
    normalize_test_mode,
    validation_run_is_match,
)

from .mismatch_sample import (
    build_grouped_mismatch_samples,
    count_mismatch_types_ndjson,
    load_mismatch_polars_for_api,
    load_per_column_value_mismatch_sample_from_ndjson,
    load_value_mismatch_sample_from_ndjson,
    mismatch_record_total,
    normalize_mismatch_summary,
    paginate_mismatch_rows_from_ndjson,
    reconcile_summary_with_artifact,
    stream_all_value_mismatch_rows_from_ndjson,
    stream_presence_mismatch_rows_from_ndjson,
    value_mismatch_counts_by_column,
    value_mismatch_counts_by_column_ndjson,
)

_completed_job_cache: OrderedDict[uuid.UUID, tuple[float, ValidationJobDetailResponse]] = OrderedDict()
_completed_job_lock = threading.Lock()
_COMPLETED_JOB_CACHE_MAX = 256
_COMPLETED_JOB_TTL_SEC = 3600.0


def validation_jobs_root(settings: Settings) -> Path:
    raw = (settings.validation_jobs_directory or "").strip()
    base = Path(raw).expanduser() if raw else Path(tempfile.gettempdir()) / "pegasus_validation_jobs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def resolve_history_mismatch_artifact(settings: Settings, run) -> Path | None:
    """Locate on-disk mismatch NDJSON for a persisted run (DB may be empty or capped)."""
    from pegasus.schemas.validation import parse_stored_footer_blob

    footer_raw = run.footer_validation if isinstance(run.footer_validation, dict) else None
    _, persistence = parse_stored_footer_blob(footer_raw)
    if persistence and persistence.mismatch_artifact_path:
        artifact = Path(str(persistence.mismatch_artifact_path)).expanduser()
        if artifact.is_file():
            return artifact

    job_roots: list[Path] = []
    if persistence and getattr(persistence, "validation_job_id", None):
        job_roots.append(validation_jobs_root(settings) / str(persistence.validation_job_id))
    found = find_job_dir_for_run(settings, run.id)
    if found is not None:
        job_roots.append(found)
    job_roots.append(validation_jobs_root(settings) / str(run.id))

    for job_dir in job_roots:
        if not job_dir.is_dir():
            continue
        try:
            result = loads_str((job_dir / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            result = {}
        resolved = resolve_job_mismatch_artifact(job_dir, result)
        if resolved is not None and _artifact_has_rows(resolved):
            return resolved
        fallback = job_dir / "mismatches.ndjson"
        if _artifact_has_rows(fallback):
            return fallback

    return None


def mismatch_totals_from_run(run) -> dict[str, int]:
    """Aggregate mismatch counts stored on a validation run row."""
    return {
        MismatchType.MISSING_IN_TARGET.value: int(run.missing_in_target_count or 0),
        MismatchType.EXTRA_IN_TARGET.value: int(run.extra_in_target_count or 0),
        MismatchType.VALUE_MISMATCH.value: int(run.value_mismatch_count or 0),
    }


def completed_job_cache_get(job_id: uuid.UUID) -> ValidationJobDetailResponse | None:
    now = time.time()
    with _completed_job_lock:
        while len(_completed_job_cache) > _COMPLETED_JOB_CACHE_MAX:
            _completed_job_cache.popitem(last=False)
        hit = _completed_job_cache.get(job_id)
        if not hit:
            return None
        t0, resp = hit
        if now - t0 > _COMPLETED_JOB_TTL_SEC:
            del _completed_job_cache[job_id]
            return None
        _completed_job_cache.move_to_end(job_id)
        return resp.model_copy(deep=True)


def completed_job_cache_put(job_id: uuid.UUID, resp: ValidationJobDetailResponse) -> None:
    with _completed_job_lock:
        _completed_job_cache[job_id] = (time.time(), resp.model_copy(deep=True))
        _completed_job_cache.move_to_end(job_id)
        while len(_completed_job_cache) > _COMPLETED_JOB_CACHE_MAX:
            _completed_job_cache.popitem(last=False)


def durations_from_result_json(res: dict[str, object]) -> ValidationRunDurations | None:
    raw = res.get("durations")
    if not isinstance(raw, dict):
        return None
    return ValidationRunDurations(
        upload_seconds=float(raw["upload_seconds"]) if raw.get("upload_seconds") is not None else None,
        validation_seconds=float(raw["validation_seconds"]) if raw.get("validation_seconds") is not None else None,
        total_seconds=float(raw["total_seconds"]) if raw.get("total_seconds") is not None else None,
    )


def find_job_dir_for_run(settings: Settings, run_id: uuid.UUID) -> Path | None:
    """Locate a validation job directory by persisted ``run_id`` in ``meta.json``."""
    root = validation_jobs_root(settings)
    if not root.is_dir():
        return None
    target = str(run_id)
    for child in root.iterdir():
        if not child.is_dir():
            continue
        meta_path = child / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = loads_str(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if str(meta.get("run_id") or "") == target:
            return child
    return None


def run_result_from_job_dir(job_dir: Path) -> tuple[ValidationRunResult, uuid.UUID | None, dict[str, object]]:
    meta = loads_str((job_dir / "meta.json").read_text(encoding="utf-8"))
    res = loads_str((job_dir / "result.json").read_text(encoding="utf-8"))
    rid = meta.get("run_id")
    run_uuid = uuid.UUID(str(rid)) if rid else None
    apath = resolve_job_mismatch_artifact(job_dir, res)
    summary = normalize_mismatch_summary(res.get("summary"))
    if apath is not None and apath.is_file():
        import polars as pl

        from pegasus.validation.comparators.models import MISMATCH_REPORT_SCHEMA, empty_mismatch_frame

        try:
            mismatches = pl.read_ndjson(str(apath), schema=MISMATCH_REPORT_SCHEMA)
        except Exception:
            logger.warning("Could not load mismatch NDJSON from %s", apath, exc_info=True)
            mismatches = empty_mismatch_frame()
    else:
        from pegasus.validation.comparators.models import empty_mismatch_frame

        mismatches = empty_mismatch_frame()
    report = MismatchReport(mismatches=mismatches, summary=summary, mismatch_artifact_path=apath)
    format_checks_raw = res.get("mapping_format_checks")
    footer_raw = res.get("footer_validation")
    vr = ValidationRunResult(
        report=report,
        source_row_count=int(res["source_row_count"]),
        target_row_count=int(res["target_row_count"]),
        compared_column_count=int(res["compared_column_count"]),
        compared_columns=list(res.get("compared_columns") or []),
        mismatch_artifact_path=apath,
        mapping_format_checks=list(format_checks_raw) if format_checks_raw else None,
        footer_validation=dict(footer_raw) if isinstance(footer_raw, dict) else None,
        test_mode=str(res.get("test_mode") or "full"),
        mismatch_snippet_limit=(
            int(res["mismatch_snippet_limit"])
            if res.get("mismatch_snippet_limit") is not None
            else None
        ),
        litmus=dict(res.get("litmus")) if isinstance(res.get("litmus"), dict) else None,
        durations=durations_from_result_json(res),
    )
    return vr, run_uuid, meta


def _validation_is_match(
    summary_dict: dict,
    total_records: int,
    *,
    run_result: ValidationRunResult | None = None,
) -> bool:
    if run_result is None:
        return validation_run_is_match(summary_dict, total_mismatch_records=total_records)
    return validation_run_is_match(
        summary_dict,
        total_mismatch_records=total_records,
        test_mode=run_result.test_mode,
        source_row_count=run_result.source_row_count,
        target_row_count=run_result.target_row_count,
    )


def build_validate_response_summary_only(
    *,
    run_result: ValidationRunResult,
    run_id: uuid.UUID | None,
) -> ValidateResponse:
    """Fast poll payload: counts and metadata only (no NDJSON scan)."""
    summary_dict = normalize_mismatch_summary(run_result.report.summary)
    counts_model = build_mismatch_counts(summary_dict)
    total_records = (
        counts_model.missing_in_target + counts_model.extra_in_target + counts_model.value_mismatch
    )

    summary = ValidationSummary(
        source_row_count=run_result.source_row_count,
        target_row_count=run_result.target_row_count,
        compared_column_count=run_result.compared_column_count,
        total_mismatch_records=total_records,
        is_match=_validation_is_match(summary_dict, total_records, run_result=run_result),
    )

    format_checks = [
        ColumnMappingFormatCheck.model_validate(c)
        for c in (run_result.mapping_format_checks or [])
    ]
    footer_val, _ = parse_stored_footer_blob(run_result.footer_validation)

    api_durations = None
    if run_result.durations is not None:
        api_durations = ValidationDurations(
            upload_seconds=run_result.durations.upload_seconds,
            validation_seconds=run_result.durations.validation_seconds,
            total_seconds=run_result.durations.total_seconds,
        )

    try:
        response_test_mode = ValidationTestMode(str(run_result.test_mode or "full"))
    except ValueError:
        response_test_mode = ValidationTestMode.FULL

    return ValidateResponse(
        summary=summary,
        mismatch_counts=counts_model,
        mismatch_sample_groups=MismatchSampleGroups(),
        value_mismatch_by_column={},
        compared_columns=run_result.compared_columns,
        run_id=run_id,
        value_mismatch_by_column_omitted=counts_model.value_mismatch > 0,
        mapping_format_checks=format_checks,
        footer_validation=footer_val,
        durations=api_durations,
        test_mode=response_test_mode,
        litmus=run_result.litmus,
    )


def resolve_job_mismatch_artifact(job_dir: Path, res: dict[str, object]) -> Path | None:
    """Resolve the on-disk mismatch NDJSON for a completed job directory."""
    artifact_raw = res.get("mismatch_artifact_path")
    if isinstance(artifact_raw, str) and artifact_raw.strip():
        cand = Path(artifact_raw.strip()).expanduser()
        if not cand.is_absolute():
            cand = job_dir / cand
        if cand.is_file() and cand.stat().st_size > 0:
            return cand
    rel = res.get("mismatch_artifact_rel")
    if isinstance(rel, str) and rel.strip():
        cand = job_dir / rel.strip()
        if cand.is_file() and cand.stat().st_size > 0:
            return cand
    for rel_path in (
        "mismatches.ndjson",
        "reconcile_workspace/mismatches_partial.ndjson",
    ):
        fallback = job_dir / rel_path
        if fallback.is_file() and fallback.stat().st_size > 0:
            return fallback
    return None


def _artifact_has_rows(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def refresh_run_result_for_persist(
    settings: Settings,
    run_result: ValidationRunResult,
    job_meta: dict[str, object] | None,
    run_id: uuid.UUID | None,
) -> tuple[ValidationRunResult, dict[str, object] | None]:
    """Re-read job artifacts so persistence sees on-disk mismatch NDJSON."""
    job_dirs: list[Path] = []
    job_id = (job_meta or {}).get("job_id")
    if job_id:
        job_dirs.append(validation_jobs_root(settings) / str(job_id))
    if run_id is not None:
        found = find_job_dir_for_run(settings, run_id)
        if found is not None:
            job_dirs.append(found)
    for job_dir in job_dirs:
        if not job_dir.is_dir():
            continue
        try:
            fresh, _, meta = run_result_from_job_dir(job_dir)
        except (OSError, ValueError, TypeError):
            logger.warning("Could not reload validation result from %s", job_dir, exc_info=True)
            continue
        artifact = fresh.mismatch_artifact_path or fresh.report.mismatch_artifact_path
        if (artifact is not None and Path(artifact).is_file()) or fresh.report.mismatches.height > 0:
            merged_meta = dict(job_meta or {})
            merged_meta.update(meta)
            return fresh, merged_meta
    return run_result, job_meta


def paginate_job_mismatch_rows(
    job_dir: Path,
    *,
    limit: int,
    offset: int,
    mismatch_type: str | None = None,
) -> tuple[list[dict[str, Any]], int, uuid.UUID | None]:
    """Paginated mismatch rows from a job's NDJSON artifact."""
    res = loads_str((job_dir / "result.json").read_text(encoding="utf-8"))
    meta = loads_str((job_dir / "meta.json").read_text(encoding="utf-8"))
    rid = meta.get("run_id")
    run_uuid = uuid.UUID(str(rid)) if rid else None
    artifact = resolve_job_mismatch_artifact(job_dir, res)
    totals = normalize_mismatch_summary(res.get("summary"))
    if artifact is None:
        return [], int(sum(totals.values()) if not mismatch_type else totals.get(mismatch_type or "", 0)), run_uuid
    return (
        *paginate_mismatch_rows_from_ndjson(
            artifact,
            limit=limit,
            offset=offset,
            mismatch_type=mismatch_type,
            totals_by_type=totals,
        ),
        run_uuid,
    )


_persist_scheduled: set[uuid.UUID] = set()
_persist_lock = threading.Lock()


def schedule_persist_completed_job(
    settings: Settings,
    *,
    run_id: uuid.UUID | None,
    run_result: ValidationRunResult,
    job_meta: dict[str, object] | None,
) -> None:
    """Persist mismatch rows in the background so summary-only polls stay fast."""
    if not settings.enable_validation_persistence or run_id is None:
        return
    with _persist_lock:
        if run_id in _persist_scheduled:
            return
        _persist_scheduled.add(run_id)

    import asyncio

    async def _persist() -> None:
        try:
            fresh_result, fresh_meta = refresh_run_result_for_persist(
                settings,
                run_result,
                job_meta,
                run_id,
            )
            await maybe_persist_completed_job(
                settings,
                run_id=run_id,
                run_result=fresh_result,
                job_meta=fresh_meta,
            )
        except Exception:
            logger.exception("Background mismatch persistence failed for run %s", run_id)
            with _persist_lock:
                _persist_scheduled.discard(run_id)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_persist())


def resolve_response_sample_caps(
    settings: Settings,
    run_result: ValidationRunResult,
) -> tuple[int, int, int | None]:
    """Return (presence_cap, value_sample_limit, value_per_column_limit) for API snippets."""
    mode = normalize_test_mode(run_result.test_mode or ValidationTestMode.FULL.value)
    if mode == ValidationTestMode.LITMUS:
        return 0, 0, None
    cap = clamp_snippet_limit(settings, requested=run_result.mismatch_snippet_limit)
    return cap, 0, cap


def build_validate_response(
    *,
    settings: Settings,
    run_result: ValidationRunResult,
    run_id: uuid.UUID | None,
) -> ValidateResponse:
    """Turn a :class:`ValidationRunResult` into API JSON."""
    artifact = run_result.mismatch_artifact_path or run_result.report.mismatch_artifact_path
    summary_dict = reconcile_summary_with_artifact(run_result.report.summary, artifact)
    counts_model = build_mismatch_counts(summary_dict)
    total_records = (
        counts_model.missing_in_target + counts_model.extra_in_target + counts_model.value_mismatch
    )

    presence_cap, sample_limit, value_per_column_limit = resolve_response_sample_caps(
        settings,
        run_result,
    )
    category_counts = (
        counts_model.missing_in_target,
        counts_model.extra_in_target,
        counts_model.value_mismatch,
    )

    mismatch_stats_frame = run_result.report.mismatches
    if str(run_result.test_mode or "").strip().lower() == ValidationTestMode.LITMUS.value:
        sample_groups = MismatchSampleGroups()
    elif artifact is not None and artifact.is_file() and total_records > 0:
        miss_rows, ext_rows = stream_presence_mismatch_rows_from_ndjson(
            artifact,
            n_miss=counts_model.missing_in_target,
            n_ext=counts_model.extra_in_target,
            presence_max_rows=presence_cap,
        )
        if value_per_column_limit is not None and value_per_column_limit > 0:
            val_df = load_per_column_value_mismatch_sample_from_ndjson(
                artifact,
                n_val=counts_model.value_mismatch,
                per_column_limit=value_per_column_limit,
            )
            val_rows = val_df.to_dicts()
        elif sample_limit <= 0:
            val_n = counts_model.value_mismatch
            if val_n <= 0:
                val_n = count_mismatch_types_ndjson(artifact).get(MismatchType.VALUE_MISMATCH.value, 0)
            val_rows = stream_all_value_mismatch_rows_from_ndjson(
                artifact,
                n_val=val_n,
            )
        else:
            val_df = load_value_mismatch_sample_from_ndjson(
                artifact,
                n_val=counts_model.value_mismatch,
                value_sample_limit=sample_limit,
            )
            val_rows = val_df.to_dicts()
        sample_groups = MismatchSampleGroups(
            missing_in_target=miss_rows,
            extra_in_target=ext_rows,
            value_mismatch=val_rows,
        )
    elif total_records > 0:
        mismatch_stats_frame = load_mismatch_polars_for_api(
            mismatches=run_result.report.mismatches,
            mismatch_artifact_path=None,
            n_rows=None,
        )
        miss_df, ext_df, val_df = build_grouped_mismatch_samples(
            mismatch_stats_frame,
            sample_limit,
            category_counts=category_counts,
            presence_max_rows=presence_cap if presence_cap > 0 else None,
            value_per_column_limit=value_per_column_limit,
        )
        sample_groups = MismatchSampleGroups(
            missing_in_target=miss_df.to_dicts(),
            extra_in_target=ext_df.to_dicts(),
            value_mismatch=val_df.to_dicts(),
        )
    else:
        sample_groups = MismatchSampleGroups()

    cap = settings.validation_value_mismatch_column_stats_max_rows
    val_n = counts_model.value_mismatch
    if cap == 0 or val_n <= cap:
        if artifact is not None and artifact.is_file():
            value_by_col = value_mismatch_counts_by_column_ndjson(artifact, max_rows=None)
        else:
            value_by_col = value_mismatch_counts_by_column(mismatch_stats_frame, max_rows=None)
        vm_omitted = False
    else:
        if artifact is not None and artifact.is_file():
            value_by_col = value_mismatch_counts_by_column_ndjson(artifact, max_rows=cap)
        else:
            value_by_col = value_mismatch_counts_by_column(mismatch_stats_frame, max_rows=cap)
        vm_omitted = value_by_col == {} and val_n > cap

    run_result.report.mismatches = empty_mismatch_frame()
    gc.collect()

    summary = ValidationSummary(
        source_row_count=run_result.source_row_count,
        target_row_count=run_result.target_row_count,
        compared_column_count=run_result.compared_column_count,
        total_mismatch_records=total_records,
        is_match=_validation_is_match(summary_dict, total_records, run_result=run_result),
    )

    format_checks = [
        ColumnMappingFormatCheck.model_validate(c)
        for c in (run_result.mapping_format_checks or [])
    ]
    footer_val, _ = parse_stored_footer_blob(run_result.footer_validation)

    api_durations = None
    if run_result.durations is not None:
        api_durations = ValidationDurations(
            upload_seconds=run_result.durations.upload_seconds,
            validation_seconds=run_result.durations.validation_seconds,
            total_seconds=run_result.durations.total_seconds,
        )

    try:
        response_test_mode = ValidationTestMode(str(run_result.test_mode or "full"))
    except ValueError:
        response_test_mode = ValidationTestMode.FULL

    return ValidateResponse(
        summary=summary,
        mismatch_counts=counts_model,
        mismatch_sample_groups=sample_groups,
        value_mismatch_by_column=value_by_col,
        compared_columns=run_result.compared_columns,
        run_id=run_id,
        value_mismatch_by_column_omitted=vm_omitted,
        mapping_format_checks=format_checks,
        footer_validation=footer_val,
        durations=api_durations,
        test_mode=response_test_mode,
        litmus=run_result.litmus,
    )


def record_poll_lifecycle(
    job_dir: Path,
    *,
    database_wall_seconds: float = 0.0,
    response_build_wall_seconds: float = 0.0,
) -> None:
    """Stamp HTTP response epoch and API-side stages onto the worker lifecycle file."""
    from pegasus.core.json_util import loads_str
    from pegasus.validation.lifecycle_profiler import LifecycleProfiler

    lifecycle_path = job_dir / "lifecycle_timings.json"
    profiler = LifecycleProfiler(job_dir=job_dir)
    if lifecycle_path.is_file():
        try:
            prior = loads_str(lifecycle_path.read_text(encoding="utf-8"))
            raw_epochs = prior.get("epochs") if isinstance(prior, dict) else None
            if isinstance(raw_epochs, dict):
                for key in (
                    "http_request_start_epoch_s",
                    "job_enqueued_epoch_s",
                    "worker_started_epoch_s",
                    "validation_started_epoch_s",
                    "worker_finished_epoch_s",
                ):
                    value = raw_epochs.get(key)
                    if isinstance(value, (int, float)):
                        setattr(profiler, key, float(value))
            for raw_stage in list(prior.get("stages") or []) if isinstance(prior, dict) else []:
                if not isinstance(raw_stage, dict):
                    continue
                name = str(raw_stage.get("name") or "")
                if not name:
                    continue
                profiler.record(
                    name,
                    wall_seconds=float(raw_stage.get("wall_seconds") or 0),
                    cpu_seconds=float(raw_stage.get("cpu_seconds") or 0),
                    bytes_read=int(raw_stage.get("bytes_read") or 0),
                    bytes_written=int(raw_stage.get("bytes_written") or 0),
                    accumulate=False,
                )
        except (OSError, ValueError, TypeError):
            pass
    if database_wall_seconds > 0:
        profiler.record("Database Updates", wall_seconds=database_wall_seconds, accumulate=False)
    if response_build_wall_seconds > 0:
        profiler.record(
            "HTTP Response",
            wall_seconds=response_build_wall_seconds,
            accumulate=False,
        )
    profiler.mark_http_response()
    profiler.write_artifacts()


async def maybe_persist_completed_job(
    settings: Settings,
    *,
    run_id: uuid.UUID | None,
    run_result: ValidationRunResult,
    job_meta: dict[str, object] | None = None,
) -> float:
    """Persist run results; return wall seconds spent in DB (0 when skipped)."""
    if not settings.enable_validation_persistence or run_id is None:
        return 0.0
    import time

    run_result, job_meta = refresh_run_result_for_persist(
        settings,
        run_result,
        job_meta,
        run_id,
    )
    t0 = time.perf_counter()
    mappings_raw = list((job_meta or {}).get("column_mappings") or [])
    column_mappings = [m for m in mappings_raw if isinstance(m, dict)]
    async with AsyncSessionLocal() as session:
        run = await ValidationRunRepository.get_run(session, run_id)
        if run is None:
            return 0.0
        stored_rows = await ValidationRunRepository.count_mismatch_reports(session, run_id)
        expected_rows = mismatch_record_total(mismatch_totals_from_run(run))
        needs_backfill = (
            run.status == ValidationRunStatus.COMPLETED
            and stored_rows == 0
            and expected_rows > 0
        )
        if run.status == ValidationRunStatus.COMPLETED and not needs_backfill:
            return 0.0
        if run.status not in (ValidationRunStatus.RUNNING, ValidationRunStatus.COMPLETED):
            return 0.0
        from pegasus.validation.test_mode_policy import resolve_mismatch_collection_policy

        collection_policy = resolve_mismatch_collection_policy(
            settings,
            test_mode=str(run_result.test_mode or "full"),
            mismatch_snippet_limit=run_result.mismatch_snippet_limit,
            compare_column_count=len(run_result.compared_columns or []),
        )
        persist_cap = (
            collection_policy.persistence_row_cap
            if collection_policy.persistence_row_cap > 0
            else settings.validation_persistence_max_mismatch_rows
        )
        await ValidationRunRepository.complete_success(
            session,
            run_id,
            run_result,
            column_mappings=column_mappings or None,
            max_mismatch_rows=persist_cap,
            job_meta=job_meta,
        )
        await session.commit()
    return time.perf_counter() - t0


async def backfill_mismatch_rows_for_run(
    settings: Settings,
    run_id: uuid.UUID,
) -> bool:
    """Insert mismatch rows when a completed run has counts but no stored snippet rows."""
    if not settings.enable_validation_persistence:
        return False
    async with AsyncSessionLocal() as session:
        run = await ValidationRunRepository.get_run(session, run_id)
        if run is None:
            return False
        if await ValidationRunRepository.count_mismatch_reports(session, run_id) > 0:
            return False
        if mismatch_record_total(mismatch_totals_from_run(run)) <= 0:
            return False
    job_dir = find_job_dir_for_run(settings, run_id)
    if job_dir is None:
        return False
    try:
        workspace = job_dir / "reconcile_workspace"
        export_path = job_dir / "mismatches.ndjson"
        result_json = loads_str((job_dir / "result.json").read_text(encoding="utf-8"))
        compared_cols = list(result_json.get("compared_columns") or [])
        if (
            workspace.is_dir()
            and compared_cols
            and (not export_path.is_file() or export_path.stat().st_size == 0)
        ):
            from pegasus.validation.pipeline.mismatch_export import export_workspace_mismatches_ndjson

            export_workspace_mismatches_ndjson(
                workspace,
                export_path,
                compare_columns=compared_cols,
            )
        run_result, _, job_meta = run_result_from_job_dir(job_dir)
    except (OSError, ValueError, TypeError):
        logger.warning("Could not load job artifacts for run %s from %s", run_id, job_dir, exc_info=True)
        return False
    artifact = run_result.mismatch_artifact_path or run_result.report.mismatch_artifact_path
    if (artifact is None or not Path(artifact).is_file()) and run_result.report.mismatches.height <= 0:
        return False
    await maybe_persist_completed_job(
        settings,
        run_id=run_id,
        run_result=run_result,
        job_meta=job_meta,
    )
    async with AsyncSessionLocal() as session:
        return await ValidationRunRepository.count_mismatch_reports(session, run_id) > 0

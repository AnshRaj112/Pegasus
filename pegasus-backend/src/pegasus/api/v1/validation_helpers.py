# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T15:00:33+05:30
# --- END GENERATED FILE METADATA ---

"""Shared helpers for validation API endpoints and job polling."""

from __future__ import annotations

import gc
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

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
)
from pegasus.services.validation_results import ValidationRunDurations, ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame

from .mismatch_sample import (
    build_grouped_mismatch_samples,
    load_mismatch_polars_for_api,
    load_value_mismatch_sample_from_ndjson,
    stream_all_value_mismatch_rows_from_ndjson,
    stream_presence_mismatch_rows_from_ndjson,
    value_mismatch_counts_by_column,
    value_mismatch_counts_by_column_ndjson,
)

_completed_job_cache: OrderedDict[uuid.UUID, tuple[float, ValidationJobDetailResponse]] = OrderedDict()
_completed_job_lock = threading.Lock()
_COMPLETED_JOB_CACHE_MAX = 256
_COMPLETED_JOB_TTL_SEC = 120.0


def validation_jobs_root(settings: Settings) -> Path:
    raw = (settings.validation_jobs_directory or "").strip()
    base = Path(raw).expanduser() if raw else Path(tempfile.gettempdir()) / "pegasus_validation_jobs"
    base.mkdir(parents=True, exist_ok=True)
    return base


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


def run_result_from_job_dir(job_dir: Path) -> tuple[ValidationRunResult, uuid.UUID | None, dict[str, object]]:
    meta = loads_str((job_dir / "meta.json").read_text(encoding="utf-8"))
    res = loads_str((job_dir / "result.json").read_text(encoding="utf-8"))
    rid = meta.get("run_id")
    run_uuid = uuid.UUID(str(rid)) if rid else None
    summary_raw = res.get("summary") or {}
    summary = {
        MismatchType.MISSING_IN_TARGET.value: int(summary_raw.get(MismatchType.MISSING_IN_TARGET.value, 0)),
        MismatchType.EXTRA_IN_TARGET.value: int(summary_raw.get(MismatchType.EXTRA_IN_TARGET.value, 0)),
        MismatchType.VALUE_MISMATCH.value: int(summary_raw.get(MismatchType.VALUE_MISMATCH.value, 0)),
    }
    apath = None
    artifact_raw = res.get("mismatch_artifact_path")
    if isinstance(artifact_raw, str) and artifact_raw.strip():
        cand = Path(artifact_raw.strip()).expanduser()
        if not cand.is_absolute():
            cand = job_dir / cand
        if cand.is_file():
            apath = cand
    if apath is None:
        rel = res.get("mismatch_artifact_rel")
        if isinstance(rel, str) and rel.strip():
            cand = job_dir / rel.strip()
            if cand.is_file():
                apath = cand
    report = MismatchReport(mismatches=empty_mismatch_frame(), summary=summary, mismatch_artifact_path=apath)
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
        litmus=dict(res.get("litmus")) if isinstance(res.get("litmus"), dict) else None,
        durations=durations_from_result_json(res),
    )
    return vr, run_uuid, meta


def build_validate_response(
    *,
    settings: Settings,
    run_result: ValidationRunResult,
    run_id: uuid.UUID | None,
) -> ValidateResponse:
    """Turn a :class:`ValidationRunResult` into API JSON."""
    summary_dict = run_result.report.summary
    counts_model = build_mismatch_counts(summary_dict)
    total_records = (
        counts_model.missing_in_target + counts_model.extra_in_target + counts_model.value_mismatch
    )

    artifact = run_result.mismatch_artifact_path or run_result.report.mismatch_artifact_path
    presence_cap = settings.validation_presence_mismatch_response_max_rows
    raw_sample_limit = settings.validation_mismatch_sample_limit
    sample_limit = raw_sample_limit if raw_sample_limit > 0 else 0
    category_counts = (
        counts_model.missing_in_target,
        counts_model.extra_in_target,
        counts_model.value_mismatch,
    )

    mismatch_stats_frame = run_result.report.mismatches
    if artifact is not None and artifact.is_file() and total_records > 0:
        miss_rows, ext_rows = stream_presence_mismatch_rows_from_ndjson(
            artifact,
            n_miss=counts_model.missing_in_target,
            n_ext=counts_model.extra_in_target,
            presence_max_rows=presence_cap,
        )
        if sample_limit <= 0:
            val_rows = stream_all_value_mismatch_rows_from_ndjson(
                artifact,
                n_val=counts_model.value_mismatch,
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
            presence_max_rows=presence_cap,
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
        is_match=total_records == 0,
    )

    format_checks = [
        ColumnMappingFormatCheck.model_validate(c)
        for c in (run_result.mapping_format_checks or [])
    ]
    footer_val = (
        FooterValidationResult.model_validate(run_result.footer_validation)
        if run_result.footer_validation
        else None
    )

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

    t0 = time.perf_counter()
    mappings_raw = list((job_meta or {}).get("column_mappings") or [])
    column_mappings = [m for m in mappings_raw if isinstance(m, dict)]
    async with AsyncSessionLocal() as session:
        run = await ValidationRunRepository.get_run(session, run_id)
        if run is None or run.status != ValidationRunStatus.RUNNING:
            return 0.0
        await ValidationRunRepository.complete_success(
            session,
            run_id,
            run_result,
            column_mappings=column_mappings or None,
        )
        await session.commit()
    return time.perf_counter() - t0

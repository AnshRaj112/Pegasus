"""CSV validation endpoint (UID-based comparison)."""

from __future__ import annotations

import json
import gc
import logging
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile, status

from pegasus.api.deps import AppSettings, ValidationServiceDep
from pegasus.core.config import Settings
from pegasus.core.database import AsyncSessionLocal
from pegasus.core.local_paths import (
    compute_file_pair_key_for_settings,
    default_browse_path,
    default_browse_path_for_ui,
    local_path_remap,
    resolve_local_path_on_disk,
    to_display_path,
)
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.models.enums import ValidationRunStatus
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.schemas.validation import (
    BatchFailureMode,
    BatchUnitResult,
    BatchValidateResponse,
    BatchValidateSummary,
    ColumnMappingFormatCheck,
    FilePairMatch,
    FooterValidationResult,
    GoogleCloudStorageConfig,
    LocalBatchValidateRequest,
    LocalBrowseEntry,
    LocalBrowseResponse,
    LocalPathBrowseConfigResponse,
    FixedWidthLayoutPreviewResponse,
    LocalColumnPreviewResponse,
    LocalPathValidateRequest,
    MappingAnalyzeRequest,
    MappingAnalyzeResponse,
    MatchFilePairsRequest,
    MatchFilePairsResponse,
    CloudBrowseRequest,
    CloudBrowseResponse,
    CloudBrowseEntry,
    CloudMatchFilePairsRequest,
    MismatchSampleGroups,
    QueueStatusResponse,
    UpdateQueueSettingsRequest,
    ValidateResponse,
    ValidationDurations,
    ValidationJobAcceptedResponse,
    ValidationJobDetailResponse,
    ValidationSummary,
    ValidationTestMode,
    build_mismatch_counts,
)
from pegasus.services.validation_job_queue import get_validation_queue
from pegasus.services.exceptions import ValidationBadRequestError, format_validation_job_error
from pegasus.services.validation_service import ValidationRunDurations, ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame
from pegasus.validation.delimiter_tokens import (
    FIXED_WIDTH_DELIMITER,
    JSON_DELIMITER,
    normalize_delimiter_for_storage,
)
from pegasus.validation.fixed_width_meta import (
    coerce_local_validate_fields,
    is_fixed_width_run,
    is_json_run,
)
from pegasus.validation.file_pairing import auto_match_files_by_name, list_files_in_directory
from pegasus.validation.gcs_browse import browse_gcs_prefix, list_gcs_files_under_prefix

from .mismatch_sample import (
    build_grouped_mismatch_samples,
    load_mismatch_polars_for_api,
    load_value_mismatch_sample_from_ndjson,
    stream_all_value_mismatch_rows_from_ndjson,
    stream_presence_mismatch_rows_from_ndjson,
    value_mismatch_counts_by_column,
    value_mismatch_counts_by_column_ndjson,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validation"])

_completed_job_cache: OrderedDict[uuid.UUID, tuple[float, ValidationJobDetailResponse]] = OrderedDict()
_completed_job_lock = threading.Lock()
_COMPLETED_JOB_CACHE_MAX = 256
_COMPLETED_JOB_TTL_SEC = 120.0


def _completed_job_cache_get(job_id: uuid.UUID) -> ValidationJobDetailResponse | None:
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


def _completed_job_cache_put(job_id: uuid.UUID, resp: ValidationJobDetailResponse) -> None:
    with _completed_job_lock:
        _completed_job_cache[job_id] = (time.time(), resp.model_copy(deep=True))
        _completed_job_cache.move_to_end(job_id)
        while len(_completed_job_cache) > _COMPLETED_JOB_CACHE_MAX:
            _completed_job_cache.popitem(last=False)

_DEFAULT_UPLOAD_SUFFIX = ".csv"
# Larger reads reduce asyncio/Starlette overhead on huge uploads.
_UPLOAD_READ_CHUNK_BYTES = 8 * 1024 * 1024
# Avoid rewriting status.json on every megabyte (was thrashing disk on 100GB+ runs).
_UPLOAD_STATUS_EMIT_BYTES = 16 * 1024 * 1024


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(dumps_bytes(payload, indent=False))
    tmp.replace(path)


_LOCAL_BROWSE_MAX_ENTRIES = 5000


def _require_local_path_access(settings: Settings) -> None:
    if not settings.validation_allow_local_paths:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Local path validation is disabled (set PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS=true).",
        )


def resolve_local_csv_path(raw: str, settings: Settings) -> Path:
    """Resolve *raw* to an absolute file path on the server (when local paths are enabled)."""
    _require_local_path_access(settings)
    return resolve_local_path_on_disk(raw, settings, must_be_file=True)


@dataclass(slots=True)
class ResolvedValidationInput:
    path: Path
    cleanup_path: Path | None
    display_name: str


def _resolve_cloud_credentials(raw_json: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cloud credential payload must be valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cloud credential payload must be a JSON object",
        )
    return parsed


def _download_gcs_object_to_path(
    cloud: GoogleCloudStorageConfig,
    dest_path: Path,
) -> Path:
    try:
        from google.cloud import storage as gcs_storage
        from google.oauth2 import service_account
    except ImportError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google-cloud-storage is required for cloud validation inputs",
        ) from exc

    info = _resolve_cloud_credentials(cloud.credentials_json)
    try:
        credentials = service_account.Credentials.from_service_account_info(info)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google Cloud service account JSON: {exc}",
        ) from exc

    bucket_name = cloud.bucket.strip()
    object_name = cloud.object_name.strip()
    if not bucket_name or not object_name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cloud bucket and object_name are required",
        )

    try:
        project_id = cloud.project_id or info.get("project_id")
        client = gcs_storage.Client(credentials=credentials, project=project_id)
        blob = client.bucket(bucket_name).blob(object_name)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest_path))
        return dest_path
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download gs://{bucket_name}/{object_name}: {exc}",
        ) from exc


def resolve_validation_input(
    *,
    settings: Settings,
    label: str,
    path: str | None = None,
    cloud: GoogleCloudStorageConfig | None = None,
    destination_path: Path | None = None,
) -> ResolvedValidationInput:
    """Resolve either a local path or a cloud object into a concrete CSV path."""
    if cloud is not None:
        suffix = Path(cloud.object_name or "").suffix or _DEFAULT_UPLOAD_SUFFIX
        if destination_path is None:
            fd, tmp_path = tempfile.mkstemp(prefix=f"pegasus_{label}_cloud_", suffix=suffix)
            os.close(fd)
            dest = Path(tmp_path)
            cleanup = dest
        else:
            dest = destination_path
            cleanup = None
        download_path = _download_gcs_object_to_path(cloud, dest)
        return ResolvedValidationInput(
            path=download_path,
            cleanup_path=cleanup,
            display_name=f"gs://{cloud.bucket.strip()}/{cloud.object_name.strip()}",
        )

    if path is None or not path.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"{label.capitalize()} path or cloud reference is required",
        )
    resolved = resolve_local_csv_path(path, settings)
    return ResolvedValidationInput(
        path=resolved,
        cleanup_path=None,
        display_name=Path(to_display_path(resolved, settings)).name or resolved.name,
    )


def resolve_local_dir_for_browse(raw: str, settings: Settings) -> Path:
    """Resolve *raw* to an absolute directory (for GET /validate/local/browse)."""
    _require_local_path_access(settings)
    return resolve_local_path_on_disk(raw, settings, must_be_dir=True)


def _browse_parent_path(current: Path) -> Path | None:
    parent = current.parent
    if parent == current:
        return None
    return parent


def build_local_browse_response(directory: Path, settings: Settings) -> LocalBrowseResponse:
    """List *directory* (already resolved)."""
    parent = _browse_parent_path(directory)
    rows: list[tuple[bool, str, Path, str]] = []
    truncated = False
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    child = Path(entry.path).resolve(strict=False)
                except OSError:
                    continue
                display_name = entry.name
                is_dir = child.is_dir()
                if not is_dir and not child.is_file():
                    continue
                rows.append((not is_dir, display_name.lower(), child, display_name))
    except OSError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cannot read directory: {exc}",
        ) from exc

    rows.sort(key=lambda t: (t[0], t[1]))
    if len(rows) > _LOCAL_BROWSE_MAX_ENTRIES:
        truncated = True
        rows = rows[:_LOCAL_BROWSE_MAX_ENTRIES]

    entries = [
        LocalBrowseEntry(
            name=display_name,
            path=to_display_path(p, settings),
            is_dir=p.is_dir(),
        )
        for _, _, p, display_name in rows
    ]
    return LocalBrowseResponse(
        path=to_display_path(directory, settings),
        parent_path=to_display_path(parent, settings) if parent is not None else None,
        entries=entries,
        truncated=truncated,
    )


def _build_validate_response(
    *,
    settings: Settings,
    run_result: ValidationRunResult,
    run_id: uuid.UUID | None,
) -> ValidateResponse:
    """Turn a :class:`ValidationRunResult` into API JSON; drops the large mismatch frame from memory."""
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
            # Avoid per-row pre-validation here; ValidateResponse model will validate once.
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


def _human_upload_limit(n: int) -> str:
    """Short human-readable size for error messages (binary units)."""
    gib = 1024**3
    if n >= gib and n % gib == 0:
        return f"{n // gib} GiB"
    if n >= gib:
        return f"{n / gib:.1f} GiB"
    mib = 1024**2
    if n >= mib:
        return f"{n / mib:.0f} MiB"
    return f"{n} bytes"


async def _spool_upload_to_temp(
    upload: UploadFile,
    *,
    max_bytes: int,
    label: str,
    on_progress=None,
    spool_dir: Path | None = None,
    read_chunk_size: int = _UPLOAD_READ_CHUNK_BYTES,
    progress_emit_min_bytes: int = _UPLOAD_STATUS_EMIT_BYTES,
) -> Path:
    """Stream upload to a temp file; enforce size limit.

    When *spool_dir* is set (e.g. the job directory on fast local disk), the temp file is created
    there so it can be promoted to ``source.csv`` / ``target.csv`` via ``os.replace`` without a
    full second copy across filesystems.
    """
    suffix = Path(upload.filename or _DEFAULT_UPLOAD_SUFFIX).suffix or _DEFAULT_UPLOAD_SUFFIX
    mk_kw: dict[str, str] = {"prefix": f"pegasus_{label}_", "suffix": suffix}
    if spool_dir is not None:
        spool_dir.mkdir(parents=True, exist_ok=True)
        mk_kw["dir"] = str(spool_dir)
    fd, path_str = tempfile.mkstemp(**mk_kw)
    path = Path(path_str)
    total = 0
    committed = False
    last_progress_emit_at = 0
    try:
        while True:
            chunk = await upload.read(read_chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if on_progress is not None and (total - last_progress_emit_at >= progress_emit_min_bytes):
                on_progress(total)
                last_progress_emit_at = total
            if total > max_bytes:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        f"{label} exceeds maximum upload size ({max_bytes} bytes, {_human_upload_limit(max_bytes)}). "
                        "Raise PEGASUS_VALIDATION_MAX_UPLOAD_BYTES in the API environment and restart."
                    ),
                )
            os.write(fd, chunk)
        if total == 0:
            raise ValidationBadRequestError(f"{label} is empty")
        committed = True
        if on_progress is not None:
            on_progress(total)
        return path
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        if not committed:
            path.unlink(missing_ok=True)


def _validation_jobs_root(settings: Settings) -> Path:
    raw = (settings.validation_jobs_directory or "").strip()
    base = Path(raw).expanduser() if raw else Path(tempfile.gettempdir()) / "pegasus_validation_jobs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _durations_from_result_json(res: dict[str, object]) -> ValidationRunDurations | None:
    raw = res.get("durations")
    if not isinstance(raw, dict):
        return None
    return ValidationRunDurations(
        upload_seconds=float(raw["upload_seconds"]) if raw.get("upload_seconds") is not None else None,
        validation_seconds=float(raw["validation_seconds"]) if raw.get("validation_seconds") is not None else None,
        total_seconds=float(raw["total_seconds"]) if raw.get("total_seconds") is not None else None,
    )


def _run_result_from_job_dir(job_dir: Path) -> tuple[ValidationRunResult, uuid.UUID | None, dict[str, object]]:
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
        durations=_durations_from_result_json(res),
    )
    return vr, run_uuid, meta


def _validate_response_from_unit_json(
    *,
    settings: Settings,
    job_dir: Path,
    unit_id: str,
    res: dict[str, object],
) -> ValidateResponse:
    """Build a ValidateResponse from a unit's stored result dict."""
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
            cand = job_dir / "units" / unit_id / cand
        if cand.is_file():
            apath = cand
    if apath is None:
        rel = res.get("mismatch_artifact_rel")
        if isinstance(rel, str) and rel.strip():
            cand = job_dir / "units" / unit_id / rel.strip()
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
        durations=None,
    )
    return _build_validate_response(settings=settings, run_result=vr, run_id=None)


def _build_batch_job_detail(
    *,
    settings: Settings,
    job_dir: Path,
    status_val: str,
    phase: str | None,
    message: str | None,
    progress: dict[str, object],
    error: str | None = None,
) -> ValidationJobDetailResponse:
    batch_path = job_dir / "batch_result.json"
    raw = loads_str(batch_path.read_text(encoding="utf-8"))
    summary_raw = raw.get("summary") or {}
    units_out: list[BatchUnitResult] = []
    for unit in list(raw.get("units") or []):
        if not isinstance(unit, dict):
            continue
        unit_id = str(unit.get("unit_id") or "")
        result_payload = None
        unit_result = unit.get("result")
        if isinstance(unit_result, dict):
            result_payload = _validate_response_from_unit_json(
                settings=settings,
                job_dir=job_dir,
                unit_id=unit_id,
                res=unit_result,
            )
        units_out.append(
            BatchUnitResult(
                unit_id=unit_id,
                source_paths=[str(p) for p in list(unit.get("source_paths") or [])],
                target_paths=[str(p) for p in list(unit.get("target_paths") or [])],
                status=str(unit.get("status") or "unknown"),
                error=str(unit.get("error")) if unit.get("error") else None,
                result=result_payload,
            )
        )
    durations_raw = raw.get("durations")
    durations = None
    if isinstance(durations_raw, dict):
        durations = ValidationDurations(
            validation_seconds=float(durations_raw["validation_seconds"])
            if durations_raw.get("validation_seconds") is not None
            else None,
            total_seconds=float(durations_raw["total_seconds"])
            if durations_raw.get("total_seconds") is not None
            else None,
        )
    on_failure_raw = str(raw.get("on_unit_failure") or BatchFailureMode.CONTINUE.value)
    try:
        on_failure = BatchFailureMode(on_failure_raw)
    except ValueError:
        on_failure = BatchFailureMode.CONTINUE
    batch_result = BatchValidateResponse(
        summary=BatchValidateSummary(
            total_units=int(summary_raw.get("total_units") or 0),
            completed_units=int(summary_raw.get("completed_units") or 0),
            failed_units=int(summary_raw.get("failed_units") or 0),
            skipped_units=int(summary_raw.get("skipped_units") or 0),
            passed_units=int(summary_raw.get("passed_units") or 0),
            is_match=bool(summary_raw.get("is_match")),
        ),
        units=units_out,
        on_unit_failure=on_failure,
        durations=durations,
    )
    return ValidationJobDetailResponse(
        status=status_val,
        phase=phase,
        message=message,
        progress=progress,
        error=error,
        batch_result=batch_result,
    )


async def _maybe_persist_completed_job(
    settings: Settings,
    *,
    run_id: uuid.UUID | None,
    run_result: ValidationRunResult,
    job_meta: dict[str, object] | None = None,
) -> None:
    if not settings.enable_validation_persistence or run_id is None:
        return
    mappings_raw = list((job_meta or {}).get("column_mappings") or [])
    column_mappings = [m for m in mappings_raw if isinstance(m, dict)]
    async with AsyncSessionLocal() as session:
        run = await ValidationRunRepository.get_run(session, run_id)
        if run is None or run.status != ValidationRunStatus.RUNNING:
            return
        await ValidationRunRepository.complete_success(
            session,
            run_id,
            run_result,
            column_mappings=column_mappings or None,
        )
        await session.commit()


@router.post(
    "/validate",
    response_model=ValidationJobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue comparison of two CSV files by UID (runs in a background subprocess)",
    responses={
        400: {"description": "Invalid files, delimiter, or missing uid column"},
        413: {"description": "Upload exceeds configured size limit"},
        422: {"description": "Comparison cannot run (e.g. duplicate UIDs)"},
    },
)
async def validate_csv_files(
    settings: AppSettings,
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
) -> ValidationJobAcceptedResponse:
    """Accept two CSV uploads, persist them under a job directory, and spawn a worker process."""
    max_bytes = settings.validation_max_upload_bytes
    job_id = uuid.uuid4()
    jobs_root = _validation_jobs_root(settings)
    job_dir = jobs_root / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)
    status_path = job_dir / "status.json"

    source_path: Path | None = None
    target_path: Path | None = None
    run_id: uuid.UUID | None = None

    try:
        _atomic_write_json(
            status_path,
            {
                "status": "running",
                "phase": "uploading",
                "message": "Uploading files to server scratch space",
                "progress": {
                    "source_uploaded_bytes": 0,
                    "target_uploaded_bytes": 0,
                    "source_total_hint_bytes": int(getattr(source_file, "size", 0) or 0),
                    "target_total_hint_bytes": int(getattr(target_file, "size", 0) or 0),
                },
            },
        )
        upload_start = time.time()
        source_path = await _spool_upload_to_temp(
            source_file,
            max_bytes=max_bytes,
            label="source",
            spool_dir=job_dir,
            on_progress=lambda n: _atomic_write_json(
                status_path,
                {
                    "status": "running",
                    "phase": "uploading",
                    "message": "Uploading source CSV",
                    "progress": {
                        "source_uploaded_bytes": int(n),
                        "target_uploaded_bytes": 0,
                        "source_total_hint_bytes": int(getattr(source_file, "size", 0) or 0),
                        "target_total_hint_bytes": int(getattr(target_file, "size", 0) or 0),
                    },
                },
            ),
        )
        target_path = await _spool_upload_to_temp(
            target_file,
            max_bytes=max_bytes,
            label="target",
            spool_dir=job_dir,
            on_progress=lambda n: _atomic_write_json(
                status_path,
                {
                    "status": "running",
                    "phase": "uploading",
                    "message": "Uploading target CSV",
                    "progress": {
                        "source_uploaded_bytes": int(source_path.stat().st_size if source_path is not None else 0),
                        "target_uploaded_bytes": int(n),
                        "source_total_hint_bytes": int(getattr(source_file, "size", 0) or 0),
                        "target_total_hint_bytes": int(getattr(target_file, "size", 0) or 0),
                    },
                },
            ),
        )
        upload_duration = time.time() - upload_start
        logger.info("Upload complete for job %s duration=%.2fs", job_id, upload_duration)

        if settings.enable_validation_persistence:
            try:
                async with AsyncSessionLocal() as session:
                    run_orm = await ValidationRunRepository.create_running(
                        session,
                        source_filename=source_file.filename,
                        target_filename=target_file.filename,
                        uid_column=uid_column.strip(),
                        delimiter=delimiter,
                        source_path=source_file.filename,
                        target_path=target_file.filename,
                    )
                    await session.commit()
                    run_id = run_orm.id
            except Exception as exc:
                logger.exception("Failed to create validation run record: %s", exc)
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not persist validation run; check database connectivity",
                ) from exc

        _atomic_write_json(
            status_path,
            {
                "status": "running",
                "phase": "staging",
                "message": "Promoting uploads to job workspace (rename)",
            },
        )
        dest_s = job_dir / "source.csv"
        dest_t = job_dir / "target.csv"
        os.replace(source_path, dest_s)
        os.replace(target_path, dest_t)

        meta = {
            "uid_column": uid_column.strip(),
            "delimiter": delimiter,
            "memory_log_interval_seconds": settings.validation_memory_log_interval_seconds,
            "run_id": str(run_id) if run_id else None,
            "upload_duration_seconds": upload_duration,
        }
        (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))

        # Enqueue into the concurrency-limited job queue
        queue = get_validation_queue(settings)
        queued_job = queue.enqueue(job_id, job_dir)
    except HTTPException:
        raise
    except Exception as exc:
        if run_id is not None:
            try:
                async with AsyncSessionLocal() as session:
                    await ValidationRunRepository.mark_failed(
                        session, run_id, detail=format_validation_job_error(exc)
                    )
                    await session.commit()
            except Exception as persist_exc:
                logger.error("Failed to record validation failure in database: %s", persist_exc)
        raise
    finally:
        for p in (source_path, target_path):
            if p is not None:
                try:
                    p.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Failed to remove temp upload %s: %s", p, exc)

    poll = f"{settings.api_v1_prefix.rstrip('/')}/validate/jobs/{job_id}"
    queue_stats = queue.stats
    return ValidationJobAcceptedResponse(
        job_id=job_id,
        status="queued",
        poll_url=poll,
        queue_position=queued_job.position,
        queue_pending=queue_stats["pending"],
        queue_running=queue_stats["running"],
        max_concurrency=queue_stats["max_concurrency"],
    )


@router.post(
    "/validate/local",
    response_model=ValidationJobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue comparison of two on-disk CSVs by UID (no upload)",
    responses={
        400: {"description": "Invalid paths, delimiter, or missing uid column"},
        403: {"description": "Local path validation disabled"},
        422: {"description": "Comparison cannot run (e.g. duplicate UIDs)"},
    },
)
async def validate_csv_local_paths(
    settings: AppSettings,
    body: Annotated[LocalPathValidateRequest, Body()],
) -> ValidationJobAcceptedResponse:
    """Queue validation for server-local CSV paths (worker reads files in-place)."""
    file_format, delimiter, fixed_width_config_dict = coerce_local_validate_fields(
        file_format=body.file_format,
        delimiter=body.delimiter,
        fixed_width_config=body.fixed_width_config.model_dump()
        if body.fixed_width_config is not None
        else None,
        column_mappings=[m.model_dump() for m in body.column_mappings],
    )
    if is_fixed_width_run(file_format=file_format, delimiter=delimiter) and not fixed_width_config_dict:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="fixed_width_config is required for fixed-width validation (date slice positions and formats)",
        )
    json_run = is_json_run(file_format=file_format, delimiter=delimiter)

    job_id = uuid.uuid4()
    jobs_root = _validation_jobs_root(settings)
    job_dir = jobs_root / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)

    source_input = resolve_validation_input(
        settings=settings,
        label="source",
        path=body.source_path,
        cloud=body.source_cloud,
        destination_path=job_dir / "source.csv" if body.source_cloud is not None else None,
    )
    target_input = resolve_validation_input(
        settings=settings,
        label="target",
        path=body.target_path,
        cloud=body.target_cloud,
        destination_path=job_dir / "target.csv" if body.target_cloud is not None else None,
    )

    run_id: uuid.UUID | None = None
    if settings.enable_validation_persistence:
        try:
            run_uid_column = (
                "date"
                if is_fixed_width_run(file_format=file_format, delimiter=delimiter)
                else "document"
                if json_run
                else body.uid_column.strip()
            )
            run_delimiter = (
                FIXED_WIDTH_DELIMITER
                if is_fixed_width_run(file_format=file_format, delimiter=delimiter)
                else JSON_DELIMITER
                if json_run
                else normalize_delimiter_for_storage(delimiter)
            )
            async with AsyncSessionLocal() as session:
                run_orm = await ValidationRunRepository.create_running(
                    session,
                    source_filename=source_input.display_name,
                    target_filename=target_input.display_name,
                    source_path=to_display_path(source_input.path, settings),
                    target_path=to_display_path(target_input.path, settings),
                    file_pair_key=compute_file_pair_key_for_settings(
                        str(source_input.path),
                        str(target_input.path),
                        settings,
                    ),
                    uid_column=run_uid_column,
                    delimiter=run_delimiter,
                    column_mappings=[m.model_dump() for m in body.column_mappings],
                    validate_header_formats=body.validate_header_formats,
                    validate_footers=body.validate_footers,
                )
                await session.commit()
                run_id = run_orm.id
        except Exception as exc:
            logger.exception("Failed to create validation run record: %s", exc)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not persist validation run; check database connectivity",
            ) from exc

    meta = {
        "uid_column": (
            "date"
            if is_fixed_width_run(file_format=file_format, delimiter=delimiter)
            else "document"
            if json_run
            else body.uid_column.strip()
        ),
        "delimiter": (
            FIXED_WIDTH_DELIMITER
            if is_fixed_width_run(file_format=file_format, delimiter=delimiter)
            else JSON_DELIMITER
            if json_run
            else delimiter
        ),
        "column_mappings": [m.model_dump() for m in body.column_mappings],
        "validate_header_formats": body.validate_header_formats,
        "validate_footers": body.validate_footers,
        "footer_trailing_rows": body.footer_trailing_rows,
        "has_header": body.has_header,
        "header_leading_rows": body.header_leading_rows,
        "memory_log_interval_seconds": settings.validation_memory_log_interval_seconds,
        "run_id": str(run_id) if run_id else None,
        "source_path": str(source_input.path),
        "target_path": str(target_input.path),
        "source_filename": source_input.display_name,
        "target_filename": target_input.display_name,
        "file_format": file_format,
        "fixed_width_config": fixed_width_config_dict,
        "test_mode": body.test_mode.value,
        "uid_gte": body.uid_gte,
    }
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))

    # Enqueue into the concurrency-limited job queue
    queue = get_validation_queue(settings)
    queued_job = queue.enqueue(job_id, job_dir)

    poll = f"{settings.api_v1_prefix.rstrip('/')}/validate/jobs/{job_id}"
    queue_stats = queue.stats
    return ValidationJobAcceptedResponse(
        job_id=job_id,
        status="queued",
        poll_url=poll,
        queue_position=queued_job.position,
        queue_pending=queue_stats["pending"],
        queue_running=queue_stats["running"],
        max_concurrency=queue_stats["max_concurrency"],
    )


@router.post(
    "/validate/local/match-pairs",
    response_model=MatchFilePairsResponse,
    summary="Auto-match files between two directories by filename",
    responses={
        400: {"description": "Invalid directories"},
        403: {"description": "Local path validation disabled"},
    },
)
async def match_local_file_pairs(
    settings: AppSettings,
    body: Annotated[MatchFilePairsRequest, Body()],
) -> MatchFilePairsResponse:
    """Suggest 1:1 file pairs from two folders (basename match); unmatched files are listed for manual pairing."""
    source_dir = resolve_local_dir_for_browse(body.source_directory, settings)
    target_dir = resolve_local_dir_for_browse(body.target_directory, settings)
    source_files = list_files_in_directory(
        source_dir,
        file_format=body.file_format,
        recursive=body.recursive,
    )
    target_files = list_files_in_directory(
        target_dir,
        file_format=body.file_format,
        recursive=body.recursive,
    )
    pairing = auto_match_files_by_name(source_files, target_files)
    return MatchFilePairsResponse(
        pairs=[
            FilePairMatch(
                unit_id=p.unit_id,
                source_path=to_display_path(p.source_path, settings),
                target_path=to_display_path(p.target_path, settings),
                source_name=p.source_path.name,
                target_name=p.target_path.name,
                auto_matched=p.auto_matched,
            )
            for p in pairing.pairs
        ],
        unmatched_sources=[to_display_path(p, settings) for p in pairing.unmatched_sources],
        unmatched_targets=[to_display_path(p, settings) for p in pairing.unmatched_targets],
    )


@router.post(
    "/validate/cloud/browse",
    response_model=CloudBrowseResponse,
    summary="Browse GCS bucket prefixes and objects for the cloud file picker",
)
async def browse_cloud_prefix(
    body: Annotated[CloudBrowseRequest, Body()],
) -> CloudBrowseResponse:
    """List child prefixes and objects under a bucket prefix (delimiter='/')."""
    info = _resolve_cloud_credentials(body.credentials_json)
    try:
        result = browse_gcs_prefix(
            bucket=body.bucket,
            prefix=body.prefix,
            credentials_info=info,
            project_id=body.project_id,
            file_format=body.file_format,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CloudBrowseResponse(
        bucket=result.bucket,
        prefix=result.prefix,
        parent_prefix=result.parent_prefix,
        entries=[
            CloudBrowseEntry(name=e.name, path=e.path, is_dir=e.is_dir) for e in result.entries
        ],
        truncated=result.truncated,
    )


@router.post(
    "/validate/cloud/match-pairs",
    response_model=MatchFilePairsResponse,
    summary="Auto-match GCS objects between two prefixes by filename",
)
async def match_cloud_file_pairs(
    body: Annotated[CloudMatchFilePairsRequest, Body()],
) -> MatchFilePairsResponse:
    """Suggest 1:1 object pairs from two bucket prefixes (basename match)."""
    info = _resolve_cloud_credentials(body.credentials_json)
    try:
        source_names = list_gcs_files_under_prefix(
            bucket=body.bucket,
            prefix=body.source_prefix,
            credentials_info=info,
            project_id=body.project_id,
            file_format=body.file_format,
            recursive=body.recursive,
        )
        target_names = list_gcs_files_under_prefix(
            bucket=body.bucket,
            prefix=body.target_prefix,
            credentials_info=info,
            project_id=body.project_id,
            file_format=body.file_format,
            recursive=body.recursive,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    pairing = auto_match_files_by_name(
        [Path(n) for n in source_names],
        [Path(n) for n in target_names],
    )
    return MatchFilePairsResponse(
        pairs=[
            FilePairMatch(
                unit_id=p.unit_id,
                source_path=p.source_path.as_posix(),
                target_path=p.target_path.as_posix(),
                source_name=Path(p.source_path).name,
                target_name=Path(p.target_path).name,
                auto_matched=p.auto_matched,
            )
            for p in pairing.pairs
        ],
        unmatched_sources=[p.as_posix() for p in pairing.unmatched_sources],
        unmatched_targets=[p.as_posix() for p in pairing.unmatched_targets],
    )


@router.post(
    "/validate/local/batch",
    response_model=ValidationJobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue batch validation (folder pairs, merge-then-validate)",
    responses={
        400: {"description": "Invalid paths or units"},
        403: {"description": "Local path validation disabled"},
    },
)
async def validate_local_batch(
    settings: AppSettings,
    body: Annotated[LocalBatchValidateRequest, Body()],
) -> ValidationJobAcceptedResponse:
    """Queue one or more validation units; each unit may merge multiple source/target files."""
    file_format, delimiter, _ = coerce_local_validate_fields(
        file_format=body.file_format,
        delimiter=body.delimiter,
        fixed_width_config=None,
        column_mappings=[],
    )
    json_run = is_json_run(file_format=file_format, delimiter=delimiter)
    fixed_run = is_fixed_width_run(file_format=file_format, delimiter=delimiter)

    job_id = uuid.uuid4()
    jobs_root = _validation_jobs_root(settings)
    job_dir = jobs_root / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)

    units_meta: list[dict[str, object]] = []
    use_cloud = bool(body.cloud_bucket and body.cloud_credentials_json)
    if use_cloud:
        _resolve_cloud_credentials(body.cloud_credentials_json)

    for unit in body.units:
        if use_cloud:
            source_paths = [p.strip() for p in unit.source_paths if p.strip()]
            target_paths = [p.strip() for p in unit.target_paths if p.strip()]
        else:
            source_paths = [str(resolve_local_csv_path(p, settings)) for p in unit.source_paths]
            target_paths = [str(resolve_local_csv_path(p, settings)) for p in unit.target_paths]
        fw_dict = None
        if fixed_run:
            if unit.fixed_width_config is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"fixed_width_config is required for unit {unit.unit_id}",
                )
            fw_dict = unit.fixed_width_config.model_dump()
        units_meta.append({
            "unit_id": unit.unit_id.strip(),
            "source_paths": source_paths,
            "target_paths": target_paths,
            "uid_column": (
                "document"
                if json_run
                else "date"
                if fixed_run
                else unit.uid_column.strip()
            ),
            "column_mappings": [m.model_dump() for m in unit.column_mappings],
            "fixed_width_config": fw_dict,
        })

    meta = {
        "batch": True,
        "file_format": file_format,
        "delimiter": (
            FIXED_WIDTH_DELIMITER
            if fixed_run
            else JSON_DELIMITER
            if json_run
            else delimiter
        ),
        "has_header": body.has_header,
        "header_leading_rows": body.header_leading_rows,
        "validate_header_formats": body.validate_header_formats,
        "validate_footers": body.validate_footers,
        "footer_trailing_rows": body.footer_trailing_rows,
        "on_unit_failure": body.on_unit_failure.value,
        "memory_log_interval_seconds": settings.validation_memory_log_interval_seconds,
        "units": units_meta,
        "test_mode": body.test_mode.value,
        "uid_gte": body.uid_gte,
    }
    if use_cloud:
        meta["cloud_bucket"] = body.cloud_bucket.strip()
        meta["cloud_credentials_json"] = body.cloud_credentials_json
        meta["cloud_project_id"] = body.cloud_project_id
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))
    _atomic_write_json(job_dir / "status.json", {"status": "queued", "phase": "queued"})

    queue = get_validation_queue(settings)
    queued_job = queue.enqueue(job_id, job_dir)
    poll = f"{settings.api_v1_prefix.rstrip('/')}/validate/jobs/{job_id}"
    queue_stats = queue.stats
    return ValidationJobAcceptedResponse(
        job_id=job_id,
        status="queued",
        poll_url=poll,
        queue_position=queued_job.position,
        queue_pending=queue_stats["pending"],
        queue_running=queue_stats["running"],
        max_concurrency=queue_stats["max_concurrency"],
    )


@router.post(
    "/validate/local/analyze",
    response_model=MappingAnalyzeResponse,
    summary="Optional header-format and footer checks for the mapping wizard",
    responses={
        400: {"description": "Invalid paths or delimiter"},
        403: {"description": "Local path validation disabled"},
    },
)
async def analyze_local_mappings(
    service: ValidationServiceDep,
    settings: AppSettings,
    body: Annotated[MappingAnalyzeRequest, Body()],
) -> MappingAnalyzeResponse:
    source_input = resolve_validation_input(settings=settings, label="source", path=body.source_path, cloud=body.source_cloud)
    target_input = resolve_validation_input(settings=settings, label="target", path=body.target_path, cloud=body.target_cloud)
    try:
        analysis = service.analyze_local_mappings(
            source_path=source_input.path,
            target_path=target_input.path,
            uid_column=body.uid_column.strip(),
            delimiter=body.delimiter,
            column_mappings=body.column_mappings,
            validate_header_formats=body.validate_header_formats,
            validate_footers=body.validate_footers,
            footer_trailing_rows=body.footer_trailing_rows,
            has_header=body.has_header,
            header_leading_rows=body.header_leading_rows,
        )
        return MappingAnalyzeResponse(
            format_checks=[ColumnMappingFormatCheck.model_validate(c) for c in analysis.get("format_checks", [])],
            footer_validation=(
                FooterValidationResult.model_validate(analysis["footer_validation"])
                if analysis.get("footer_validation")
                else None
            ),
            delimiter=str(analysis.get("delimiter") or body.delimiter),
        )
    finally:
        for p in (source_input.cleanup_path, target_input.cleanup_path):
            if p is not None:
                try:
                    p.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Failed to remove temp cloud input %s: %s", p, exc)


@router.get(
    "/validate/local/fixed-width/columns",
    response_model=FixedWidthLayoutPreviewResponse,
    summary="Infer fixed-width column slices from sample lines",
    responses={
        400: {"description": "Invalid paths"},
        403: {"description": "Local path validation disabled"},
    },
)
async def preview_local_fixed_width_columns(
    service: ValidationServiceDep,
    settings: AppSettings,
    source_path: Annotated[str, Query(description="Absolute source file path")],
    target_path: Annotated[str, Query(description="Absolute target file path")],
) -> FixedWidthLayoutPreviewResponse:
    source = resolve_local_csv_path(source_path, settings)
    target = resolve_local_csv_path(target_path, settings)
    preview = service.preview_fixed_width_layout(source_path=source, target_path=target)
    return FixedWidthLayoutPreviewResponse(**preview)


@router.get(
    "/validate/local/columns",
    response_model=LocalColumnPreviewResponse,
    summary="Preview source and target CSV headers for mapping",
    responses={
        400: {"description": "Invalid paths or delimiter"},
        403: {"description": "Local path validation disabled"},
    },
)
async def preview_local_csv_columns(
    service: ValidationServiceDep,
    settings: AppSettings,
    source_path: Annotated[str, Query(description="Absolute source CSV path")],
    target_path: Annotated[str, Query(description="Absolute target CSV path")],
    uid_column: Annotated[str, Query(description="Join key column to exclude from compare mapping")] = "id",
    delimiter: Annotated[str, Query(description="Field separator or auto")] = "auto",
    has_header: Annotated[bool, Query(description="Whether the first row contains column names")] = True,
    header_leading_rows: Annotated[int, Query(description="Leading rows to skip before reading columns")] = 0,
) -> LocalColumnPreviewResponse:
    source = resolve_local_csv_path(source_path, settings)
    target = resolve_local_csv_path(target_path, settings)
    preview = service.preview_local_column_headers(
        source_path=source,
        target_path=target,
        uid_column=uid_column,
        delimiter=delimiter,
        has_header=has_header,
        header_leading_rows=header_leading_rows,
    )
    return LocalColumnPreviewResponse(**preview)


@router.post(
    "/validate/local/columns",
    response_model=LocalColumnPreviewResponse,
    summary="Preview source and target CSV headers for mapping (body variant for cloud inputs)",
    responses={
        400: {"description": "Invalid paths, cloud inputs, or delimiter"},
        403: {"description": "Local path validation disabled"},
    },
)
async def preview_local_csv_columns_body(
    service: ValidationServiceDep,
    settings: AppSettings,
    body: Annotated[LocalPathValidateRequest, Body()],
) -> LocalColumnPreviewResponse:
    source_input = resolve_validation_input(settings=settings, label="source", path=body.source_path, cloud=body.source_cloud)
    target_input = resolve_validation_input(settings=settings, label="target", path=body.target_path, cloud=body.target_cloud)
    try:
        preview = service.preview_local_column_headers(
            source_path=source_input.path,
            target_path=target_input.path,
            uid_column=body.uid_column,
            delimiter=body.delimiter,
            has_header=body.has_header,
            header_leading_rows=body.header_leading_rows,
        )
        return LocalColumnPreviewResponse(**preview)
    finally:
        for p in (source_input.cleanup_path, target_input.cleanup_path):
            if p is not None:
                try:
                    p.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Failed to remove temp cloud input %s: %s", p, exc)

@router.get(
    "/validate/local/browse/config",
    response_model=LocalPathBrowseConfigResponse,
    summary="Default browse directory and Docker path remap settings for the file picker",
    responses={403: {"description": "Local path validation disabled"}},
)
async def get_local_browse_config(settings: AppSettings) -> LocalPathBrowseConfigResponse:
    _require_local_path_access(settings)
    remap = local_path_remap(settings)
    return LocalPathBrowseConfigResponse(
        default_browse_path=default_browse_path_for_ui(settings),
        path_remap_enabled=remap is not None,
        host_path_prefix=remap[0] if remap else None,
        container_path_prefix=remap[1] if remap else None,
    )


@router.get(
    "/validate/local/browse",
    response_model=LocalBrowseResponse,
    summary="List files and folders under a server directory (local-path picker)",
    responses={
        400: {"description": "Path not found or not a directory"},
        403: {"description": "Local path validation disabled"},
    },
)
async def browse_local_directory(
    settings: AppSettings,
    path: Annotated[
        str | None,
        Query(description="Absolute directory to list; defaults to / when omitted"),
    ] = None,
) -> LocalBrowseResponse:
    """Directory listing for picking ``source_path`` / ``target_path`` via the UI file browser."""
    _require_local_path_access(settings)
    raw = (path or "").strip() or default_browse_path(settings)
    directory = resolve_local_dir_for_browse(raw, settings)
    return build_local_browse_response(directory, settings)


@router.get(
    "/validate/jobs/{job_id}",
    response_model=ValidationJobDetailResponse,
    summary="Poll a queued validation job",
)
async def get_validation_job(settings: AppSettings, job_id: uuid.UUID) -> ValidationJobDetailResponse:
    job_dir = _validation_jobs_root(settings) / str(job_id)
    status_path = job_dir / "status.json"
    if not status_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown job_id")
    try:
        st = loads_str(status_path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, TypeError, OSError):
        return ValidationJobDetailResponse(status="running", phase="updating", message="Refreshing job status")
    status_val = str(st.get("status") or "unknown")
    phase = st.get("phase")
    message = st.get("message")
    progress = st.get("progress") if isinstance(st.get("progress"), dict) else {}
    if status_val in {"queued", "running"}:
        # Enrich with live queue position when the job is still waiting
        if status_val == "queued":
            queue = get_validation_queue(settings)
            pos = queue.get_queue_position(job_id)
            if pos is not None:
                progress["queue_position"] = pos
                progress["pending_ahead"] = pos
                progress["running_jobs"] = queue.running_count
                progress["max_concurrency"] = queue.max_concurrency
                eta = progress.get("estimated_wait_seconds")
                if isinstance(eta, (int, float)):
                    message = (
                        f"Waiting in queue (position {pos + 1} of {queue.pending_count}, "
                        f"estimated wait {int(eta)}s)"
                    )
                else:
                    message = f"Waiting in queue (position {pos + 1} of {queue.pending_count})"
        return ValidationJobDetailResponse(status=status_val, phase=phase, message=message, progress=progress)
    if status_val == "failed":
        batch_path = job_dir / "batch_result.json"
        if batch_path.is_file():
            return _build_batch_job_detail(
                settings=settings,
                job_dir=job_dir,
                status_val=status_val,
                phase=phase,
                message=message,
                progress=progress,
                error=str(st.get("error") or "failed"),
            )
        return ValidationJobDetailResponse(
            status="failed",
            phase=phase,
            message=message,
            progress=progress,
            error=str(st.get("error") or "failed"),
        )
    if status_val != "completed":
        return ValidationJobDetailResponse(
            status=status_val,
            phase=phase,
            message=message,
            progress=progress,
            error=str(st.get("error") or ""),
        )

    batch_path = job_dir / "batch_result.json"
    if batch_path.is_file():
        return _build_batch_job_detail(
            settings=settings,
            job_dir=job_dir,
            status_val=status_val,
            phase=phase,
            message=message,
            progress=progress,
        )

    result_path = job_dir / "result.json"
    if not result_path.is_file():
        return ValidationJobDetailResponse(
            status="failed",
            phase=phase,
            message=message,
            progress=progress,
            error="completed but result.json missing",
        )

    cached = _completed_job_cache_get(job_id)
    if cached is not None:
        return cached

    run_result, rid, job_meta = _run_result_from_job_dir(job_dir)
    await _maybe_persist_completed_job(settings, run_id=rid, run_result=run_result, job_meta=job_meta)
    payload = _build_validate_response(settings=settings, run_result=run_result, run_id=rid)
    detail = ValidationJobDetailResponse(
        status="completed",
        phase=phase,
        message=message,
        progress=progress,
        result=payload,
    )
    _completed_job_cache_put(job_id, detail)
    return detail


@router.get(
    "/validate/queue",
    summary="Get validation job queue status, CPU info, and job list",
    response_model=QueueStatusResponse,
)
async def get_validation_queue_status(settings: AppSettings) -> QueueStatusResponse:
    """Return queue statistics including ``cpu_cores_available`` so users
    can decide how much concurrency to allow via ``PATCH /validate/queue``.
    """
    queue = get_validation_queue(settings)
    stats = queue.stats
    return QueueStatusResponse(
        **stats,
        jobs=queue.list_jobs(limit=50),
    )


@router.patch(
    "/validate/queue",
    summary="Update queue settings (e.g. max parallel validations)",
    response_model=QueueStatusResponse,
)
async def update_validation_queue_settings(
    settings: AppSettings,
    body: Annotated[UpdateQueueSettingsRequest, Body()],
) -> QueueStatusResponse:
    """Dynamically change queue settings.

    - ``max_concurrency``: how many jobs run in parallel (user's upper cap).
    - ``auto_tune_enabled``: when true, the system further reduces effective
      concurrency if RAM / disk / swap pressure is too high.

    The server reports ``cpu_cores_available`` and ``resource_advisor`` so you
    can make an informed decision.  Running jobs are **never** killed — changes
    only affect when queued jobs are promoted to running.
    """
    queue = get_validation_queue(settings)
    if body.max_concurrency is not None:
        queue.set_max_concurrency(body.max_concurrency)
    if body.auto_tune_enabled is not None:
        queue.set_auto_tune(body.auto_tune_enabled)
    if body.threads_per_job is not None:
        queue.set_threads_per_job(body.threads_per_job)
    if body.disk_headroom_multiplier is not None:
        queue.set_disk_headroom_multiplier(body.disk_headroom_multiplier)
    stats = queue.stats
    return QueueStatusResponse(
        **stats,
        jobs=queue.list_jobs(limit=50),
    )


"""CSV validation endpoint (UID-based comparison)."""

from __future__ import annotations

import gc
import logging
import os
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile, status

from pegasus.api.deps import AppSettings, ValidationServiceDep
from pegasus.core.config import Settings
from pegasus.core.database import AsyncSessionLocal
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.models.enums import ValidationRunStatus
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.schemas.validation import (
    ColumnMappingFormatCheck,
    FooterValidationResult,
    LocalBrowseEntry,
    LocalBrowseResponse,
    LocalColumnPreviewResponse,
    LocalPathValidateRequest,
    MappingAnalyzeRequest,
    MappingAnalyzeResponse,
    MismatchSampleGroups,
    MismatchSampleRow,
    QueueStatusResponse,
    UpdateQueueSettingsRequest,
    ValidateResponse,
    ValidationDurations,
    ValidationJobAcceptedResponse,
    ValidationJobDetailResponse,
    ValidationSummary,
    build_mismatch_counts,
)
from pegasus.services.validation_job_queue import get_validation_queue
from pegasus.services.exceptions import ValidationBadRequestError
from pegasus.services.validation_service import ValidationRunDurations, ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame
from pegasus.validation.delimiter_tokens import FIXED_WIDTH_DELIMITER, normalize_delimiter_for_storage

from .mismatch_sample import (
    build_grouped_mismatch_samples,
    load_mismatch_polars_for_api,
    load_value_mismatch_sample_from_ndjson,
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
_LOCAL_BROWSE_DEFAULT_DIR = Path("/")


def _require_local_path_access(settings: Settings) -> None:
    if not settings.validation_allow_local_paths:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Local path validation is disabled (set PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS=true).",
        )


def resolve_local_csv_path(raw: str, settings: Settings) -> Path:
    """Resolve *raw* to an absolute file path on the server (when local paths are enabled)."""
    _require_local_path_access(settings)
    path = Path(raw.strip()).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Path not found: {raw!r}") from exc
    if not resolved.is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Not a regular file: {resolved}")
    return resolved


def resolve_local_dir_for_browse(raw: str, settings: Settings) -> Path:
    """Resolve *raw* to an absolute directory (for GET /validate/local/browse)."""
    _require_local_path_access(settings)
    path = Path(raw.strip()).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Path not found: {raw!r}") from exc
    if not resolved.is_dir():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Not a directory: {resolved}")
    return resolved


def _browse_parent_path(current: Path) -> Path | None:
    parent = current.parent
    if parent == current:
        return None
    return parent


def build_local_browse_response(directory: Path) -> LocalBrowseResponse:
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

    entries = [LocalBrowseEntry(name=display_name, path=str(p), is_dir=p.is_dir()) for _, _, p, display_name in rows]
    return LocalBrowseResponse(
        path=str(directory),
        parent_path=str(parent) if parent is not None else None,
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
    sample_limit = raw_sample_limit
    if total_records > 0:
        if sample_limit <= 0:
            sample_limit = min(10_000, total_records)
            logger.info(
                "validation_mismatch_sample_limit was %s; using effective sample_limit=%s for value_mismatch samples",
                raw_sample_limit,
                sample_limit,
            )
        if raw_sample_limit > 0:
            sample_limit = min(sample_limit, raw_sample_limit)
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
        val_df = load_value_mismatch_sample_from_ndjson(
            artifact,
            n_val=counts_model.value_mismatch,
            value_sample_limit=sample_limit,
        )
        sample_groups = MismatchSampleGroups(
            missing_in_target=[MismatchSampleRow.model_validate(r) for r in miss_rows],
            extra_in_target=[MismatchSampleRow.model_validate(r) for r in ext_rows],
            value_mismatch=[MismatchSampleRow.model_validate(r) for r in val_df.to_dicts()],
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
            missing_in_target=[MismatchSampleRow.model_validate(r) for r in miss_df.to_dicts()],
            extra_in_target=[MismatchSampleRow.model_validate(r) for r in ext_df.to_dicts()],
            value_mismatch=[MismatchSampleRow.model_validate(r) for r in val_df.to_dicts()],
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
    rel = res.get("mismatch_artifact_rel")
    apath = (job_dir / str(rel)) if rel else None
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
        durations=_durations_from_result_json(res),
    )
    return vr, run_uuid, meta


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
                    await ValidationRunRepository.mark_failed(session, run_id, detail=repr(exc))
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
    source_path = resolve_local_csv_path(body.source_path, settings)
    target_path = resolve_local_csv_path(body.target_path, settings)

    job_id = uuid.uuid4()
    jobs_root = _validation_jobs_root(settings)
    job_dir = jobs_root / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)

    run_id: uuid.UUID | None = None
    if settings.enable_validation_persistence:
        try:
            run_uid_column = "date" if body.file_format == "fixed-width" else body.uid_column.strip()
            run_delimiter = (
                FIXED_WIDTH_DELIMITER
                if body.file_format == "fixed-width"
                else normalize_delimiter_for_storage(body.delimiter)
            )
            async with AsyncSessionLocal() as session:
                run_orm = await ValidationRunRepository.create_running(
                    session,
                    source_filename=source_path.name,
                    target_filename=target_path.name,
                    source_path=str(source_path),
                    target_path=str(target_path),
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
        "uid_column": "date" if body.file_format == "fixed-width" else body.uid_column.strip(),
        "delimiter": (
            FIXED_WIDTH_DELIMITER if body.file_format == "fixed-width" else body.delimiter
        ),
        "column_mappings": [m.model_dump() for m in body.column_mappings],
        "validate_header_formats": body.validate_header_formats,
        "validate_footers": body.validate_footers,
        "footer_trailing_rows": body.footer_trailing_rows,
        "memory_log_interval_seconds": settings.validation_memory_log_interval_seconds,
        "run_id": str(run_id) if run_id else None,
        "source_path": str(source_path),
        "target_path": str(target_path),
        "file_format": body.file_format,
        "fixed_width_config": body.fixed_width_config.model_dump() if body.fixed_width_config else None,
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
    source = resolve_local_csv_path(body.source_path, settings)
    target = resolve_local_csv_path(body.target_path, settings)
    analysis = service.analyze_local_mappings(
        source_path=source,
        target_path=target,
        uid_column=body.uid_column.strip(),
        delimiter=body.delimiter,
        column_mappings=body.column_mappings,
        validate_header_formats=body.validate_header_formats,
        validate_footers=body.validate_footers,
        footer_trailing_rows=body.footer_trailing_rows,
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
) -> LocalColumnPreviewResponse:
    source = resolve_local_csv_path(source_path, settings)
    target = resolve_local_csv_path(target_path, settings)
    preview = service.preview_local_column_headers(
        source_path=source,
        target_path=target,
        uid_column=uid_column,
        delimiter=delimiter,
    )
    return LocalColumnPreviewResponse(**preview)

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
    raw = (path or "").strip() or str(_LOCAL_BROWSE_DEFAULT_DIR)
    directory = resolve_local_dir_for_browse(raw, settings)
    return build_local_browse_response(directory)


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
                message = f"Waiting in queue (position {pos + 1} of {queue.pending_count})"
        return ValidationJobDetailResponse(status=status_val, phase=phase, message=message, progress=progress)
    if status_val == "failed":
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


# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T11:38:03Z
# --- END GENERATED FILE METADATA ---

"""CSV validation endpoints (local paths, browse, job polling)."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, status

logger = logging.getLogger(__name__)

from pegasus.api.deps import AppSettings, DbSession, ValidationServiceDep
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.core.local_paths import (
    compute_file_pair_key_for_settings,
    default_browse_path,
    default_browse_path_for_ui,
    local_path_remap,
    resolve_local_path_on_disk,
    to_display_path,
)
from pegasus.repositories.validation_repository import ValidationRunRepository
from pegasus.schemas.validation import (
    CloudBrowseEntry,
    CloudBrowseRequest,
    CloudBrowseResponse,
    CloudFileProfileRequest,
    CloudFileProfileResponse,
    CloudMatchFilePairsRequest,
    FileDetectionResponse,
    FilePairMatch,
    FixedWidthLayoutPreviewResponse,
    LocalBrowseResponse,
    LocalColumnPreviewResponse,
    LocalPathBrowseConfigResponse,
    LocalBatchValidateRequest,
    LocalPathValidateRequest,
    MatchFilePairsRequest,
    MatchFilePairsResponse,
    QueueStatusResponse,
    UpdateQueueSettingsRequest,
    ValidationJobAcceptedResponse,
    ValidationJobDetailResponse,
    ValidationOptionsResponse,
    ValidationTestMode,
)
from pegasus.schemas.validation_history import (
    ValidationHistoryMismatchRow,
    ValidationHistoryMismatchesResponse,
)
from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.coerce import coerce_local_validate_fields_with_detection
from pegasus.validation.file_format import infer_file_format_from_path, normalize_file_format
from pegasus.validation.file_pairing import auto_match_files_by_name, list_files_in_directory
from pegasus.services.exceptions import ValidationBadRequestError
from pegasus.services.job_size_estimate import enrich_meta_file_sizes
from pegasus.services.validation_job_queue import get_validation_queue
from pegasus.validation.cloud_credentials import resolve_gcs_auth
from pegasus.validation.cloud_input import (
    ResolvedDelimitedInput,
    coerce_cloud_storage_reference,
    delimited_input_from_meta,
    ensure_resolved_cloud_config,
    resolve_cloud_config_with_saved_connection,
    resolve_delimited_input,
)
from pegasus.validation.gcs_object import cloud_config_to_meta
from pegasus.validation.gcs_browse import browse_gcs_prefix, list_gcs_buckets, list_gcs_files_under_prefix
from pegasus.validation.local_browse import (
    build_local_browse_response,
    require_local_path_access,
    resolve_local_csv_path,
    resolve_local_dir_for_browse,
)

from pegasus.validation.test_mode_policy import clamp_snippet_limit

from .validation_helpers import (
    build_validate_response,
    build_validate_response_summary_only,
    completed_job_cache_get,
    completed_job_cache_put,
    maybe_persist_completed_job,
    paginate_job_mismatch_rows,
    record_poll_lifecycle,
    run_result_from_job_dir,
    schedule_persist_completed_job,
    validation_jobs_root,
)

router = APIRouter(tags=["validation"])


def _resolved_snippet_limit(
    settings: AppSettings,
    *,
    test_mode: ValidationTestMode,
    requested: int | None,
) -> int | None:
    if test_mode != ValidationTestMode.FULL:
        return None
    return clamp_snippet_limit(settings, requested=requested)


@router.get(
    "/validate/options",
    response_model=ValidationOptionsResponse,
    summary="Validation wizard options (test modes and snippet limits)",
)
async def validation_options(settings: AppSettings) -> ValidationOptionsResponse:
    return ValidationOptionsResponse(
        mismatch_snippet_limit_default=settings.validation_mismatch_snippet_limit_default,
        mismatch_snippet_limit_max=settings.validation_mismatch_snippet_limit_max,
    )


def _preview_columns(
    service: ValidationServiceDep,
    settings: AppSettings,
    *,
    source_path: str,
    target_path: str,
    uid_column: str,
    delimiter: str,
    has_header: bool,
    header_leading_rows: int,
    file_format: str | None,
) -> LocalColumnPreviewResponse:
    require_local_path_access(settings)
    source = resolve_local_path_on_disk(source_path, settings, must_be_file=True)
    target = resolve_local_path_on_disk(target_path, settings, must_be_file=True)
    try:
        preview = service.preview_local_column_headers(
            source_path=source,
            target_path=target,
            uid_column=uid_column,
            delimiter=delimiter,
            has_header=has_header,
            header_leading_rows=header_leading_rows,
            file_format=file_format,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LocalColumnPreviewResponse(**preview)


@router.get(
    "/validate/local/browse/config",
    response_model=LocalPathBrowseConfigResponse,
    summary="Default browse directory and Docker path remap settings for the file picker",
    responses={403: {"description": "Local path validation disabled"}},
)
async def get_local_browse_config(settings: AppSettings) -> LocalPathBrowseConfigResponse:
    require_local_path_access(settings)
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
        Query(description="Absolute directory to list; defaults to configured browse root when omitted"),
    ] = None,
) -> LocalBrowseResponse:
    require_local_path_access(settings)
    raw = (path or "").strip() or default_browse_path(settings)
    directory = resolve_local_dir_for_browse(raw, settings)
    return build_local_browse_response(directory, settings)


@router.get(
    "/validate/local/detect",
    response_model=FileDetectionResponse,
    summary="Multi-layer file type detection report for a local path",
    responses={
        400: {"description": "Invalid path"},
        403: {"description": "Local path validation disabled"},
    },
)
async def detect_local_file(
    settings: AppSettings,
    path: Annotated[str, Query(description="Absolute file path to inspect")],
    file_format: Annotated[
        str | None,
        Query(description="Declared format hint (csv, auto, parquet, …)"),
    ] = None,
) -> FileDetectionResponse:
    require_local_path_access(settings)
    resolved = resolve_local_path_on_disk(path, settings, must_be_file=True)
    report = detect_file(resolved, user_format_hint=file_format)
    return report.to_api()


@router.get(
    "/validate/local/columns",
    response_model=LocalColumnPreviewResponse,
    summary="Preview source and target headers for mapping",
    responses={
        400: {"description": "Invalid paths or delimiter"},
        403: {"description": "Local path validation disabled"},
    },
)
async def preview_local_csv_columns(
    service: ValidationServiceDep,
    settings: AppSettings,
    source_path: Annotated[str, Query(description="Absolute source file path")],
    target_path: Annotated[str, Query(description="Absolute target file path")],
    uid_column: Annotated[str, Query(description="Join key column to exclude from compare mapping")] = "id",
    delimiter: Annotated[str, Query(description="Field separator or auto")] = "auto",
    has_header: Annotated[bool, Query(description="Whether the first row contains column names")] = True,
    header_leading_rows: Annotated[int, Query(description="Leading rows to skip before reading columns")] = 0,
    file_format: Annotated[str | None, Query(description="File format or auto (inferred from extension)")] = None,
) -> LocalColumnPreviewResponse:
    return _preview_columns(
        service,
        settings,
        source_path=source_path,
        target_path=target_path,
        uid_column=uid_column,
        delimiter=delimiter,
        has_header=has_header,
        header_leading_rows=header_leading_rows,
        file_format=file_format,
    )


@router.post(
    "/validate/local/columns",
    response_model=LocalColumnPreviewResponse,
    summary="Preview source and target headers for mapping (body variant)",
    responses={
        400: {"description": "Invalid paths, cloud inputs, or delimiter"},
        403: {"description": "Local path validation disabled"},
    },
)
async def preview_local_csv_columns_body(
    service: ValidationServiceDep,
    settings: AppSettings,
    session: DbSession,
    body: Annotated[LocalPathValidateRequest, Body()],
) -> LocalColumnPreviewResponse:
    source_cloud, source_path = await coerce_cloud_storage_reference(
        session,
        label="source",
        path=body.source_path,
        cloud=(
            await resolve_cloud_config_with_saved_connection(body.source_cloud, session=session)
            if body.source_cloud is not None
            else None
        ),
    )
    target_cloud, target_path = await coerce_cloud_storage_reference(
        session,
        label="target",
        path=body.target_path,
        cloud=(
            await resolve_cloud_config_with_saved_connection(body.target_cloud, session=session)
            if body.target_cloud is not None
            else None
        ),
    )
    source_cloud = await ensure_resolved_cloud_config(session, source_cloud)
    target_cloud = await ensure_resolved_cloud_config(session, target_cloud)
    source_input = resolve_delimited_input(
        settings=settings,
        label="source",
        path=source_path,
        cloud=source_cloud,
        delimiter=body.delimiter,
        has_header=body.has_header,
        skip_rows=body.header_leading_rows,
    )
    target_input = resolve_delimited_input(
        settings=settings,
        label="target",
        path=target_path,
        cloud=target_cloud,
        delimiter=body.delimiter,
        has_header=body.has_header,
        skip_rows=body.header_leading_rows,
    )
    from pegasus.validation.file_format import normalize_file_format

    requested_fmt = normalize_file_format(body.file_format) if body.file_format else None
    if requested_fmt == "fixed-width":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Use POST /validate/local/fixed-width-layout for fixed-width files",
        )
    try:
        preview = service.preview_column_headers_from_adapters(
            source=source_input.adapter,
            target=target_input.adapter,
            uid_column=body.uid_column,
            delimiter=body.delimiter,
            has_header=body.has_header,
            header_leading_rows=body.header_leading_rows,
            file_format=body.file_format,
        )
        return LocalColumnPreviewResponse(**preview)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/validate/local/fixed-width-layout",
    response_model=FixedWidthLayoutPreviewResponse,
    summary="Infer fixed-width column slices and date formats for mapping",
    responses={
        400: {"description": "Invalid paths, cloud inputs, or unreadable files"},
        403: {"description": "Local path validation disabled"},
    },
)
async def preview_fixed_width_layout_body(
    service: ValidationServiceDep,
    settings: AppSettings,
    session: DbSession,
    body: Annotated[LocalPathValidateRequest, Body()],
) -> FixedWidthLayoutPreviewResponse:
    source_cloud, source_path = await coerce_cloud_storage_reference(
        session,
        label="source",
        path=body.source_path,
        cloud=(
            await resolve_cloud_config_with_saved_connection(body.source_cloud, session=session)
            if body.source_cloud is not None
            else None
        ),
    )
    target_cloud, target_path = await coerce_cloud_storage_reference(
        session,
        label="target",
        path=body.target_path,
        cloud=(
            await resolve_cloud_config_with_saved_connection(body.target_cloud, session=session)
            if body.target_cloud is not None
            else None
        ),
    )
    source_cloud = await ensure_resolved_cloud_config(session, source_cloud)
    target_cloud = await ensure_resolved_cloud_config(session, target_cloud)
    source_input = resolve_delimited_input(
        settings=settings,
        label="source",
        path=source_path,
        cloud=source_cloud,
        delimiter=body.delimiter,
        has_header=body.has_header,
        skip_rows=body.header_leading_rows,
    )
    target_input = resolve_delimited_input(
        settings=settings,
        label="target",
        path=target_path,
        cloud=target_cloud,
        delimiter=body.delimiter,
        has_header=body.has_header,
        skip_rows=body.header_leading_rows,
    )
    try:
        preview = service.preview_fixed_width_layout_from_adapters(
            source=source_input.adapter,
            target=target_input.adapter,
        )
        return FixedWidthLayoutPreviewResponse(**preview)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/validate/cloud/browse",
    response_model=CloudBrowseResponse,
    summary="Browse GCS bucket prefixes and objects for the cloud file picker",
)
async def browse_cloud_prefix(
    session: DbSession,
    body: Annotated[CloudBrowseRequest, Body()],
) -> CloudBrowseResponse:
    """List child prefixes and objects under a bucket prefix (delimiter='/')."""
    bucket, project_id, info = await resolve_gcs_auth(
        session,
        bucket=body.bucket,
        project_id=body.project_id,
        credentials_json=body.credentials_json,
        connection_id=body.connection_id,
        allow_empty_bucket=True,
    )
    try:
        if not bucket:
            result = list_gcs_buckets(
                credentials_info=info,
                project_id=project_id,
            )
        else:
            result = browse_gcs_prefix(
                bucket=bucket,
                prefix=body.prefix,
                credentials_info=info,
                project_id=project_id,
                file_format=body.file_format,
            )
    except ImportError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google-cloud-storage is required for cloud browse",
        ) from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CloudBrowseResponse(
        bucket=result.bucket,
        prefix=result.prefix,
        parent_prefix=result.parent_prefix,
        entries=[
            CloudBrowseEntry(
                name=e.name,
                path=e.path,
                is_dir=e.is_dir,
                size_bytes=e.size_bytes,
                created_at=e.created_at,
                updated_at=e.updated_at,
                owner=e.owner,
                created_by=e.created_by,
            )
            for e in result.entries
        ],
        truncated=result.truncated,
    )


@router.post(
    "/validate/cloud/profile",
    response_model=CloudFileProfileResponse,
    summary="Detect format and count rows/columns for a GCS object",
)
async def profile_cloud_file(
    service: ValidationServiceDep,
    settings: AppSettings,
    session: DbSession,
    body: Annotated[CloudFileProfileRequest, Body()],
) -> CloudFileProfileResponse:
    """Run file-type detection and profile shape stats from GCS metadata + prefix sample."""
    cloud = await resolve_cloud_config_with_saved_connection(body.cloud, session=session)
    cloud = await ensure_resolved_cloud_config(session, cloud)
    resolved = resolve_delimited_input(
        settings=settings,
        label="source",
        path=None,
        cloud=cloud,
        delimiter=",",
        has_header=body.has_header,
        skip_rows=0,
    )
    try:
        return service.profile_delimited_adapter(
            resolved.adapter,
            object_name=cloud.object_name,
            gcs_uri=resolved.display_name,
            delimiter=body.delimiter,
            has_header=body.has_header,
        )
    except ValidationBadRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/validate/cloud/match-pairs",
    response_model=MatchFilePairsResponse,
    summary="Auto-match GCS objects between two prefixes by filename",
)
async def match_cloud_file_pairs(
    session: DbSession,
    body: Annotated[CloudMatchFilePairsRequest, Body()],
) -> MatchFilePairsResponse:
    """Suggest 1:1 object pairs from two bucket prefixes (basename match)."""
    bucket, project_id, info = await resolve_gcs_auth(
        session,
        bucket=body.bucket,
        project_id=body.project_id,
        credentials_json=body.credentials_json,
        connection_id=body.connection_id,
    )
    try:
        source_names = list_gcs_files_under_prefix(
            bucket=bucket,
            prefix=body.source_prefix,
            credentials_info=info,
            project_id=project_id,
            file_format=body.file_format,
            recursive=body.recursive,
        )
        target_names = list_gcs_files_under_prefix(
            bucket=bucket,
            prefix=body.target_prefix,
            credentials_info=info,
            project_id=project_id,
            file_format=body.file_format,
            recursive=body.recursive,
        )
    except ImportError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google-cloud-storage is required for cloud file matching",
        ) from exc
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
                source_name=p.source_path.name,
                target_name=p.target_path.name,
                auto_matched=p.auto_matched,
            )
            for p in pairing.pairs
        ],
        unmatched_sources=[p.as_posix() for p in pairing.unmatched_sources],
        unmatched_targets=[p.as_posix() for p in pairing.unmatched_targets],
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
    require_local_path_access(settings)
    source_dir = resolve_local_dir_for_browse(body.source_directory, settings)
    target_dir = resolve_local_dir_for_browse(body.target_directory, settings)
    try:
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
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
    "/validate/local",
    response_model=ValidationJobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue comparison of two on-disk files by UID (no upload)",
    responses={
        400: {"description": "Invalid paths, delimiter, or missing uid column"},
        403: {"description": "Local path validation disabled"},
        422: {"description": "Comparison cannot run (e.g. duplicate UIDs)"},
    },
)
async def validate_csv_local_paths(
    settings: AppSettings,
    session: DbSession,
    body: Annotated[LocalPathValidateRequest, Body()],
) -> ValidationJobAcceptedResponse:
    source_cloud, source_path = await coerce_cloud_storage_reference(
        session,
        label="source",
        path=body.source_path,
        cloud=(
            await resolve_cloud_config_with_saved_connection(body.source_cloud, session=session)
            if body.source_cloud is not None
            else None
        ),
    )
    target_cloud, target_path = await coerce_cloud_storage_reference(
        session,
        label="target",
        path=body.target_path,
        cloud=(
            await resolve_cloud_config_with_saved_connection(body.target_cloud, session=session)
            if body.target_cloud is not None
            else None
        ),
    )
    source_cloud = await ensure_resolved_cloud_config(session, source_cloud)
    target_cloud = await ensure_resolved_cloud_config(session, target_cloud)

    if source_path is None and source_cloud is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="source_path or source_cloud is required")
    if target_path is None and target_cloud is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="target_path or target_cloud is required")

    source_input: ResolvedDelimitedInput | None = None
    target_input: ResolvedDelimitedInput | None = None
    if source_cloud is not None or target_cloud is not None:
        from pegasus.validation.file_format import is_columnar_format

        normalized = normalize_file_format(body.file_format)
        if is_columnar_format(normalized):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Cloud streaming validation currently supports delimited CSV/TSV inputs only",
            )
        source_input = resolve_delimited_input(
            settings=settings,
            label="source",
            path=source_path,
            cloud=source_cloud,
            delimiter=body.delimiter,
            has_header=body.has_header,
            skip_rows=body.header_leading_rows,
        )
        target_input = resolve_delimited_input(
            settings=settings,
            label="target",
            path=target_path,
            cloud=target_cloud,
            delimiter=body.delimiter,
            has_header=body.has_header,
            skip_rows=body.header_leading_rows,
        )
        resolved_source = source_input.adapter.path
        resolved_target = target_input.adapter.path
        file_format = "csv"
    else:
        require_local_path_access(settings)
        resolved_source = resolve_local_path_on_disk(source_path, settings, must_be_file=True)
        resolved_target = resolve_local_path_on_disk(target_path, settings, must_be_file=True)
        try:
            file_format, detection_warnings = coerce_local_validate_fields_with_detection(
                resolved_source,
                resolved_target,
                body.file_format,
                settings=settings,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if detection_warnings:
            logger.info(
                "file detection warnings job paths source=%s target=%s warnings=%s",
                resolved_source,
                resolved_target,
                detection_warnings,
            )
        legacy_source = infer_file_format_from_path(resolved_source, body.file_format)
        legacy_target = infer_file_format_from_path(resolved_target, body.file_format)
        if legacy_source != legacy_target:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Source and target must use the same file format",
            )
        if normalize_file_format(body.file_format) not in {"auto"} and file_format != legacy_source:
            logger.warning(
                "file_format override source=%s declared=%s detected=%s",
                resolved_source,
                body.file_format,
                file_format,
            )

    job_id = uuid.uuid4()
    job_dir = validation_jobs_root(settings) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)

    src_display = None
    tgt_display = None
    pair_key = None
    if source_cloud is None and target_cloud is None:
        src_display = to_display_path(resolved_source, settings)
        tgt_display = to_display_path(resolved_target, settings)
        pair_key = compute_file_pair_key_for_settings(
            str(resolved_source),
            str(resolved_target),
            settings,
        )
    else:
        if source_input is not None:
            src_display = source_input.display_name
        if target_input is not None:
            tgt_display = target_input.display_name

    run_id: uuid.UUID | None = None
    if settings.enable_validation_persistence:
        run = await ValidationRunRepository.create_running(
            session,
            source_filename=source_input.display_name if source_input else resolved_source.name,
            target_filename=target_input.display_name if target_input else resolved_target.name,
            uid_column=body.uid_column.strip(),
            delimiter=body.delimiter,
            source_path=src_display,
            target_path=tgt_display,
            file_pair_key=pair_key,
            column_mappings=[m.model_dump() for m in body.column_mappings],
            validate_header_formats=body.validate_header_formats,
            validate_footers=body.validate_footers,
        )
        await session.commit()
        run_id = run.id

    meta = {
        "uid_column": body.uid_column.strip(),
        "delimiter": body.delimiter,
        "column_mappings": [m.model_dump() for m in body.column_mappings],
        "validate_header_formats": body.validate_header_formats,
        "validate_footers": body.validate_footers,
        "footer_trailing_rows": body.footer_trailing_rows,
        "has_header": body.has_header,
        "header_leading_rows": body.header_leading_rows,
        "run_id": str(run_id) if run_id else None,
        "job_id": str(job_id),
        "source_filename": source_input.display_name if source_input else resolved_source.name,
        "target_filename": target_input.display_name if target_input else resolved_target.name,
        "file_format": file_format,
        "test_mode": body.test_mode.value,
        "mismatch_snippet_limit": _resolved_snippet_limit(
            settings,
            test_mode=body.test_mode,
            requested=body.mismatch_snippet_limit,
        ),
    }
    if body.fixed_width_config is not None:
        meta["fixed_width_config"] = body.fixed_width_config.model_dump()
    if source_input is not None and source_input.is_cloud:
        meta["source_cloud"] = cloud_config_to_meta(source_cloud)  # type: ignore[arg-type]
    else:
        meta["source_path"] = str(resolved_source)
    if target_input is not None and target_input.is_cloud:
        meta["target_cloud"] = cloud_config_to_meta(target_cloud)  # type: ignore[arg-type]
    else:
        meta["target_path"] = str(resolved_target)
    try:
        src_sz = (
            int(source_input.adapter.get_size_bytes())
            if source_input is not None
            else resolved_source.stat().st_size
        )
        tgt_sz = (
            int(target_input.adapter.get_size_bytes())
            if target_input is not None
            else resolved_target.stat().st_size
        )
        enrich_meta_file_sizes(meta, source_bytes=src_sz, target_bytes=tgt_sz)
    except OSError:
        enrich_meta_file_sizes(meta)
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))

    (job_dir / "status.json").write_bytes(
        dumps_bytes(
            {
                "status": "queued",
                "phase": "queued",
                "message": "Job accepted, waiting for worker slot",
                "progress": {"enqueued_at_epoch_s": time.time()},
            },
            indent=True,
        )
    )

    queue = get_validation_queue(settings)
    queued_job = queue.enqueue(job_id, job_dir)
    poll = f"{settings.api_v1_prefix.rstrip('/')}/validate/jobs/{job_id}"
    queue_stats = queue.stats
    from pegasus.services.validation_job_queue import JobState

    accepted_status = (
        "running" if queued_job.state == JobState.RUNNING else "queued"
    )
    return ValidationJobAcceptedResponse(
        job_id=job_id,
        status=accepted_status,
        poll_url=poll,
        queue_position=queued_job.position if accepted_status == "queued" else None,
        queue_pending=queue_stats["pending"],
        queue_running=queue_stats["running"],
        max_concurrency=queue_stats["max_concurrency"],
    )


@router.post(
    "/validate/local/batch",
    response_model=ValidationJobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue batch comparison of multiple local file pairs",
)
async def validate_csv_local_batch(
    settings: AppSettings,
    body: Annotated[LocalBatchValidateRequest, Body()],
) -> ValidationJobAcceptedResponse:
    require_local_path_access(settings)
    if body.cloud_bucket:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cloud batch is not implemented on this endpoint; use local paths only",
        )

    batch_units: list[dict[str, object]] = []
    total_bytes = 0
    for unit in body.units:
        src = resolve_local_path_on_disk(Path(unit.source_paths[0]), settings, must_be_file=True)
        tgt = resolve_local_path_on_disk(Path(unit.target_paths[0]), settings, must_be_file=True)
        try:
            total_bytes += src.stat().st_size + tgt.stat().st_size
        except OSError:
            pass
        batch_units.append(
            {
                "unit_id": unit.unit_id,
                "source_path": str(src.resolve()),
                "target_path": str(tgt.resolve()),
                "source_paths": [str(src.resolve())],
                "target_paths": [str(tgt.resolve())],
                "uid_column": unit.uid_column,
                "column_mappings": [m.model_dump() for m in unit.column_mappings],
            }
        )

    job_id = uuid.uuid4()
    job_dir = validation_jobs_root(settings) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)

    meta: dict[str, object] = {
        "batch": True,
        "batch_units": batch_units,
        "on_unit_failure": body.on_unit_failure.value,
        "delimiter": body.delimiter,
        "has_header": body.has_header,
        "header_leading_rows": body.header_leading_rows,
        "validate_header_formats": body.validate_header_formats,
        "validate_footers": body.validate_footers,
        "footer_trailing_rows": body.footer_trailing_rows,
        "file_format": normalize_file_format(body.file_format),
        "test_mode": body.test_mode.value,
        "source_bytes": total_bytes // 2,
        "target_bytes": total_bytes // 2,
    }
    enrich_meta_file_sizes(meta, source_bytes=total_bytes // 2, target_bytes=total_bytes // 2)
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))
    (job_dir / "status.json").write_bytes(
        dumps_bytes(
            {
                "status": "queued",
                "phase": "queued",
                "message": f"Batch job accepted ({len(batch_units)} units)",
                "progress": {"total_units": len(batch_units), "enqueued_at_epoch_s": time.time()},
            },
            indent=True,
        )
    )

    queue = get_validation_queue(settings)
    queued_job = queue.enqueue(job_id, job_dir)
    poll = f"{settings.api_v1_prefix.rstrip('/')}/validate/jobs/{job_id}"
    queue_stats = queue.stats
    from pegasus.services.validation_job_queue import JobState

    accepted_status = "running" if queued_job.state == JobState.RUNNING else "queued"
    return ValidationJobAcceptedResponse(
        job_id=job_id,
        status=accepted_status,
        poll_url=poll,
        queue_position=queued_job.position if accepted_status == "queued" else None,
        queue_pending=queue_stats["pending"],
        queue_running=queue_stats["running"],
        max_concurrency=queue_stats["max_concurrency"],
    )


@router.get(
    "/validate/jobs/{job_id}",
    response_model=ValidationJobDetailResponse,
    summary="Poll a queued validation job",
)
async def get_validation_job(
    settings: AppSettings,
    job_id: uuid.UUID,
    summary_only: Annotated[
        bool,
        Query(
            description=(
                "When true (recommended for UI), return counts and metadata only without "
                "scanning the full mismatch artifact. Mismatch rows are available via "
                "GET /validate/jobs/{job_id}/mismatches or history mismatches."
            ),
        ),
    ] = False,
) -> ValidationJobDetailResponse:
    job_dir = validation_jobs_root(settings) / str(job_id)
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
    resource_profile = st.get("resource_profile") if isinstance(st.get("resource_profile"), dict) else None

    if status_val in {"queued", "running"}:
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
        return ValidationJobDetailResponse(
            status=status_val,
            phase=phase,
            message=message,
            progress=progress,
            resource_profile=resource_profile,
        )

    if status_val == "failed":
        return ValidationJobDetailResponse(
            status="failed",
            phase=phase,
            message=message,
            progress=progress,
            error=str(st.get("error") or "failed"),
            resource_profile=resource_profile,
        )

    if status_val != "completed":
        return ValidationJobDetailResponse(
            status=status_val,
            phase=phase,
            message=message,
            progress=progress,
            error=str(st.get("error") or ""),
            resource_profile=resource_profile,
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

    try:
        raw_result = loads_str(result_path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, TypeError, OSError):
        raw_result = {}
    if isinstance(raw_result, dict) and raw_result.get("batch"):
        from pegasus.schemas.validation import BatchValidateResponse

        batch_payload = {
            k: raw_result[k]
            for k in ("summary", "units", "on_unit_failure", "durations")
            if k in raw_result
        }
        return ValidationJobDetailResponse(
            status="completed",
            phase=phase,
            message=message,
            progress=progress,
            batch_result=BatchValidateResponse.model_validate(batch_payload),
            resource_profile=resource_profile,
        )

    cached = completed_job_cache_get(job_id)
    if cached is not None and (summary_only or cached.result is not None):
        if summary_only and cached.result is not None:
            groups = cached.result.mismatch_sample_groups
            has_samples = (
                len(groups.missing_in_target) > 0
                or len(groups.extra_in_target) > 0
                or len(groups.value_mismatch) > 0
            )
            if has_samples:
                cached = None
        elif not summary_only and cached.result is not None:
            groups = cached.result.mismatch_sample_groups
            has_samples = (
                len(groups.missing_in_target) > 0
                or len(groups.extra_in_target) > 0
                or len(groups.value_mismatch) > 0
            )
            if not has_samples and cached.result.mismatch_counts.value_mismatch > 0:
                cached = None
    if cached is not None:
        return cached

    import time

    run_result, rid, job_meta = run_result_from_job_dir(job_dir)
    if summary_only:
        schedule_persist_completed_job(
            settings,
            run_id=rid,
            run_result=run_result,
            job_meta=job_meta,
        )
        db_wall = 0.0
        t_build = time.perf_counter()
        payload = build_validate_response_summary_only(run_result=run_result, run_id=rid)
    else:
        db_wall = await maybe_persist_completed_job(
            settings, run_id=rid, run_result=run_result, job_meta=job_meta
        )
        t_build = time.perf_counter()
        payload = build_validate_response(settings=settings, run_result=run_result, run_id=rid)
    response_wall = time.perf_counter() - t_build
    record_poll_lifecycle(
        job_dir,
        database_wall_seconds=db_wall,
        response_build_wall_seconds=response_wall,
    )
    detail = ValidationJobDetailResponse(
        status="completed",
        phase=phase,
        message=message,
        progress=progress,
        result=payload,
        resource_profile=resource_profile,
    )
    completed_job_cache_put(job_id, detail)
    return detail


@router.get(
    "/validate/jobs/{job_id}/mismatches",
    response_model=ValidationHistoryMismatchesResponse,
    summary="Paginated mismatch rows for a completed validation job (reads on-disk NDJSON)",
)
async def list_validation_job_mismatches(
    settings: AppSettings,
    job_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=5000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    mismatch_type: Annotated[
        str | None,
        Query(description="Filter by missing_in_target | extra_in_target | value_mismatch"),
    ] = None,
) -> ValidationHistoryMismatchesResponse:
    job_dir = validation_jobs_root(settings) / str(job_id)
    status_path = job_dir / "status.json"
    if not status_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown job_id")
    try:
        st = loads_str(status_path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, TypeError, OSError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job status unavailable") from exc
    if str(st.get("status") or "") != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Job is not completed yet")
    result_path = job_dir / "result.json"
    if not result_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job result not found")

    rows, total, run_uuid = paginate_job_mismatch_rows(
        job_dir,
        limit=limit,
        offset=offset,
        mismatch_type=mismatch_type,
    )
    return ValidationHistoryMismatchesResponse(
        run_id=run_uuid or job_id,
        items=[
            ValidationHistoryMismatchRow(
                uid=str(r.get("uid") or ""),
                mismatch_type=str(r.get("mismatch_type") or ""),
                column_name=r.get("column_name"),
                source_value=r.get("source_value"),
                target_value=r.get("target_value"),
                row_detail=r.get("row_detail"),
            )
            for r in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/validate/queue",
    summary="Get validation job queue status, CPU info, and job list",
    response_model=QueueStatusResponse,
)
async def get_validation_queue_status(settings: AppSettings) -> QueueStatusResponse:
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


# Re-export for validation_history and other modules.
resolve_local_csv_path = resolve_local_csv_path

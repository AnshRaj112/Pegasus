# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T11:54:13Z
# --- END GENERATED FILE METADATA ---

"""Validation service — routes tabular full validation through Category-1 pipeline."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from pegasus.core.config import Settings
from pegasus.core.resource_tuning import align_partition_buckets_to_threads, cap_partition_buckets
from pegasus.services.queue_resource_policy import QueueResourcePolicy
from pegasus.core.workload_budget import plan_workload_budget
from pegasus.schemas.validation import (
    CloudFileProfileResponse,
    ColumnMapping,
    LitmusComparison,
    LitmusFileStats,
    ValidationTestMode,
)
from pegasus.services.exceptions import ValidationBadRequestError, ValidationUnprocessableError
from pegasus.services.validation_results import ValidationRunDurations, ValidationRunResult
from pegasus.validation.adapters.file_columnar import FileColumnarAdapter
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter, create_delimited_adapter
from pegasus.validation.comparators.models import MismatchReport, empty_mismatch_frame
from pegasus.validation.delimiter_resolve import resolve_delimiter_for_adapters, resolve_delimiter_for_paths
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.comparators.policy import build_compare_policy
from pegasus.validation.pipeline.fingerprint import filter_compare_columns, parse_identity_columns
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline
from pegasus.validation.pipeline.reporting import write_validation_results
from pegasus.validation.services.validation_run import pipeline_result_to_run_result

logger = logging.getLogger(__name__)


def _resolve_compare_columns(
    schema_names: list[str],
    uid_column: str,
    column_mappings: list[ColumnMapping] | None,
) -> list[str]:
    """Columns used for value comparison (never the UID / identity column)."""
    uid_cols = set(parse_identity_columns(uid_column))
    default = [c for c in schema_names if c not in uid_cols]
    if not column_mappings:
        return filter_compare_columns(default, schema_names)
    mapped = list(
        dict.fromkeys(
            m.source_column.strip()
            for m in column_mappings
            if m.source_column and m.source_column.strip() and m.source_column.strip() not in uid_cols
        )
    )
    return mapped if mapped else filter_compare_columns(default, schema_names)

__all__ = ("ValidationRunDurations", "ValidationRunResult", "ValidationService")


class ValidationService:
    """Orchestrates Category-1 tabular reconciliation."""

    __slots__ = ("_settings",)

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _pipeline_config(
        self,
        *,
        source_bytes: int,
        target_bytes: int,
        compare_column_count: int,
        identity_column_count: int = 1,
        resource_policy: dict[str, Any] | None = None,
    ) -> TabularPipelineConfig:
        import os

        from pegasus.core.workload_budget import _estimated_row_bytes
        from pegasus.validation.readers import native_multichar

        policy = resource_policy or {}
        memory_budget = int(
            policy.get("memory_budget_bytes") or self._settings.validation_memory_budget_bytes
        )
        target_duration = int(
            policy.get("target_duration_seconds") or self._settings.validation_target_duration_seconds
        )
        cpu_cores = os.cpu_count() or 1
        stamped_effective = policy.get("effective_threads_per_job")
        raw_threads = policy.get("threads_per_job")
        if stamped_effective is not None and int(stamped_effective) > 0:
            requested_max_workers = int(stamped_effective)
        elif raw_threads is not None and int(raw_threads) > 0:
            requested_max_workers = int(raw_threads)
        else:
            requested_max_workers = QueueResourcePolicy.from_settings(
                self._settings
            ).effective_threads(cpu_cores=cpu_cores)
        inline_native = native_multichar.native_extension_available()
        row_width = _estimated_row_bytes(
            compare_column_count=compare_column_count,
            identity_column_count=identity_column_count,
            inline_native_spill=inline_native,
        )
        min_row_bytes = max(48, 8 * (compare_column_count + identity_column_count) + 32)
        dense_source_rows = max(1, source_bytes // min_row_bytes)
        dense_target_rows = max(1, target_bytes // min_row_bytes)
        source_row_estimate = max(1, source_bytes // row_width, dense_source_rows)
        target_row_estimate = max(1, target_bytes // row_width, dense_target_rows)
        budget = plan_workload_budget(
            source_bytes=source_bytes,
            target_bytes=target_bytes,
            compare_column_count=compare_column_count,
            cpu_cores=cpu_cores,
            memory_budget_bytes=memory_budget,
            target_duration_seconds=target_duration,
            requested_chunk_rows=self._settings.validation_reconciliation_chunk_rows,
            requested_partition_buckets=cap_partition_buckets(
                self._settings.validation_reconciliation_partition_buckets,
                combined_file_bytes=source_bytes + target_bytes,
            ),
            requested_max_workers=requested_max_workers,
            requested_sub_partition_buckets=self._settings.validation_reconciliation_sub_partition_buckets,
            source_row_estimate=source_row_estimate,
            target_row_estimate=target_row_estimate,
            identity_column_count=identity_column_count,
            inline_native_spill=inline_native,
        )
        partition_buckets = align_partition_buckets_to_threads(
            budget.partition_buckets,
            budget.max_parallel_workers,
        )
        preset = self._settings.validation_tabular_partition_preset
        reconcile_workers = self._settings.validation_partition_reconcile_workers
        if reconcile_workers <= 0:
            reconcile_workers = budget.max_parallel_workers
        return TabularPipelineConfig(
            chunk_rows=budget.chunk_rows,
            partition_count=partition_buckets,
            partition_preset=preset,
            enable_column_drilldown=self._settings.validation_tabular_enable_column_drilldown,
            enable_in_memory_reconcile=self._settings.validation_enable_in_memory_reconcile,
            auto_in_memory_max_bytes=self._settings.validation_auto_in_memory_max_bytes,
            memory_budget_bytes=memory_budget,
            disk_headroom_multiplier=float(
                policy.get("disk_headroom_multiplier")
                or self._settings.validation_reconciliation_disk_headroom_multiplier
            ),
            enable_merkle_fast_path=self._settings.validation_enable_merkle_fast_path,
            enable_content_digest_precheck=self._settings.validation_enable_content_digest_precheck,
            lazy_column_drilldown=True,
            fingerprint_only_spill=True,
            force_native_multichar_spill=True,
            use_arrow_ipc_spill=True,
            partition_reconcile_workers=reconcile_workers,
            gcs_streaming_only=self._settings.validation_gcs_streaming_only,
            partition_wave_size=self._settings.validation_reconciliation_partition_wave_size,
            wave_min_bytes=self._settings.validation_reconciliation_wave_min_bytes,
            partition_reconcile_use_processes=self._settings.validation_partition_reconcile_use_processes,
            distributed_enabled=self._settings.validation_distributed_enabled,
            distributed_redis_url=self._settings.validation_redis_url,
            distributed_min_bytes=self._settings.validation_distributed_min_bytes,
            stream_mismatches_to_disk=self._settings.validation_stream_mismatches_to_disk,
        )

    def _resolve_delimiter(
        self,
        delimiter: str,
        source_path: Path,
        target_path: Path | None = None,
    ) -> str:
        try:
            return resolve_delimiter_for_paths(delimiter, source_path, target_path)
        except ValueError as exc:
            raise ValidationBadRequestError(str(exc)) from exc

    def _rebuild_delimited_adapter(
        self,
        adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
        *,
        delimiter: str,
        has_header: bool,
        skip_rows: int,
    ) -> FileDelimitedAdapter | GcsDelimitedAdapter:
        if isinstance(adapter, GcsDelimitedAdapter):
            from pegasus.validation.adapters.gcs_delimited import inherit_gcs_metadata

            rebuilt = GcsDelimitedAdapter(
                adapter._ref,
                delimiter=delimiter,
                has_header=has_header,
                skip_rows=skip_rows,
                size_bytes=adapter.get_size_bytes(),
            )
            inherit_gcs_metadata(adapter, rebuilt)
            return rebuilt
        return FileDelimitedAdapter(
            adapter.path,
            delimiter=delimiter,
            has_header=has_header,
            skip_rows=skip_rows,
        )

    def _resolve_delimiter_for_inputs(
        self,
        delimiter: str,
        source: FileDelimitedAdapter | GcsDelimitedAdapter,
        target: FileDelimitedAdapter | GcsDelimitedAdapter,
    ) -> str:
        from pegasus.validation.delimiter_resolve import resolve_delimiter_for_adapters

        try:
            return resolve_delimiter_for_adapters(delimiter, source, target)
        except ValueError as exc:
            raise ValidationBadRequestError(str(exc)) from exc

    def _validate_delimited_adapters_sync(
        self,
        source: FileDelimitedAdapter | GcsDelimitedAdapter,
        target: FileDelimitedAdapter | GcsDelimitedAdapter,
        uid_column: str,
        delimiter: str = "auto",
        column_mappings: list[ColumnMapping] | None = None,
        *,
        source_label: str,
        target_label: str,
        artifact_export_parent: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        has_header: bool = True,
        header_leading_rows: int = 0,
        file_format: str = "csv",
        resource_policy: dict[str, Any] | None = None,
        test_mode: ValidationTestMode = ValidationTestMode.FULL,
    ) -> ValidationRunResult:
        if test_mode == ValidationTestMode.LITMUS:
            raise ValidationBadRequestError("Litmus mode is not supported for cloud streaming inputs yet")

        if progress_callback:
            progress_callback({"phase": "planning", "message": "Planning reconciliation budget"})

        sep = self._resolve_delimiter_for_inputs(delimiter, source, target)
        source = self._rebuild_delimited_adapter(
            source, delimiter=sep, has_header=has_header, skip_rows=header_leading_rows
        )
        target = self._rebuild_delimited_adapter(
            target, delimiter=sep, has_header=has_header, skip_rows=header_leading_rows
        )

        from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter, prefetch_gcs_delimited_pair
        from pegasus.validation.lifecycle_profiler import get_active_profiler, lifecycle_span

        needs_warm = any(
            isinstance(adapter, GcsDelimitedAdapter)
            and (
                adapter._crc32c is None
                or adapter._md5_hex is None
                or adapter._size_bytes is None
            )
            for adapter in (source, target)
        )
        if needs_warm:
            with lifecycle_span("GCS Prefetch"):
                prefetch_gcs_delimited_pair(source, target)

        with lifecycle_span("Schema And Planning"):
            schema = source.get_schema()
        compare_columns = _resolve_compare_columns(schema.column_names, uid_column, column_mappings)
        compare_policy = build_compare_policy(
            source,
            target,
            compare_columns,
            column_mappings,
            schema_names=schema.column_names,
            uid_column=uid_column,
        )
        compare_columns = compare_policy.compare_keys
        identity_columns = parse_identity_columns(uid_column) or [uid_column.strip()]

        cfg = self._pipeline_config(
            source_bytes=source.get_size_bytes(),
            target_bytes=target.get_size_bytes(),
            compare_column_count=len(compare_columns),
            identity_column_count=len(identity_columns),
            resource_policy=resource_policy,
        )
        cfg.compare_policy = compare_policy
        if artifact_export_parent is not None:
            cfg.distributed_job_id = str(artifact_export_parent.name)
        combined_bytes = source.get_size_bytes() + target.get_size_bytes()
        logger.info(
            "reconciliation delimiter=%r source_bytes=%s target_bytes=%s in_memory=%s "
            "chunk_rows=%s partitions=%s reconcile_workers=%s",
            sep,
            source.get_size_bytes(),
            target.get_size_bytes(),
            cfg.enable_in_memory_reconcile
            and combined_bytes <= cfg.auto_in_memory_max_bytes,
            cfg.chunk_rows,
            cfg.resolved_partition_count(),
            cfg.partition_reconcile_workers,
        )

        workspace = None
        if artifact_export_parent is not None:
            workspace = artifact_export_parent / "reconcile_workspace"
            workspace.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback({"phase": "reconciling", "message": "Running streaming reconciliation"})

        if artifact_export_parent is not None:
            from pegasus.validation.pipeline.timing import configure_stage_metrics_log

            configure_stage_metrics_log(artifact_export_parent / "stage_metrics.log")

        profiler = get_active_profiler()
        if profiler is not None:
            profiler.mark_validation_started()

        t0 = time.perf_counter()
        pipeline = TabularReconciliationPipeline(
            source,
            target,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            config=cfg,
        )
        try:
            result = pipeline.run(workspace=workspace, progress_callback=progress_callback)
        finally:
            if artifact_export_parent is not None:
                from pegasus.validation.pipeline.timing import configure_stage_metrics_log

                configure_stage_metrics_log(None)
        elapsed = time.perf_counter() - t0
        if profiler is not None:
            extra = result.extra_stats or {}
            profiler.ingest_pipeline_stages(list(extra.get("stages") or []))

        if artifact_export_parent is not None and not self._settings.validation_skip_artifact_report:
            report_cpu_start = time.thread_time()
            report_wall_start = time.perf_counter()
            with lifecycle_span("Report Generation"):
                write_validation_results(
                    artifact_export_parent / "VALIDATION_RESULTS.md",
                    result,
                    source_label=source_label,
                    target_label=target_label,
                    extra_stats={
                        "memory_budget_bytes": cfg.memory_budget_bytes,
                        "chunk_rows": cfg.chunk_rows,
                        "partition_count": cfg.resolved_partition_count(),
                    },
                )
            extra = result.extra_stats or {}
            if extra.get("timings"):
                from pegasus.validation.pipeline.timing import refresh_report_stage

                refresh_report_stage(
                    extra,
                    wall_seconds=time.perf_counter() - report_wall_start,
                    cpu_seconds=time.thread_time() - report_cpu_start,
                )
                from pegasus.validation.pipeline.timing import (
                    _io_from_mapping,
                    _timings_from_mapping,
                    build_stage_metrics,
                    publish_stage,
                )

                timings = _timings_from_mapping(dict(extra.get("timings") or {}))
                io = _io_from_mapping(dict(extra.get("io") or {}))
                for stage in build_stage_metrics(timings, io):
                    if stage.name in ("Report", "Total"):
                        publish_stage(stage, progress_callback=progress_callback)
                result.extra_stats = extra

        run_result = pipeline_result_to_run_result(result)
        run_result.durations = ValidationRunDurations(validation_seconds=elapsed)
        return run_result

    def _validate_csv_pair_sync(
        self,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str = "auto",
        column_mappings: list[ColumnMapping] | None = None,
        *,
        artifact_export_parent: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        has_header: bool = True,
        header_leading_rows: int = 0,
        file_format: str = "csv",
        resource_policy: dict[str, Any] | None = None,
        test_mode: ValidationTestMode = ValidationTestMode.FULL,
    ) -> ValidationRunResult:
        source_path = source_path.resolve()
        target_path = target_path.resolve()
        if not source_path.is_file():
            raise ValidationBadRequestError(f"Source file not found: {source_path}")
        if not target_path.is_file():
            raise ValidationBadRequestError(f"Target file not found: {target_path}")

        if test_mode == ValidationTestMode.LITMUS:
            return self.validate_csv_litmus_sync(source_path, target_path, delimiter=delimiter)

        source = FileDelimitedAdapter(
            source_path, delimiter=delimiter, has_header=has_header, skip_rows=header_leading_rows
        )
        target = FileDelimitedAdapter(
            target_path, delimiter=delimiter, has_header=has_header, skip_rows=header_leading_rows
        )
        return self._validate_delimited_adapters_sync(
            source,
            target,
            uid_column,
            delimiter,
            column_mappings,
            source_label=str(source_path),
            target_label=str(target_path),
            artifact_export_parent=artifact_export_parent,
            progress_callback=progress_callback,
            has_header=has_header,
            header_leading_rows=header_leading_rows,
            file_format=file_format,
            resource_policy=resource_policy,
            test_mode=test_mode,
        )

    def preview_column_headers_from_adapters(
        self,
        *,
        source: FileDelimitedAdapter | GcsDelimitedAdapter,
        target: FileDelimitedAdapter | GcsDelimitedAdapter,
        uid_column: str,
        delimiter: str = "auto",
        has_header: bool = True,
        header_leading_rows: int = 0,
        file_format: str | None = None,
    ) -> dict[str, object]:
        from pegasus.validation.column_preview import build_column_preview_from_adapters

        sep = self._resolve_delimiter_for_inputs(delimiter, source, target)
        source = self._rebuild_delimited_adapter(
            source, delimiter=sep, has_header=has_header, skip_rows=header_leading_rows
        )
        target = self._rebuild_delimited_adapter(
            target, delimiter=sep, has_header=has_header, skip_rows=header_leading_rows
        )
        return build_column_preview_from_adapters(
            source=source,
            target=target,
            uid_column=uid_column,
            resolved_delimiter=sep,
            has_header=has_header,
            file_format=file_format or "csv",
        )

    def profile_delimited_adapter(
        self,
        adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
        *,
        object_name: str,
        gcs_uri: str,
        delimiter: str = "auto",
        has_header: bool = True,
        skip_rows: int = 0,
    ) -> CloudFileProfileResponse:
        from pegasus.validation.cloud_profile import build_delimited_profile

        sep = self._resolve_delimiter_for_inputs(delimiter, adapter, adapter)
        adapter = self._rebuild_delimited_adapter(
            adapter, delimiter=sep, has_header=has_header, skip_rows=skip_rows
        )
        return build_delimited_profile(
            adapter,
            object_name=object_name,
            gcs_uri=gcs_uri,
            resolved_delimiter=sep,
            has_header=has_header,
        )

    def validate_columnar_pair_sync(
        self,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        file_format: str,
        *,
        artifact_export_parent: Path | None = None,
        resource_policy: dict[str, Any] | None = None,
    ) -> ValidationRunResult:
        src_adapter = FileColumnarAdapter(source_path, file_format=file_format)
        tgt_adapter = FileColumnarAdapter(target_path, file_format=file_format)
        schema = src_adapter.get_schema()
        identity_columns = parse_identity_columns(uid_column) or [uid_column.strip()]
        compare_columns = [c for c in schema.column_names if c not in identity_columns]
        cfg = self._pipeline_config(
            source_bytes=source_path.stat().st_size,
            target_bytes=target_path.stat().st_size,
            compare_column_count=len(compare_columns),
            identity_column_count=len(identity_columns),
            resource_policy=resource_policy,
        )
        workspace = None
        if artifact_export_parent is not None:
            workspace = artifact_export_parent / "reconcile_workspace"
            workspace.mkdir(parents=True, exist_ok=True)
        pipeline = TabularReconciliationPipeline(
            src_adapter,
            tgt_adapter,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            config=cfg,
        )
        result = pipeline.run(workspace=workspace)
        if artifact_export_parent is not None:
            write_validation_results(
                artifact_export_parent / "VALIDATION_RESULTS.md",
                result,
                source_label=str(source_path),
                target_label=str(target_path),
            )
        return pipeline_result_to_run_result(result)

    def preview_local_column_headers(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str = "auto",
        has_header: bool = True,
        header_leading_rows: int = 0,
        file_format: str | None = None,
    ) -> dict[str, object]:
        """Return source/target headers and exact-name mapping suggestions for the UI."""
        from pegasus.validation.column_preview import build_column_preview

        return build_column_preview(
            source_path=source_path,
            target_path=target_path,
            uid_column=uid_column,
            delimiter=delimiter,
            has_header=has_header,
            header_leading_rows=header_leading_rows,
            file_format=file_format,
        )

    def validate_csv_litmus_sync(
        self,
        source_path: Path,
        target_path: Path,
        *,
        delimiter: str = "auto",
    ) -> ValidationRunResult:
        """Fast structural checks without full reconciliation."""
        sep = self._resolve_delimiter(delimiter, source_path, target_path)
        src = FileDelimitedAdapter(source_path, delimiter=sep)
        tgt = FileDelimitedAdapter(target_path, delimiter=sep)
        src_schema = src.get_schema()
        tgt_schema = tgt.get_schema()
        litmus = LitmusComparison(
            checks_run=["size", "columns", "row_count"],
            checks_passed=[],
            checks_failed=[],
            source=LitmusFileStats(
                path=str(source_path),
                size_bytes=source_path.stat().st_size,
                row_count=src.get_row_count() or 0,
                column_count=len(src_schema.column_names),
                columns=src_schema.column_names,
            ),
            target=LitmusFileStats(
                path=str(target_path),
                size_bytes=target_path.stat().st_size,
                row_count=tgt.get_row_count() or 0,
                column_count=len(tgt_schema.column_names),
                columns=tgt_schema.column_names,
            ),
        )
        if litmus.source.columns == litmus.target.columns:
            litmus.checks_passed.append("columns")
        else:
            litmus.checks_failed.append("columns")
        if litmus.source.size_bytes and litmus.target.size_bytes:
            litmus.checks_passed.append("size")
        if litmus.source.row_count == litmus.target.row_count:
            litmus.checks_passed.append("row_count")
        else:
            litmus.checks_failed.append("row_count")

        is_match = not litmus.checks_failed
        return ValidationRunResult(
            report=MismatchReport(mismatches=empty_mismatch_frame(), summary={}),
            source_row_count=litmus.source.row_count,
            target_row_count=litmus.target.row_count,
            compared_column_count=0,
            compared_columns=[],
            test_mode="litmus",
            litmus=litmus.model_dump(),
        )

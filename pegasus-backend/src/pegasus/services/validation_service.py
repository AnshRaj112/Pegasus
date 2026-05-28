"""Orchestrates CSV load and UID-based comparison (blocking Polars in a thread pool)."""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import csv
from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd
import polars as pl

from pegasus.core.config import Settings
from pegasus.schemas.validation import ColumnMapping
from pegasus.core.resource_tuning import (
    align_partition_buckets_to_threads,
    cap_partition_buckets,
    log_swap_pressure_warning,
    max_reconciliation_partition_buckets,
    physical_cpu_count,
    physical_ram_bytes,
)
from pegasus.services.queue_resource_policy import (
    QueueResourcePolicy,
    apply_queue_policy_to_reconciliation_config,
)
from pegasus.services.exceptions import (
    ValidationBadRequestError,
    ValidationUnprocessableError,
)
from pegasus.validation.comparators.exceptions import UIDComparisonError
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame
from pegasus.validation.compare_rules import build_rules_by_source_column
from pegasus.validation.comparators.uid_based import UIDBasedComparator
from pegasus.validation.readers.exceptions import (
    CSVFileNotFoundError,
    CSVParseError,
    CSVValidationError,
)
from pegasus.validation.readers.delimiter_detection import (
    polars_supports_csv_delimiter,
    resolve_shared_auto_delimiter,
)
from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader
from pegasus.validation.reconciliation.config import (
    ReconciliationRuntimeConfig,
    ReconciliationStrategy,
)
from pegasus.validation.reconciliation.coordinator import (
    ReconciliationCoordinator,
    auto_external_enabled,
)
from pegasus.validation.reconciliation.exceptions import ReconciliationError, ReconciliationStrategyError
from pegasus.validation.csv_header import infer_csv_has_header
from pegasus.validation.mapping_analyze import analyze_column_mappings, sample_column_values
from pegasus.validation.reconciliation.partition_manager import multichar_csv_header_frame
from pegasus.validation.csv_preflight import CsvPreflightError, preflight_csv_structure
from pegasus.validation.flat_file import csv_has_data_rows
from pegasus.validation.fixed_width_dates import normalize_strptime_format, parse_fixed_width_date
from pegasus.validation.fixed_width_layout import preview_fixed_width_layout
from pegasus.validation.fixed_width_matching import fuzzy_pair_by_join_key

logger = logging.getLogger(__name__)

_MAPPING_PREVIEW_SAMPLE_ROWS = 6
_LITMUS_LINE_ESTIMATE_THRESHOLD_BYTES = 2 * 1024 * 1024
_LITMUS_SAMPLE_BYTES = 256 * 1024
_LITMUS_STATS_CACHE_MAX = 256
_LITMUS_STATS_CACHE: "OrderedDict[tuple[str, int, int], dict[str, Any]]" = OrderedDict()


@dataclass(slots=True)
class ValidationRunDurations:
    """Timing metadata for a validation job."""

    upload_seconds: float | None = None
    validation_seconds: float | None = None
    total_seconds: float | None = None


@dataclass(slots=True)
class ValidationRunResult:
    """Outcome of a single validation run."""

    report: MismatchReport
    source_row_count: int
    target_row_count: int
    compared_column_count: int
    compared_columns: list[str]
    mismatch_artifact_path: Path | None = None
    mapping_format_checks: list[dict[str, Any]] | None = None
    footer_validation: dict[str, Any] | None = None
    test_mode: str = "full"
    litmus: dict[str, Any] | None = None
    durations: ValidationRunDurations | None = None


class ValidationService:
    """Load two CSV files and compare rows on a shared UID column."""

    __slots__ = ("_settings",)

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _reconciliation_runtime_config(
        self, *, artifact_export_parent: Path | None = None
    ) -> ReconciliationRuntimeConfig:
        raw = (self._settings.validation_reconciliation_strategy or "").strip().lower()
        try:
            strategy = ReconciliationStrategy(raw)
        except ValueError:
            strategy = ReconciliationStrategy.AUTO
        temp = self._settings.validation_reconciliation_temp_dir
        artifact_export = None
        if artifact_export_parent is not None:
            artifact_export_parent.mkdir(parents=True, exist_ok=True)
            artifact_export = artifact_export_parent / "mismatches.ndjson"
        return ReconciliationRuntimeConfig(
            strategy=strategy,
            chunk_rows=self._settings.validation_reconciliation_chunk_rows,
            partition_buckets=self._settings.validation_reconciliation_partition_buckets,
            sliding_window=self._settings.validation_reconciliation_sliding_window,
            assume_sorted=self._settings.validation_reconciliation_assume_sorted,
            temp_dir=Path(temp) if temp else None,
            retry_max_attempts=self._settings.validation_reconciliation_retry_attempts,
            external_memory_threshold_bytes=self._settings.validation_external_memory_threshold_bytes,
            stringify_null_in_report=True,
            sub_partition_buckets=self._settings.validation_reconciliation_sub_partition_buckets,
            parallel_spill_sides=self._settings.validation_reconciliation_parallel_spill,
            disk_headroom_multiplier=self._settings.validation_reconciliation_disk_headroom_multiplier,
            mismatch_ndjson_mirror=self._settings.validation_reconciliation_mismatch_ndjson_mirror,
            force_external=self._settings.validation_force_external_reconciliation,
            stream_mismatches=self._settings.validation_stream_mismatches_to_disk,
            artifact_export_path=artifact_export,
        )

    def _apply_host_reconciliation_tuning(
        self,
        rcfg: ReconciliationRuntimeConfig,
        *,
        source_path: Path,
        target_path: Path,
        resource_policy: QueueResourcePolicy | None = None,
    ) -> ReconciliationRuntimeConfig:
        """Clamp partition counts using host CPU and RAM hints."""
        cores = physical_cpu_count()
        ncpu = (
            resource_policy.effective_threads(cpu_cores=cores)
            if resource_policy is not None
            else cores
        )
        ram = physical_ram_bytes()

        orig_pb = rcfg.partition_buckets
        pb = cap_partition_buckets(orig_pb, ncpu=ncpu, ram_bytes=ram)
        pb = align_partition_buckets_to_threads(pb, ncpu)

        updates: dict[str, object] = {}
        if pb != orig_pb:
            updates["partition_buckets"] = pb

        if updates:
            logger.info(
                "Host-tuned reconciliation (cpus=%d max_partition_cap=%d): %s",
                ncpu,
                max_reconciliation_partition_buckets(ncpu=ncpu, ram_bytes=ram),
                ", ".join(f"{k}={v}" for k, v in updates.items()),
            )
            return rcfg.model_copy(update=updates)
        return rcfg

    async def validate_csv_pair(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        column_mappings: Sequence[ColumnMapping] | None = None,
        artifact_export_parent: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        validate_header_formats: bool = False,
        validate_footers: bool = False,
        footer_trailing_rows: int = 1,
        has_header: bool = True,
        header_leading_rows: int = 0,
        uid_gte: str | None = None,
    ) -> ValidationRunResult:
        """Run validation off the event loop so Polars work does not block asyncio."""
        return await asyncio.to_thread(
            self._validate_csv_pair_sync,
            source_path,
            target_path,
            uid_column,
            delimiter,
            list(column_mappings or []),
            artifact_export_parent,
            progress_callback,
            validate_header_formats,
            validate_footers,
            footer_trailing_rows,
            has_header,
            header_leading_rows,
            uid_gte,
        )

    def validate_csv_litmus_sync(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        has_header: bool = True,
        header_leading_rows: int = 0,
    ) -> ValidationRunResult:
        """Run quick structural checks without row-level mismatch comparison."""
        del uid_column  # not required for litmus mode
        delim = self._resolve_delimiter(
            source_path=source_path,
            target_path=target_path,
            delimiter=delimiter,
        )
        prepared_source, prepared_target, cleanup_paths = self._prepare_csv_pair_for_comparison(
            source_path=source_path,
            target_path=target_path,
            header_leading_rows=header_leading_rows,
            footer_trailing_rows=0,
        )
        try:
            source_stats = self._quick_csv_litmus_stats(
                prepared_source,
                delimiter=delim,
                has_header=has_header,
            )
            target_stats = self._quick_csv_litmus_stats(
                prepared_target,
                delimiter=delim,
                has_header=has_header,
            )
            checks_run = [
                "file_name",
                "file_type",
                "file_size",
                "row_count",
                "column_count",
                "column_names",
            ]
            checks_passed: list[str] = []
            checks_failed: list[str] = []
            notes: list[str] = []
            if source_path.name == target_path.name:
                checks_passed.append("file_name")
            else:
                checks_failed.append("file_name")
            checks_passed.append("file_type")
            if source_path.stat().st_size == target_path.stat().st_size:
                checks_passed.append("file_size")
            else:
                checks_failed.append("file_size")
                notes.append("File sizes differ.")
            if source_stats["row_count"] == target_stats["row_count"]:
                checks_passed.append("row_count")
            else:
                checks_failed.append("row_count")
                notes.append("Row counts differ.")
            if source_path.stat().st_size > _LITMUS_LINE_ESTIMATE_THRESHOLD_BYTES:
                notes.append("Source row count is estimated for speed (turbo litmus).")
            if target_path.stat().st_size > _LITMUS_LINE_ESTIMATE_THRESHOLD_BYTES:
                notes.append("Target row count is estimated for speed (turbo litmus).")
            if source_stats["column_count"] == target_stats["column_count"]:
                checks_passed.append("column_count")
            else:
                checks_failed.append("column_count")
                notes.append("Column counts differ.")
            if source_stats["columns"] == target_stats["columns"]:
                checks_passed.append("column_names")
            else:
                checks_failed.append("column_names")
                notes.append("Column names/order differ.")

            litmus = {
                "checks_run": checks_run,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "source": {
                    "path": str(source_path),
                    "file_name": source_path.name,
                    "file_type": "csv",
                    "size_bytes": source_path.stat().st_size,
                    "row_count": int(source_stats["row_count"]),
                    "column_count": int(source_stats["column_count"]),
                    "columns": list(source_stats["columns"]),
                },
                "target": {
                    "path": str(target_path),
                    "file_name": target_path.name,
                    "file_type": "csv",
                    "size_bytes": target_path.stat().st_size,
                    "row_count": int(target_stats["row_count"]),
                    "column_count": int(target_stats["column_count"]),
                    "columns": list(target_stats["columns"]),
                },
                "notes": notes,
            }
            return ValidationRunResult(
                report=MismatchReport(
                    mismatches=empty_mismatch_frame(),
                    summary={
                        MismatchType.MISSING_IN_TARGET.value: 0,
                        MismatchType.EXTRA_IN_TARGET.value: 0,
                        MismatchType.VALUE_MISMATCH.value: len(checks_failed),
                    },
                ),
                source_row_count=int(source_stats["row_count"]),
                target_row_count=int(target_stats["row_count"]),
                compared_column_count=min(int(source_stats["column_count"]), int(target_stats["column_count"])),
                compared_columns=[c for c in source_stats["columns"] if c in set(target_stats["columns"])],
                test_mode="litmus",
                litmus=litmus,
            )
        finally:
            for p in cleanup_paths:
                p.unlink(missing_ok=True)

    @staticmethod
    def _quick_csv_litmus_stats(
        path: Path,
        *,
        delimiter: str,
        has_header: bool,
    ) -> dict[str, Any]:
        """Fast byte-level CSV stats for litmus mode."""
        stat = path.stat()
        cache_key = (str(path), stat.st_size, stat.st_mtime_ns)
        cached = _LITMUS_STATS_CACHE.get(cache_key)
        if cached is not None:
            _LITMUS_STATS_CACHE.move_to_end(cache_key)
            return dict(cached)

        line_count = ValidationService._fast_line_count(path, stat.st_size)

        header_line = ValidationService._first_non_empty_line(path)
        columns = ValidationService._split_csv_line(header_line, delimiter=delimiter) if header_line else []
        if not has_header:
            columns = [f"column_{idx}" for idx in range(1, len(columns) + 1)]
        data_rows = max(line_count - (1 if has_header and line_count > 0 else 0), 0)
        out = {
            "row_count": data_rows,
            "column_count": len(columns),
            "columns": columns,
        }
        _LITMUS_STATS_CACHE[cache_key] = dict(out)
        _LITMUS_STATS_CACHE.move_to_end(cache_key)
        while len(_LITMUS_STATS_CACHE) > _LITMUS_STATS_CACHE_MAX:
            _LITMUS_STATS_CACHE.popitem(last=False)
        return out

    @staticmethod
    def _fast_line_count(path: Path, file_size: int) -> int:
        if file_size <= 0:
            return 0
        if file_size <= _LITMUS_LINE_ESTIMATE_THRESHOLD_BYTES:
            return ValidationService._exact_line_count(path)
        return ValidationService._estimated_line_count(path, file_size)

    @staticmethod
    def _exact_line_count(path: Path) -> int:
        line_count = 0
        saw_any = False
        last_chunk_ended_with_newline = True
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(8 * 1024 * 1024)
                if not chunk:
                    break
                saw_any = True
                line_count += chunk.count(b"\n")
                last_chunk_ended_with_newline = chunk.endswith(b"\n")
        if saw_any and not last_chunk_ended_with_newline:
            line_count += 1
        return line_count

    @staticmethod
    def _estimated_line_count(path: Path, file_size: int) -> int:
        sample_size = min(_LITMUS_SAMPLE_BYTES, file_size)
        with path.open("rb") as handle:
            sample = handle.read(sample_size)
            if not sample:
                return 0
            newline_count = sample.count(b"\n")
            if newline_count <= 0:
                return 1
            estimated = int((newline_count / sample_size) * file_size)
            if not sample.endswith(b"\n"):
                estimated += 1
            return max(estimated, 1)

    @staticmethod
    def _first_non_empty_line(path: Path) -> str:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    return stripped
        return ""

    @staticmethod
    def _split_csv_line(line: str, *, delimiter: str) -> list[str]:
        if not line:
            return []
        if delimiter and len(delimiter) == 1:
            try:
                return next(csv.reader([line], delimiter=delimiter))
            except Exception:
                pass
        # Multi-char delimiter fallback for litmus mode.
        if not delimiter:
            return [line]
        return [part.strip() for part in line.split(delimiter)]

    def analyze_local_mappings(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        column_mappings: list[ColumnMapping],
        validate_header_formats: bool,
        validate_footers: bool,
        footer_trailing_rows: int,
        has_header: bool = True,
        header_leading_rows: int = 0,
    ) -> dict[str, Any]:
        """Run optional format/footer checks for the mapping wizard."""
        delim = self._resolve_delimiter(
            source_path=source_path,
            target_path=target_path,
            delimiter=delimiter,
        )
        analysis = analyze_column_mappings(
            source_path=source_path,
            target_path=target_path,
            delimiter=delim,
            column_mappings=column_mappings,
            validate_header_formats=validate_header_formats,
            validate_footers=validate_footers,
            footer_trailing_rows=footer_trailing_rows,
            has_header=has_header,
            header_leading_rows=header_leading_rows,
        )
        analysis["delimiter"] = delim
        return analysis

    def preview_fixed_width_layout(
        self,
        *,
        source_path: Path,
        target_path: Path,
    ) -> dict[str, Any]:
        """Infer column slices from the first non-empty line of each file."""
        return preview_fixed_width_layout(
            source_path=str(source_path),
            target_path=str(target_path),
        )

    def preview_local_column_headers(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        has_header: bool = True,
        header_leading_rows: int = 0,
    ) -> dict[str, Any]:
        """Return source/target headers and exact-name mapping suggestions for the UI."""
        uid = uid_column.strip()
        delim = self._resolve_delimiter(
            source_path=source_path,
            target_path=target_path,
            delimiter=delimiter,
        )
        prepared_source, prepared_target, cleanup_paths = self._prepare_csv_pair_for_comparison(
            source_path=source_path,
            target_path=target_path,
            header_leading_rows=header_leading_rows,
            footer_trailing_rows=0,
        )
        try:
            inferred_has_header = infer_csv_has_header(prepared_source, delim) and infer_csv_has_header(
                prepared_target, delim
            )
            self._preflight_csv_pair(prepared_source, prepared_target, delim, has_header=has_header)
            source_columns = self._read_column_names(prepared_source, delim, has_header=has_header)
            target_columns = self._read_column_names(prepared_target, delim, has_header=has_header)
            compare_columns = [c for c in source_columns if c != uid]
            compare_targets = [c for c in target_columns if c != uid]
            auto_mappings = self._auto_map_columns(compare_columns, compare_targets)
            matched_sources = {m["source_column"] for m in auto_mappings}
            matched_targets = {m["target_column"] for m in auto_mappings}
            sample_rows = _MAPPING_PREVIEW_SAMPLE_ROWS
            source_samples = sample_column_values(
                prepared_source,
                delimiter=delim,
                columns=source_columns,
                sample_rows=sample_rows,
                has_header=has_header,
            )
            target_samples = sample_column_values(
                prepared_target,
                delimiter=delim,
                columns=target_columns,
                sample_rows=sample_rows,
                has_header=has_header,
            )
            return {
                "source_columns": source_columns,
                "target_columns": target_columns,
                "compare_columns": compare_columns,
                "auto_mappings": auto_mappings,
                "unmatched_source_columns": [c for c in source_columns if c not in matched_sources],
                "unmatched_target_columns": [c for c in target_columns if c not in matched_targets],
                "delimiter": delim,
                "has_header": has_header,
                "inferred_has_header": inferred_has_header,
                "source_samples": source_samples,
                "target_samples": target_samples,
                "sample_row_count": sample_rows,
            }
        finally:
            for p in cleanup_paths:
                p.unlink(missing_ok=True)

    def _validate_csv_pair_sync(
        self,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        column_mappings: list[ColumnMapping] | None = None,
        artifact_export_parent: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        validate_header_formats: bool = False,
        validate_footers: bool = False,
        footer_trailing_rows: int = 1,
        has_header: bool = True,
        header_leading_rows: int = 0,
        uid_gte: str | None = None,
        resource_policy: dict[str, object] | None = None,
    ) -> ValidationRunResult:
        uid = uid_column.strip()
        if not uid:
            raise ValidationBadRequestError("uid_column must be a non-empty string")
        original_source_path = source_path
        original_target_path = target_path

        queue_policy = QueueResourcePolicy.from_dict(
            dict(resource_policy) if resource_policy else None,
            settings=self._settings,
        ).clamp(cpu_cores=physical_cpu_count())

        rcfg = self._reconciliation_runtime_config(artifact_export_parent=artifact_export_parent)
        rcfg = apply_queue_policy_to_reconciliation_config(
            rcfg,
            queue_policy,
            cpu_cores=physical_cpu_count(),
        )
        delim = self._resolve_delimiter(
            source_path=source_path,
            target_path=target_path,
            delimiter=delimiter,
        )
        source_path, target_path, _cleanup_paths = self._prepare_csv_pair_for_comparison(
            source_path=source_path,
            target_path=target_path,
            header_leading_rows=header_leading_rows,
            footer_trailing_rows=footer_trailing_rows if validate_footers else 0,
        )
        rcfg = rcfg.model_copy(update={"has_header": has_header})

        mapping_analysis: dict[str, Any] | None = None
        if validate_header_formats or validate_footers:
            mappings = column_mappings or []
            if validate_header_formats and not mappings:
                compare_src = [
                    c
                    for c in self._read_column_names(source_path, delim, has_header=has_header)
                    if c != uid
                ]
                compare_tgt = [
                    c
                    for c in self._read_column_names(target_path, delim, has_header=has_header)
                    if c != uid
                ]
                auto = self._auto_map_columns(compare_src, compare_tgt)
                mappings = [ColumnMapping.model_validate(m) for m in auto]
            mapping_analysis = analyze_column_mappings(
                source_path=source_path,
                target_path=target_path,
                delimiter=delim,
                column_mappings=mappings,
                validate_header_formats=validate_header_formats,
                validate_footers=validate_footers,
                footer_trailing_rows=footer_trailing_rows,
                has_header=has_header,
                header_leading_rows=0,
                footer_validation_source_path=original_source_path,
                footer_validation_target_path=original_target_path,
            )

        self._raise_if_csv_pair_has_no_data(source_path, target_path)

        reader = PolarsCSVReader(default_batch_size=rcfg.chunk_rows)
        try:
            reader.validate_file(source_path)
            reader.validate_file(target_path)
        except CSVFileNotFoundError as exc:
            raise ValidationBadRequestError(str(exc)) from exc
        except CSVValidationError as exc:
            raise ValidationBadRequestError(str(exc)) from exc

        self._preflight_csv_pair(source_path, target_path, delim, has_header=has_header)

        log_swap_pressure_warning(logger)

        combined_bytes = source_path.stat().st_size + target_path.stat().st_size
        use_multichar_streaming = not polars_supports_csv_delimiter(delim)
        uid_threshold = (uid_gte or "").strip() or None
        if uid_threshold is not None:
            use_multichar_streaming = False

        rcfg = self._apply_host_reconciliation_tuning(
            rcfg,
            source_path=source_path,
            target_path=target_path,
            resource_policy=queue_policy,
        )

        if use_multichar_streaming:
            try:
                src_head = multichar_csv_header_frame(
                    source_path, delimiter=delim, has_header=has_header
                )
                tgt_head = multichar_csv_header_frame(
                    target_path, delimiter=delim, has_header=has_header
                )
            except ReconciliationError as exc:
                raise ValidationBadRequestError(str(exc)) from exc

            src_cols = set(src_head.columns)
            tgt_cols = set(tgt_head.columns)
            if uid not in src_cols:
                raise ValidationBadRequestError(
                    f"uid_column {uid!r} not found in source file columns: {sorted(src_cols)}"
                )
            if uid not in tgt_cols:
                raise ValidationBadRequestError(
                    f"uid_column {uid!r} not found in target file columns: {sorted(tgt_cols)}"
                )
            compared_columns = sorted((src_cols & tgt_cols) - {uid})
            compared = len(compared_columns)

            logger.info(
                "Running chunked multichar hash-partition validation (combined_bytes=%d buckets=%d) "
                "source=%s target=%s uid_column=%r delimiter=%r",
                combined_bytes,
                rcfg.partition_buckets,
                source_path.name,
                target_path.name,
                uid,
                delim,
            )
            coordinator = ReconciliationCoordinator(reader=reader)
            try:
                report, src_rows, tgt_rows, _resolved = coordinator.run_multichar_hash_partition_csv_pair(
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid,
                    delimiter=delim,
                    compare_columns=compared_columns,
                    cfg=rcfg,
                )
            except UIDComparisonError as exc:
                logger.warning("UID comparison rejected multichar partitioned input: %s", exc)
                raise ValidationUnprocessableError(str(exc)) from exc
            except ReconciliationError as exc:
                logger.warning("Multichar streaming validation failed: %s", exc)
                if not csv_has_data_rows(source_path) and not csv_has_data_rows(target_path):
                    raise ValidationBadRequestError(
                        "Both source and target files are empty (no data rows)."
                    ) from exc
                raise ValidationBadRequestError(str(exc)) from exc

            n_mismatch = report.mismatches.height if report.mismatch_artifact_path is None else sum(
                report.summary.values()
            )
            logger.info(
                "Validation finished (multichar streaming) source_rows=%d target_rows=%d mismatch_report_rows=%d",
                src_rows,
                tgt_rows,
                n_mismatch,
            )
            return self._attach_mapping_analysis(
                ValidationRunResult(
                    report=report,
                    source_row_count=src_rows,
                    target_row_count=tgt_rows,
                    compared_column_count=compared,
                    compared_columns=compared_columns,
                    mismatch_artifact_path=report.mismatch_artifact_path,
                ),
                mapping_analysis,
            )

        want_external = (
            uid_threshold is None
            and not column_mappings
            and polars_supports_csv_delimiter(delim)
            and (
            self._settings.validation_force_external_reconciliation
            or rcfg.strategy != ReconciliationStrategy.AUTO
            or auto_external_enabled(source_path=source_path, target_path=target_path, cfg=rcfg)
            )
        )

        if want_external:
            try:
                schema_s = reader.detect_schema(
                    source_path, delimiter=delim, encoding="utf-8", has_header=has_header
                )
                schema_t = reader.detect_schema(
                    target_path, delimiter=delim, encoding="utf-8", has_header=has_header
                )
            except CSVParseError as exc:
                logger.warning("CSV schema probe failed during validation: %s", exc)
                raise ValidationBadRequestError(f"Could not parse CSV: {exc}") from exc

            src_cols = set(schema_s.keys())
            tgt_cols = set(schema_t.keys())
            if uid not in src_cols:
                raise ValidationBadRequestError(
                    f"uid_column {uid!r} not found in source file columns: {sorted(src_cols)}"
                )
            if uid not in tgt_cols:
                raise ValidationBadRequestError(
                    f"uid_column {uid!r} not found in target file columns: {sorted(tgt_cols)}"
                )
            compared_columns = sorted((src_cols & tgt_cols) - {uid})
            compared = len(compared_columns)

            logger.info(
                "Running external-memory reconciliation source=%s target=%s uid_column=%r delimiter=%r strategy=%s",
                source_path.name,
                target_path.name,
                uid,
                delim,
                rcfg.strategy.value,
            )
            coordinator = ReconciliationCoordinator(reader=reader)
            try:
                report, src_rows, tgt_rows, _resolved = coordinator.run_csv_pair(
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid,
                    delimiter=delim,
                    compare_columns=compared_columns,
                    cfg=rcfg,
                    progress_callback=progress_callback,
                )
            except ReconciliationStrategyError as exc:
                if (
                    not self._settings.validation_force_external_reconciliation
                    and rcfg.strategy == ReconciliationStrategy.AUTO
                    and "below external_memory_threshold_bytes" in str(exc)
                ):
                    logger.info("Falling back to in-memory validation: %s", exc)
                    want_external = False
                else:
                    raise ValidationBadRequestError(str(exc)) from exc
            except UIDComparisonError as exc:
                logger.warning("UID comparison rejected partitioned input: %s", exc)
                raise ValidationUnprocessableError(str(exc)) from exc
            except ReconciliationError as exc:
                logger.warning("External reconciliation failed: %s", exc)
                raise ValidationBadRequestError(str(exc)) from exc
            else:
                n_mismatch = report.mismatches.height if report.mismatch_artifact_path is None else sum(
                    report.summary.values()
                )
                logger.info(
                    "Validation finished (external) source_rows=%d target_rows=%d mismatch_report_rows=%d",
                    src_rows,
                    tgt_rows,
                    n_mismatch,
                )
                return self._attach_mapping_analysis(
                    ValidationRunResult(
                        report=report,
                        source_row_count=src_rows,
                        target_row_count=tgt_rows,
                        compared_column_count=compared,
                        compared_columns=compared_columns,
                        mismatch_artifact_path=report.mismatch_artifact_path,
                    ),
                    mapping_analysis,
                )

        logger.info(
            "Loading CSV pair for validation source=%s target=%s uid_column=%r delimiter=%r",
            source_path.name,
            target_path.name,
            uid,
            delim,
        )
        try:
            source_df = self._read_dataframe(reader, source_path, delim, has_header=has_header)
            target_df = self._read_dataframe(reader, target_path, delim, has_header=has_header)
        except CSVParseError as exc:
            logger.warning("CSV parse failed during validation: %s", exc)
            raise ValidationBadRequestError(f"Could not parse CSV: {exc}") from exc

        if uid_threshold is not None:
            source_df = self._apply_uid_gte_filter(source_df, uid, uid_threshold)
            target_df = self._apply_uid_gte_filter(target_df, uid, uid_threshold)

        if uid not in source_df.columns:
            raise ValidationBadRequestError(
                f"uid_column {uid!r} not found in source file columns: {list(source_df.columns)}"
            )
        if uid not in target_df.columns:
            raise ValidationBadRequestError(
                f"uid_column {uid!r} not found in target file columns: {list(target_df.columns)}"
            )

        target_rename_map = self._resolve_target_rename_map(
            source_columns=list(source_df.columns),
            target_columns=list(target_df.columns),
            uid_column=uid,
            column_mappings=column_mappings or [],
        )
        if target_rename_map:
            target_df = target_df.rename(target_rename_map)

        # Synthesize 1-to-many mapped composite columns (e.g. Full Name from First/Last/Middle Name)
        from collections import defaultdict
        source_to_targets = defaultdict(list)
        for mapping in (column_mappings or []):
            src = mapping.source_column.strip()
            if not src:
                continue
            tgts_list = []
            if hasattr(mapping, "target_columns") and mapping.target_columns:
                tgts_list = [t.strip() for t in mapping.target_columns if t.strip()]
            if not tgts_list and mapping.target_column.strip():
                tgts_list = [mapping.target_column.strip()]
            for t in tgts_list:
                if t not in source_to_targets[src]:
                    source_to_targets[src].append(t)

        composite_mappings = {src: tgts for src, tgts in source_to_targets.items() if len(tgts) > 1}
        if composite_mappings:
            target_col_order = {col: i for i, col in enumerate(target_df.columns)}
            
            def get_target_name_rank(col_name: str) -> int:
                name_lower = col_name.lower()
                if any(k in name_lower for k in ("first", "fname", "f_name", "given")):
                    return 1
                if any(k in name_lower for k in ("middle", "mname", "m_name")):
                    return 2
                if any(k in name_lower for k in ("last", "lname", "l_name", "sur", "family")):
                    return 3
                return 4

            for src_col, tgt_cols in composite_mappings.items():
                # Sort target columns by name rank, then by original file layout position
                sorted_tgts = sorted(
                    tgt_cols,
                    key=lambda col: (get_target_name_rank(col), target_col_order.get(col, 999))
                )
                exprs = [pl.col(col).cast(pl.String).fill_null("") for col in sorted_tgts]
                concat_expr = (
                    pl.concat_str(exprs, separator=" ")
                    .str.replace_all(r"\s+", " ", literal=False)
                    .str.strip_chars()
                )
                target_df = target_df.with_columns(concat_expr.alias(src_col))

        src_cols = set(source_df.columns)
        tgt_cols = set(target_df.columns)
        shared = src_cols & tgt_cols
        compared_columns = sorted(shared - {uid})
        compared = len(compared_columns)
        compare_rules = build_rules_by_source_column(column_mappings)

        comparator = UIDBasedComparator(stringify_null_in_report=True)
        try:
            report = comparator.compare_dataframes(
                source_df,
                target_df,
                uid_column=uid,
                compare_columns=None,
                compare_rules=compare_rules,
            )
        except UIDComparisonError as exc:
            logger.warning("UID comparison rejected input: %s", exc)
            raise ValidationUnprocessableError(str(exc)) from exc

        logger.info(
            "Validation finished source_rows=%d target_rows=%d mismatch_report_rows=%d",
            source_df.height,
            target_df.height,
            report.mismatches.height,
        )
        return self._attach_mapping_analysis(
            ValidationRunResult(
                report=report,
                source_row_count=source_df.height,
                target_row_count=target_df.height,
                compared_column_count=compared,
                compared_columns=compared_columns,
                mismatch_artifact_path=report.mismatch_artifact_path,
                test_mode="full",
            ),
            mapping_analysis,
        )

    @staticmethod
    def _apply_uid_gte_filter(df: pl.DataFrame, uid_column: str, threshold: str) -> pl.DataFrame:
        expr = pl.col(uid_column).cast(pl.Utf8).str.strip_chars()
        try:
            numeric_threshold = float(threshold)
        except ValueError:
            return df.filter(expr >= threshold)
        numeric_expr = expr.cast(pl.Float64, strict=False)
        return df.filter(numeric_expr >= numeric_threshold)

    @staticmethod
    def _attach_mapping_analysis(
        result: ValidationRunResult,
        mapping_analysis: dict[str, Any] | None,
    ) -> ValidationRunResult:
        if not mapping_analysis:
            return result
        return replace(
            result,
            mapping_format_checks=list(mapping_analysis.get("format_checks") or []) or None,
            footer_validation=mapping_analysis.get("footer_validation"),
        )

    @staticmethod
    def _prepare_csv_pair_for_comparison(
        *,
        source_path: Path,
        target_path: Path,
        header_leading_rows: int,
        footer_trailing_rows: int,
    ) -> tuple[Path, Path, list[Path]]:
        header_rows = max(0, int(header_leading_rows or 0))
        footer_rows = max(0, int(footer_trailing_rows or 0))
        if header_rows == 0 and footer_rows == 0:
            return source_path, target_path, []
        prepared_source, src_tmp = ValidationService._slice_csv_rows(
            source_path,
            header_rows=header_rows,
            footer_rows=footer_rows,
        )
        prepared_target, tgt_tmp = ValidationService._slice_csv_rows(
            target_path,
            header_rows=header_rows,
            footer_rows=footer_rows,
        )
        return prepared_source, prepared_target, [src_tmp, tgt_tmp]

    @staticmethod
    def _slice_csv_rows(
        path: Path,
        *,
        header_rows: int,
        footer_rows: int,
    ) -> tuple[Path, Path]:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = min(header_rows, len(lines))
        end = len(lines) - min(footer_rows, max(0, len(lines) - start))
        kept = lines[start:end]
        fd, tmp_path = tempfile.mkstemp(prefix="pegasus_csv_slice_", suffix=".csv")
        Path(tmp_path).write_text("\n".join(kept), encoding="utf-8")
        return Path(tmp_path), Path(tmp_path)

    def _read_column_names(self, path: Path, delimiter: str, *, has_header: bool = True) -> list[str]:
        if not polars_supports_csv_delimiter(delimiter):
            frame = multichar_csv_header_frame(path, delimiter=delimiter, has_header=has_header)
            return [c.strip() for c in frame.columns]
        reader = PolarsCSVReader(default_batch_size=512)
        schema = reader.detect_schema(
            path,
            delimiter=delimiter,
            encoding="utf-8",
            has_header=has_header,
        )
        return list(schema.keys())

    def _auto_map_columns(self, source_columns: list[str], target_columns: list[str]) -> list[dict[str, str]]:
        target_by_norm = {self._normalize_column_name(c): c for c in target_columns}
        auto: list[dict[str, str]] = []
        seen_targets: set[str] = set()
        for source in source_columns:
            target = target_by_norm.get(self._normalize_column_name(source))
            if target is None or target in seen_targets:
                continue
            auto.append({"source_column": source, "target_column": target})
            seen_targets.add(target)
        return auto

    def _resolve_target_rename_map(
        self,
        *,
        source_columns: list[str],
        target_columns: list[str],
        uid_column: str,
        column_mappings: list[ColumnMapping],
    ) -> dict[str, str]:
        source_set = set(source_columns)
        target_set = set(target_columns)
        rename_map: dict[str, str] = {}
        
        # Build normalized source-to-targets mapping
        from collections import defaultdict
        source_to_targets = defaultdict(list)
        for mapping in column_mappings:
            source = mapping.source_column.strip()
            if not source:
                continue
            tgts_list = []
            if hasattr(mapping, "target_columns") and mapping.target_columns:
                tgts_list = [t.strip() for t in mapping.target_columns if t.strip()]
            if not tgts_list and mapping.target_column.strip():
                tgts_list = [mapping.target_column.strip()]
            for t in tgts_list:
                if t not in source_to_targets[source]:
                    source_to_targets[source].append(t)
                    
        used_targets: set[str] = set()

        # Validate normalized mappings
        for source, tgts in source_to_targets.items():
            if source == uid_column:
                raise ValidationBadRequestError("column_mappings cannot include the uid_column")
            if source not in source_set:
                raise ValidationBadRequestError(f"source column {source!r} not found in source file columns")
                
            for target in tgts:
                if target == uid_column:
                    raise ValidationBadRequestError("column_mappings cannot include the uid_column")
                if target not in target_set:
                    raise ValidationBadRequestError(f"target column {target!r} not found in target file columns")
                if target in used_targets:
                    raise ValidationBadRequestError(f"target column {target!r} is mapped more than once")
                used_targets.add(target)
                
            # Standard 1-to-1 mappings are added to rename_map
            if len(tgts) == 1:
                rename_map[tgts[0]] = source

        if not rename_map:
            return {}

        renamed_target_columns = [rename_map.get(column, column) for column in target_columns]
        if len(set(renamed_target_columns)) != len(renamed_target_columns):
            raise ValidationBadRequestError("column_mappings would create duplicate target column names")
        return rename_map

    @staticmethod
    def _normalize_column_name(name: str) -> str:
        return re.sub(r"\s+", "", name.strip().casefold())

    @staticmethod
    def _raise_if_csv_pair_has_no_data(source_path: Path, target_path: Path) -> None:
        """Reject validation when both CSVs lack data rows (empty or header-only)."""
        src_has_data = csv_has_data_rows(source_path)
        tgt_has_data = csv_has_data_rows(target_path)
        if not src_has_data and not tgt_has_data:
            raise ValidationBadRequestError(
                "Both source and target files are empty (no data rows)."
            )

    @staticmethod
    def _preflight_csv_pair(
        source_path: Path,
        target_path: Path,
        delimiter: str,
        *,
        has_header: bool = True,
    ) -> None:
        for path, tag in ((source_path, "source"), (target_path, "target")):
            try:
                preflight_csv_structure(path, delimiter, label=tag, has_header=has_header)
            except CsvPreflightError as exc:
                raise ValidationBadRequestError(str(exc)) from exc

    def _resolve_delimiter(
        self,
        *,
        source_path: Path,
        target_path: Path,
        delimiter: str | None,
    ) -> str:
        token = (delimiter or "").strip()
        lowered = token.lower()
        if lowered in {"", "auto", "infer", "detect"}:
            try:
                shared = resolve_shared_auto_delimiter(source_path, target_path)
                return shared.delimiter
            except ValueError as exc:
                raise ValidationBadRequestError(str(exc)) from exc

        if token in {"\\t", "\\\\t"} or lowered == "tab":
            return "\t"

        if len(token) != 1:
            # explicit multi-char delimiter: supported through pandas fallback
            return token
        return token

    def _read_dataframe(
        self,
        reader: PolarsCSVReader,
        path: Path,
        delimiter: str,
        *,
        has_header: bool = True,
    ) -> pl.DataFrame:
        if polars_supports_csv_delimiter(delimiter):
            return reader.read_file(
                path,
                delimiter=delimiter,
                encoding="utf-8",
                use_streaming_engine=True,
                has_header=has_header,
            )

        # Polars only accepts single-byte separators; use pandas for multi-char / emoji / etc.
        logger.info("Using pandas fallback for delimiter %r on %s", delimiter, path.name)
        try:
            pdf = pd.read_csv(
                path,
                sep=re.escape(delimiter),
                engine="python",
                encoding="utf-8",
                header=0 if has_header else None,
                quotechar='"',
                doublequote=True,
            )
        except Exception as exc:
            raise CSVParseError(f"Failed pandas fallback parse for {path.name}: {exc}") from exc

        if not has_header:
            pdf.columns = [f"column_{index}" for index in range(1, len(pdf.columns) + 1)]

        df = pl.from_pandas(pdf, include_index=False)
        rename_map = {col: col.strip() for col in df.columns if col != col.strip()}
        if rename_map:
            df = df.rename(rename_map)
        return df

    def validate_fixed_width_pair_sync(
        self,
        source_path: Path,
        target_path: Path,
        fixed_width_config: dict[str, Any],
        artifact_export_parent: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> ValidationRunResult:
        """Stream two fixed-width files and validate dates line-by-line in lockstep."""
        from collections import defaultdict, deque
        import json

        from pegasus.validation.fixed_width_meta import materialize_fixed_width_fields

        fixed_width_config = materialize_fixed_width_fields(dict(fixed_width_config))
        source_path = Path(source_path).resolve()
        target_path = Path(target_path).resolve()

        if not source_path.is_file():
            raise ValidationBadRequestError(f"Source file not found: {source_path}")
        if not target_path.is_file():
            raise ValidationBadRequestError(f"Target file not found: {target_path}")

        # Retrieve fields list if multi-field validation is used
        fields = fixed_width_config.get("fields", [])
        has_fields = len(fields) > 0

        if not has_fields:
            src_start_check = int(fixed_width_config.get("source_date_start", 0))
            src_end_check = int(fixed_width_config.get("source_date_end", 0))
            tgt_start_check = int(fixed_width_config.get("target_date_start", 0))
            tgt_end_check = int(fixed_width_config.get("target_date_end", 0))
            if src_end_check <= src_start_check or tgt_end_check <= tgt_start_check:
                raise ValidationBadRequestError(
                    "fixed_width_config must define non-empty date slice positions "
                    "(source_date_end > source_date_start and target_date_end > target_date_start)"
                )
            if not str(fixed_width_config.get("source_date_format") or "").strip():
                raise ValidationBadRequestError("fixed_width_config.source_date_format is required")
            if not str(fixed_width_config.get("target_date_format") or "").strip():
                raise ValidationBadRequestError("fixed_width_config.target_date_format is required")

        # Slicing parameters for single-date fallback mode
        src_start = int(fixed_width_config.get("source_date_start", 0)) if not has_fields else 0
        src_end = int(fixed_width_config.get("source_date_end", 0)) if not has_fields else 0
        src_format = (
            normalize_strptime_format(str(fixed_width_config.get("source_date_format", "")))
            if not has_fields
            else ""
        )
        tgt_start = int(fixed_width_config.get("target_date_start", 0)) if not has_fields else 0
        tgt_end = int(fixed_width_config.get("target_date_end", 0)) if not has_fields else 0
        tgt_format = (
            normalize_strptime_format(str(fixed_width_config.get("target_date_format", "")))
            if not has_fields
            else ""
        )

        uid_col = str(fixed_width_config.get("uid_column") or "").strip()
        if not uid_col:
            raise ValidationBadRequestError(
                "fixed_width_config.uid_column is required — choose which column to match rows by (e.g. id, name, email)"
            )
        if not has_fields:
            raise ValidationBadRequestError(
                "fixed_width_config.fields is required — list every column slice to compare"
            )

        join_field = next((f for f in fields if str(f.get("field_name")) == uid_col), None)
        if join_field is not None:
            uid_src_start = int(join_field["source_start"])
            uid_src_end = int(join_field["source_end"])
            uid_tgt_start = int(join_field["target_start"])
            uid_tgt_end = int(join_field["target_end"])
        else:
            uid_src_start = int(fixed_width_config.get("uid_source_start", -1))
            uid_src_end = int(fixed_width_config.get("uid_source_end", -1))
            uid_tgt_start = int(fixed_width_config.get("uid_target_start", -1))
            uid_tgt_end = int(fixed_width_config.get("uid_target_end", -1))
            if uid_src_end <= uid_src_start or uid_tgt_end <= uid_tgt_start:
                raise ValidationBadRequestError(
                    f"Join column '{uid_col}' was not found in fixed_width_config.fields "
                    "and uid slice positions were not provided"
                )
        if uid_src_end <= uid_src_start or uid_tgt_end <= uid_tgt_start:
            raise ValidationBadRequestError(
                f"Join column '{uid_col}' must have non-empty source and target slice positions"
            )

        match_strategy = str(fixed_width_config.get("match_strategy") or "exact").strip().lower()
        fuzzy_threshold = float(fixed_width_config.get("fuzzy_similarity_threshold") or 0.75)
        use_fuzzy = match_strategy == "fuzzy"
        use_uid_alignment = True

        artifact_path = None
        if artifact_export_parent is not None:
            artifact_export_parent.mkdir(parents=True, exist_ok=True)
            artifact_path = artifact_export_parent / "mismatches.ndjson"

        total_rows = 0
        source_row_count = 0
        target_row_count = 0
        mismatches = 0
        missing_in_target = 0
        missing_in_source = 0
        value_mismatch = 0

        buffer_size = 16 * 1024 * 1024
        
        # If we have an artifact export path, open it for streaming NDJSON
        log_fp = None
        if artifact_path is not None:
            log_fp = open(artifact_path, "w", encoding="utf-8")

        def _row_detail_json(payload: dict[str, Any]) -> str:
            return json.dumps(payload, default=str)

        from pegasus.validation.structured_compare import structured_strings_equal
        from pegasus.validation.value_compare import values_equal_for_validation

        def safe_cast(value_str: str, f_type: str, d_format: str | None) -> tuple[Any, str | None]:
            v = value_str.strip()
            if not v:
                return None, None
            try:
                if f_type == "integer":
                    return int(v), None
                elif f_type == "float":
                    return float(v), None
                elif f_type == "date":
                    fmt = normalize_strptime_format(d_format or "%Y-%m-%d")
                    return parse_fixed_width_date(v, fmt), None
                elif f_type == "structured":
                    return v, None
                else:  # text
                    return v, None
            except Exception as e:
                return None, str(e)

        def _fixed_width_values_match(
            *,
            src_raw: str,
            tgt_raw: str,
            f_type: str,
            src_val: Any,
            tgt_val: Any,
            order_sensitive: bool,
        ) -> bool:
            if f_type == "structured":
                return structured_strings_equal(
                    src_raw,
                    tgt_raw,
                    order_sensitive=order_sensitive,
                )
            if f_type == "text":
                return values_equal_for_validation(src_raw.strip(), tgt_raw.strip())
            return src_val == tgt_val

        def _uid_from_line(line: str, start: int | None, end: int | None, fallback: str) -> str:
            if start is None or end is None:
                return fallback
            return line[int(start):int(end)].strip() or fallback

        def _emit_value_mismatch(
            *,
            row_uid: str,
            column_name: str,
            source_value: str | None,
            target_value: str | None,
            row_detail: dict[str, Any],
        ) -> None:
            nonlocal mismatches, value_mismatch
            mismatches += 1
            value_mismatch += 1
            if log_fp is not None:
                log_fp.write(json.dumps({
                    "uid": row_uid,
                    "mismatch_type": "value_mismatch",
                    "column_name": column_name,
                    "source_value": source_value,
                    "target_value": target_value,
                    "row_detail": _row_detail_json(row_detail),
                }) + "\n")

        def _compare_mapped_fields(
            *,
            src_line: str,
            tgt_line: str,
            row_uid: str,
            display_line_idx: int,
            pairing_note: str | None = None,
        ) -> None:
            nonlocal mismatches, value_mismatch
            for field in fields:
                f_name = field["field_name"]
                f_type = field.get("field_type", "text")
                shared_fmt = field.get("date_format")
                src_fmt = field.get("source_date_format") or shared_fmt
                tgt_fmt = field.get("target_date_format") or shared_fmt

                src_s = int(field["source_start"])
                src_e = int(field["source_end"])
                tgt_s = int(field["target_start"])
                tgt_e = int(field["target_end"])

                src_raw = src_line[src_s:src_e]
                tgt_raw = tgt_line[tgt_s:tgt_e]

                src_val, src_err = safe_cast(src_raw, f_type, src_fmt)
                tgt_val, tgt_err = safe_cast(tgt_raw, f_type, tgt_fmt)

                has_mismatch = False
                err_msg = None
                if src_err or tgt_err:
                    has_mismatch = True
                    err_msg = f"Parsing error: Source({src_err}) Target({tgt_err})"
                elif not _fixed_width_values_match(
                    src_raw=src_raw,
                    tgt_raw=tgt_raw,
                    f_type=f_type,
                    src_val=src_val,
                    tgt_val=tgt_val,
                    order_sensitive=bool(field.get("structured_order_sensitive", False)),
                ):
                    has_mismatch = True

                if has_mismatch:
                    detail: dict[str, Any] = {
                        "error": err_msg or "Value mismatch",
                        "line_index": display_line_idx,
                        "source_record": {f_name: src_raw.strip()},
                        "target_record": {f_name: tgt_raw.strip()},
                    }
                    if pairing_note:
                        detail["pairing"] = pairing_note
                    _emit_value_mismatch(
                        row_uid=row_uid,
                        column_name=f_name,
                        source_value=src_raw.strip(),
                        target_value=tgt_raw.strip(),
                        row_detail=detail,
                    )

        def _compare_aligned_pair(
            *,
            src_line: str,
            tgt_line: str,
            row_uid: str,
            display_line_idx: int,
            pairing_note: str | None = None,
        ) -> None:
            _compare_mapped_fields(
                src_line=src_line,
                tgt_line=tgt_line,
                row_uid=row_uid,
                display_line_idx=display_line_idx,
                pairing_note=pairing_note,
            )

        try:
            target_by_uid: dict[str, deque[tuple[int, str]]] = defaultdict(deque)
            unmatched_src: list[tuple[int, str, str]] = []

            with open(target_path, "r", encoding="utf-8", buffering=buffer_size) as tgt_file:
                for target_idx, tgt_line in enumerate(tgt_file, start=1):
                    if not tgt_line.strip():
                        continue
                    target_row_count += 1
                    uid = _uid_from_line(
                        tgt_line,
                        uid_tgt_start,
                        uid_tgt_end,
                        f"Line {target_idx}",
                    )
                    target_by_uid[uid].append((target_idx, tgt_line))

            with open(source_path, "r", encoding="utf-8", buffering=buffer_size) as src_file:
                for source_idx, src_line in enumerate(src_file, start=1):
                    if not src_line.strip():
                        continue
                    source_row_count += 1
                    total_rows += 1

                    if progress_callback is not None and source_row_count % 1_000_000 == 0:
                        progress_callback({
                            "phase": "validating",
                            "message": f"Processed {source_row_count:,} rows",
                            "percent": None,
                        })

                    row_uid = _uid_from_line(
                        src_line,
                        uid_src_start,
                        uid_src_end,
                        f"Line {source_idx}",
                    )
                    bucket = target_by_uid.get(row_uid)
                    if not bucket:
                        unmatched_src.append((source_idx, src_line, row_uid))
                        continue

                    _, tgt_line = bucket.popleft()
                    if not bucket:
                        del target_by_uid[row_uid]

                    _compare_aligned_pair(
                        src_line=src_line,
                        tgt_line=tgt_line,
                        row_uid=row_uid,
                        display_line_idx=source_idx,
                    )

            unmatched_tgt: list[tuple[int, str, str]] = []
            for leftover_uid, leftover_lines in target_by_uid.items():
                while leftover_lines:
                    target_idx, tgt_line = leftover_lines.popleft()
                    unmatched_tgt.append((target_idx, tgt_line, leftover_uid))

            if use_fuzzy and unmatched_src and unmatched_tgt:
                pairs, unmatched_src, unmatched_tgt = fuzzy_pair_by_join_key(
                    unmatched_src,
                    unmatched_tgt,
                    threshold=fuzzy_threshold,
                )
                for (src_idx, src_line, src_key), (tgt_idx, tgt_line, tgt_key), score in pairs:
                    pairing_note = (
                        f"Fuzzy matched on '{uid_col}' (similarity {score:.2f}): "
                        f"source {src_key!r} vs target {tgt_key!r}"
                    )
                    _compare_aligned_pair(
                        src_line=src_line,
                        tgt_line=tgt_line,
                        row_uid=src_key,
                        display_line_idx=src_idx,
                        pairing_note=pairing_note,
                    )

            for _src_idx, src_line, row_uid in unmatched_src:
                mismatches += 1
                missing_in_target += 1
                if log_fp is not None:
                    log_fp.write(json.dumps({
                        "uid": row_uid,
                        "mismatch_type": "missing_in_target",
                        "column_name": uid_col,
                        "source_value": src_line.rstrip()[:100],
                        "target_value": None,
                        "row_detail": _row_detail_json({
                            "error": f"No target row with matching {uid_col}",
                            "source_line": src_line.rstrip()[:200],
                        }),
                    }) + "\n")

            for target_idx, tgt_line, row_uid in unmatched_tgt:
                mismatches += 1
                missing_in_source += 1
                if log_fp is not None:
                    log_fp.write(json.dumps({
                        "uid": row_uid,
                        "mismatch_type": "extra_in_target",
                        "column_name": uid_col,
                        "source_value": None,
                        "target_value": tgt_line.rstrip()[:100],
                        "row_detail": _row_detail_json({
                            "error": f"No source row with matching {uid_col}",
                            "target_line": tgt_line.rstrip()[:200],
                            "target_line_index": target_idx,
                        }),
                    }) + "\n")
        finally:
            if log_fp is not None:
                log_fp.close()

        # Build a compatible MismatchReport
        summary = {
            "missing_in_target": missing_in_target,
            "extra_in_target": missing_in_source,
            "value_mismatch": value_mismatch,
        }
        report = MismatchReport(
            mismatches=pl.DataFrame(),
            summary=summary,
            mismatch_artifact_path=artifact_path,
        )

        compared_columns = [f["field_name"] for f in fields]

        return ValidationRunResult(
            report=report,
            source_row_count=source_row_count,
            target_row_count=target_row_count,
            compared_column_count=len(compared_columns),
            compared_columns=compared_columns,
            mismatch_artifact_path=artifact_path,
        )

    def validate_json_pair_sync(
        self,
        source_path: Path,
        target_path: Path,
        *,
        artifact_export_parent: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> ValidationRunResult:
        """Compare two JSON files with order-insensitive canonical equality."""
        import json as _json

        from pegasus.validation.json_compare import (
            collect_json_mismatches,
            compare_json_documents,
            load_json_file,
        )

        source_path = Path(source_path).resolve()
        target_path = Path(target_path).resolve()
        if not source_path.is_file():
            raise ValidationBadRequestError(f"Source file not found: {source_path}")
        if not target_path.is_file():
            raise ValidationBadRequestError(f"Target file not found: {target_path}")

        if progress_callback is not None:
            progress_callback({
                "phase": "validating",
                "message": "Loading and comparing JSON documents",
                "percent": 10,
            })

        source_doc = load_json_file(source_path)
        target_doc = load_json_file(target_path)
        is_match, _src_canon, _tgt_canon = compare_json_documents(source_doc, target_doc)
        summary, mismatch_rows = collect_json_mismatches(source_doc, target_doc)

        artifact_path: Path | None = None
        if mismatch_rows and artifact_export_parent is not None:
            artifact_export_parent.mkdir(parents=True, exist_ok=True)
            artifact_path = artifact_export_parent / "mismatches.ndjson"
            with artifact_path.open("w", encoding="utf-8") as handle:
                for row in mismatch_rows:
                    handle.write(_json.dumps(row) + "\n")
        report = MismatchReport(
            mismatches=empty_mismatch_frame(),
            summary=summary,
            mismatch_artifact_path=artifact_path,
        )

        if progress_callback is not None:
            progress_callback({
                "phase": "validating",
                "message": "JSON comparison complete",
                "percent": 100,
            })

        return ValidationRunResult(
            report=report,
            source_row_count=1,
            target_row_count=1,
            compared_column_count=1,
            compared_columns=["json"],
            mismatch_artifact_path=artifact_path,
        )

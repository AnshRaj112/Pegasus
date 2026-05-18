"""Orchestrates CSV load and UID-based comparison (blocking Polars in a thread pool)."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
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
from pegasus.services.exceptions import (
    ValidationBadRequestError,
    ValidationUnprocessableError,
)
from pegasus.validation.comparators.exceptions import UIDComparisonError
from pegasus.validation.comparators.models import MismatchReport
from pegasus.validation.comparators.uid_based import UIDBasedComparator
from pegasus.validation.readers.exceptions import (
    CSVFileNotFoundError,
    CSVParseError,
    CSVValidationError,
)
from pegasus.validation.readers.delimiter_detection import resolve_shared_auto_delimiter
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
from pegasus.validation.reconciliation.partition_manager import multichar_csv_header_frame

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationRunResult:
    """Outcome of a single validation run."""

    report: MismatchReport
    source_row_count: int
    target_row_count: int
    compared_column_count: int
    compared_columns: list[str]
    mismatch_artifact_path: Path | None = None


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
    ) -> ReconciliationRuntimeConfig:
        """Clamp partition counts using host CPU and RAM hints."""
        ncpu = physical_cpu_count()
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
        )

    def preview_local_column_headers(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
    ) -> dict[str, Any]:
        """Return source/target headers and exact-name mapping suggestions for the UI."""
        uid = uid_column.strip()
        delim = self._resolve_delimiter(
            source_path=source_path,
            target_path=target_path,
            delimiter=delimiter,
        )
        source_columns = self._read_column_names(source_path, delim)
        target_columns = self._read_column_names(target_path, delim)
        compare_columns = [c for c in source_columns if c != uid]
        compare_targets = [c for c in target_columns if c != uid]
        auto_mappings = self._auto_map_columns(compare_columns, compare_targets)
        matched_sources = {m["source_column"] for m in auto_mappings}
        matched_targets = {m["target_column"] for m in auto_mappings}
        return {
            "source_columns": source_columns,
            "target_columns": target_columns,
            "compare_columns": compare_columns,
            "auto_mappings": auto_mappings,
            "unmatched_source_columns": [c for c in source_columns if c not in matched_sources],
            "unmatched_target_columns": [c for c in target_columns if c not in matched_targets],
            "delimiter": delim,
        }

    def _validate_csv_pair_sync(
        self,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        column_mappings: list[ColumnMapping] | None = None,
        artifact_export_parent: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> ValidationRunResult:
        uid = uid_column.strip()
        if not uid:
            raise ValidationBadRequestError("uid_column must be a non-empty string")

        rcfg = self._reconciliation_runtime_config(artifact_export_parent=artifact_export_parent)
        delim = self._resolve_delimiter(
            source_path=source_path,
            target_path=target_path,
            delimiter=delimiter,
        )

        reader = PolarsCSVReader(default_batch_size=rcfg.chunk_rows)
        try:
            reader.validate_file(source_path)
            reader.validate_file(target_path)
        except CSVFileNotFoundError as exc:
            raise ValidationBadRequestError(str(exc)) from exc
        except CSVValidationError as exc:
            raise ValidationBadRequestError(str(exc)) from exc

        log_swap_pressure_warning(logger)

        combined_bytes = source_path.stat().st_size + target_path.stat().st_size
        use_multichar_streaming = len(delim) > 1

        rcfg = self._apply_host_reconciliation_tuning(rcfg, source_path=source_path, target_path=target_path)

        if use_multichar_streaming:
            try:
                src_head = multichar_csv_header_frame(source_path, delimiter=delim)
                tgt_head = multichar_csv_header_frame(target_path, delimiter=delim)
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
            return ValidationRunResult(
                report=report,
                source_row_count=src_rows,
                target_row_count=tgt_rows,
                compared_column_count=compared,
                compared_columns=compared_columns,
                mismatch_artifact_path=report.mismatch_artifact_path,
            )

        want_external = not column_mappings and len(delim) == 1 and (
            self._settings.validation_force_external_reconciliation
            or rcfg.strategy != ReconciliationStrategy.AUTO
            or auto_external_enabled(source_path=source_path, target_path=target_path, cfg=rcfg)
        )

        if want_external:
            try:
                schema_s = reader.detect_schema(source_path, delimiter=delim, encoding="utf-8")
                schema_t = reader.detect_schema(target_path, delimiter=delim, encoding="utf-8")
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
                return ValidationRunResult(
                    report=report,
                    source_row_count=src_rows,
                    target_row_count=tgt_rows,
                    compared_column_count=compared,
                    compared_columns=compared_columns,
                    mismatch_artifact_path=report.mismatch_artifact_path,
                )

        logger.info(
            "Loading CSV pair for validation source=%s target=%s uid_column=%r delimiter=%r",
            source_path.name,
            target_path.name,
            uid,
            delim,
        )
        try:
            source_df = self._read_dataframe(reader, source_path, delim)
            target_df = self._read_dataframe(reader, target_path, delim)
        except CSVParseError as exc:
            logger.warning("CSV parse failed during validation: %s", exc)
            raise ValidationBadRequestError(f"Could not parse CSV: {exc}") from exc

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

        src_cols = set(source_df.columns)
        tgt_cols = set(target_df.columns)
        shared = src_cols & tgt_cols
        compared_columns = sorted(shared - {uid})
        compared = len(compared_columns)

        comparator = UIDBasedComparator(stringify_null_in_report=True)
        try:
            report = comparator.compare_dataframes(
                source_df,
                target_df,
                uid_column=uid,
                compare_columns=None,
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
        return ValidationRunResult(
            report=report,
            source_row_count=source_df.height,
            target_row_count=target_df.height,
            compared_column_count=compared,
            compared_columns=compared_columns,
            mismatch_artifact_path=report.mismatch_artifact_path,
        )

    def _read_column_names(self, path: Path, delimiter: str) -> list[str]:
        reader = PolarsCSVReader(default_batch_size=512)
        if len(delimiter) > 1:
            frame = multichar_csv_header_frame(path, delimiter=delimiter)
            return list(frame.columns)
        schema = reader.detect_schema(path, delimiter=delimiter, encoding="utf-8")
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
        used_sources: set[str] = set()
        used_targets: set[str] = set()

        for mapping in column_mappings:
            source = mapping.source_column.strip()
            target = mapping.target_column.strip()
            if not source or not target:
                continue
            if source == uid_column or target == uid_column:
                raise ValidationBadRequestError("column_mappings cannot include the uid_column")
            if source not in source_set:
                raise ValidationBadRequestError(f"source column {source!r} not found in source file columns")
            if target not in target_set:
                raise ValidationBadRequestError(f"target column {target!r} not found in target file columns")
            if source in used_sources:
                raise ValidationBadRequestError(f"source column {source!r} is mapped more than once")
            if target in used_targets:
                raise ValidationBadRequestError(f"target column {target!r} is mapped more than once")
            rename_map[target] = source
            used_sources.add(source)
            used_targets.add(target)

        if not rename_map:
            return {}

        renamed_target_columns = [rename_map.get(column, column) for column in target_columns]
        if len(set(renamed_target_columns)) != len(renamed_target_columns):
            raise ValidationBadRequestError("column_mappings would create duplicate target column names")
        return rename_map

    @staticmethod
    def _normalize_column_name(name: str) -> str:
        return re.sub(r"\s+", "", name.strip().casefold())

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

    def _read_dataframe(self, reader: PolarsCSVReader, path: Path, delimiter: str) -> pl.DataFrame:
        if len(delimiter) == 1:
            return reader.read_file(
                path,
                delimiter=delimiter,
                encoding="utf-8",
                use_streaming_engine=True,
            )

        # Multi-character delimiters are not supported by Polars CSV parser.
        # Use pandas python engine, then convert to Polars for downstream pipeline.
        logger.info("Using pandas fallback for multi-character delimiter %r on %s", delimiter, path.name)
        try:
            pdf = pd.read_csv(
                path,
                sep=re.escape(delimiter),
                engine="python",
                encoding="utf-8",
            )
        except Exception as exc:
            raise CSVParseError(f"Failed pandas fallback parse for {path.name}: {exc}") from exc

        return pl.from_pandas(pdf, include_index=False)

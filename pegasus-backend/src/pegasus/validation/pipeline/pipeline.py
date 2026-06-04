# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-03T15:30:26+05:30
# --- END GENERATED FILE METADATA ---

"""Six-stage tabular reconciliation pipeline."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from pegasus.validation.adapters.base import TabularSourceAdapter, TabularSchema
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.fingerprint import (
    filter_compare_columns,
    identity_key,
    identity_key_from_parts,
    partition_id,
    row_fingerprint_bytes,
    row_fingerprint_from_parts,
    _canonical_parts,
)
from pegasus.validation.pipeline.in_memory import (
    should_try_in_memory_reconcile,
    try_in_memory_reconcile,
)
from pegasus.validation.pipeline.precheck import (
    spill_partitions_identical,
    try_identical_precheck,
)
from pegasus.validation.pipeline.drilldown_cache import DrilldownCache
from pegasus.validation.pipeline.polars_spill import (
    can_use_polars_spill,
    partition_side_polars,
    try_partition_side_polars,
)
from pegasus.validation.pipeline.result import (
    ColumnDifference,
    MismatchSample,
    PipelineResult,
    SchemaDifference,
)
from pegasus.validation.pipeline.spill import (
    PartitionWriter,
    iter_partition,
    list_partition_ids,
)
from pegasus.validation.pipeline.timing import PipelineTimings, StageTimer


def _adapter_network_seconds(adapter: object) -> float:
    return float(getattr(adapter, "network_transfer_seconds", 0.0) or 0.0)


def _adapter_size_bytes(adapter: object) -> int:
    getter = getattr(adapter, "get_size_bytes", None)
    if callable(getter):
        return int(getter())
    return int(Path(getattr(adapter, "path")).stat().st_size)


def _adaptive_partition_count(
    *,
    source_bytes: int,
    target_bytes: int,
    requested: int,
) -> int:
    """Use fewer buckets for small files to avoid empty-partition overhead."""
    file_bytes = source_bytes + target_bytes
    if file_bytes <= 4 * 1024 * 1024:
        return min(requested, 16)
    if file_bytes <= 32 * 1024 * 1024:
        return min(requested, 64)
    if file_bytes <= 128 * 1024 * 1024:
        return min(requested, 256)
    return requested


def _compare_schemas(source: TabularSchema, target: TabularSchema) -> list[SchemaDifference]:
    diffs: list[SchemaDifference] = []
    src = {c.name: c for c in source.columns}
    tgt = {c.name: c for c in target.columns}
    for name in src:
        if name not in tgt:
            diffs.append(SchemaDifference(name, "missing_in_target", source_value=name))
        elif src[name].data_type != tgt[name].data_type:
            diffs.append(SchemaDifference(
                name, "type_mismatch", src[name].data_type, tgt[name].data_type
            ))
    for name in tgt:
        if name not in src:
            diffs.append(SchemaDifference(name, "extra_in_target", target_value=name))
    return diffs


def _fp_equal(a: bytes, b: bytes) -> bool:
    return a == b


class TabularReconciliationPipeline:
    """Streaming partition-based reconciliation (Stages 1–6)."""

    __slots__ = ("_source", "_target", "_identity_columns", "_compare_columns", "_config")

    def __init__(
        self,
        source: TabularSourceAdapter,
        target: TabularSourceAdapter,
        *,
        identity_columns: list[str],
        compare_columns: list[str],
        config: TabularPipelineConfig,
    ) -> None:
        self._source = source
        self._target = target
        self._identity_columns = identity_columns
        self._compare_columns = compare_columns
        self._config = config

    def _resolved_compare_columns(self, schema_names: list[str]) -> list[str]:
        return filter_compare_columns(self._compare_columns, schema_names)

    def run(self, *, workspace: Path | None = None) -> PipelineResult:
        source_bytes = _adapter_size_bytes(self._source)
        target_bytes = _adapter_size_bytes(self._target)
        compare_columns = self._resolved_compare_columns(self._source.get_schema().column_names)

        if self._config.enable_merkle_fast_path:
            prechecked = try_identical_precheck(
                self._source,
                self._target,
                compare_columns=compare_columns,
                enable_metadata=True,
                enable_content_digest=self._config.enable_content_digest_precheck,
            )
            if prechecked is not None:
                return prechecked

        if should_try_in_memory_reconcile(
            enable_in_memory_reconcile=self._config.enable_in_memory_reconcile,
            auto_in_memory_max_bytes=self._config.auto_in_memory_max_bytes,
            source_bytes=source_bytes,
            target_bytes=target_bytes,
        ):
            in_memory = try_in_memory_reconcile(
                self._source,
                self._target,
                identity_columns=self._identity_columns,
                compare_columns=compare_columns,
                memory_budget_bytes=self._config.memory_budget_bytes,
                enable_column_drilldown=self._config.enable_column_drilldown,
            )
            if in_memory is not None:
                in_memory.extra_stats["path"] = "in_memory_polars"
                return in_memory

        combined_bytes = source_bytes + target_bytes
        if (
            not self._config.force_disk_spill
            and combined_bytes <= self._config.polars_spill_max_bytes
        ):
            direct = try_in_memory_reconcile(
                self._source,
                self._target,
                identity_columns=self._identity_columns,
                compare_columns=compare_columns,
                memory_budget_bytes=self._config.memory_budget_bytes,
                enable_column_drilldown=self._config.enable_column_drilldown,
            )
            if direct is not None:
                direct.extra_stats["path"] = "polars_direct"
                return direct

        timings = PipelineTimings()
        t0 = time.perf_counter()

        num_partitions = _adaptive_partition_count(
            source_bytes=source_bytes,
            target_bytes=target_bytes,
            requested=self._config.resolved_partition_count(),
        )
        chunk_rows = self._config.chunk_rows
        enable_drilldown = self._config.enable_column_drilldown
        algo = self._config.fingerprint_algorithm

        src_schema = self._source.get_schema()
        tgt_schema = self._target.get_schema()
        schema_diffs = _compare_schemas(src_schema, tgt_schema)

        work = workspace or Path("/tmp/pegasus_reconcile")
        work.mkdir(parents=True, exist_ok=True)

        use_polars = combined_bytes <= self._config.polars_spill_max_bytes
        lazy_drilldown = (
            enable_drilldown
            and self._config.lazy_column_drilldown
            and use_polars
        )
        drilldown_cache = DrilldownCache(compare_columns) if lazy_drilldown else None
        spill_payload = enable_drilldown and not lazy_drilldown

        src_writer = PartitionWriter(
            work,
            "source",
            store_payload=spill_payload,
            compare_columns=compare_columns,
        )
        tgt_writer = PartitionWriter(
            work,
            "target",
            store_payload=spill_payload,
            compare_columns=compare_columns,
        )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(
                    self._partition_side,
                    self._source,
                    src_writer,
                    chunk_rows,
                    num_partitions,
                    spill_payload,
                    algo,
                    timings,
                    compare_columns,
                    drilldown_cache,
                    lazy_drilldown,
                    is_source=True,
                    use_polars=use_polars,
                ): "source",
                pool.submit(
                    self._partition_side,
                    self._target,
                    tgt_writer,
                    chunk_rows,
                    num_partitions,
                    spill_payload,
                    algo,
                    timings,
                    compare_columns,
                    drilldown_cache,
                    lazy_drilldown,
                    is_source=False,
                    use_polars=use_polars,
                ): "target",
            }
            counts: dict[str, int] = {}
            for fut in as_completed(futures):
                counts[futures[fut]] = fut.result()

        src_writer.close()
        tgt_writer.close()
        src_rows = counts.get("source", 0)
        tgt_rows = counts.get("target", 0)

        missing = extra = changed = matching = 0
        mismatched_partitions = 0
        samples: list[MismatchSample] = []
        sample_limit = 1000

        active_pids = list_partition_ids(work, "source") | list_partition_ids(work, "target")

        spill_bytes = 0
        for pid in active_pids:
            sp = work / "source" / f"part_{pid:05d}.bin"
            tp = work / "target" / f"part_{pid:05d}.bin"
            if sp.is_file():
                spill_bytes += sp.stat().st_size
            if tp.is_file():
                spill_bytes += tp.stat().st_size

        if (
            self._config.enable_merkle_fast_path
            and src_rows == tgt_rows
            and active_pids
            and len(active_pids) <= 64
            and spill_bytes <= self._config.spill_merkle_max_bytes
            and spill_partitions_identical(
                work,
                active_pids,
                max_bytes_to_hash=self._config.spill_merkle_max_bytes,
            )
        ):
            timings.total_seconds = time.perf_counter() - t0
            return PipelineResult(
                schema_valid=len(schema_diffs) == 0,
                schema_differences=schema_diffs,
                source_row_count=src_rows,
                target_row_count=tgt_rows,
                row_count_match=True,
                missing_count=0,
                extra_count=0,
                changed_count=0,
                matching_count=src_rows,
                partitions_processed=len(active_pids),
                mismatched_partitions=0,
                compared_columns=list(self._compare_columns),
                execution_seconds=timings.total_seconds,
                extra_stats={
                    "path": "precheck_spill_partitions",
                    "precheck_method": "partition_digest",
                    "timings": timings.to_dict(),
                },
            )

        with StageTimer(timings, "partition_reconciliation_seconds"):
            for pid in sorted(active_pids):
                src_path = work / "source" / f"part_{pid:05d}.bin"
                tgt_path = work / "target" / f"part_{pid:05d}.bin"

                use_spill_payload = enable_drilldown and drilldown_cache is None
                src_fp_map: dict[str, bytes] = {}
                src_payload_map: dict[str, dict[str, Any]] = {}
                with StageTimer(timings, "disk_read_seconds"):
                    for key, fp, payload in iter_partition(
                        src_path,
                        compare_columns=compare_columns if use_spill_payload else None,
                    ):
                        src_fp_map[key] = fp
                        if use_spill_payload and payload:
                            src_payload_map[key] = payload

                tgt_keys: set[str] = set()
                part_changed = part_missing = part_extra = 0

                with StageTimer(timings, "disk_read_seconds"):
                    for key, fp, payload in iter_partition(
                        tgt_path,
                        compare_columns=compare_columns if use_spill_payload else None,
                    ):
                        tgt_keys.add(key)
                        src_fp = src_fp_map.get(key)
                        if src_fp is None:
                            part_extra += 1
                            if len(samples) < sample_limit:
                                samples.append(MismatchSample(key, "extra"))
                        elif not _fp_equal(src_fp, fp):
                            part_changed += 1
                            if enable_drilldown and len(samples) < sample_limit:
                                col_diffs: list[ColumnDifference] = []
                                if drilldown_cache is not None:
                                    src_data = drilldown_cache.source_values(key)
                                    tgt_data = drilldown_cache.target_values(key)
                                else:
                                    src_data = src_payload_map.get(key, {})
                                    tgt_data = payload or {}
                                with StageTimer(timings, "column_comparison_seconds"):
                                    for col in compare_columns:
                                        sv = src_data.get(col)
                                        tv = tgt_data.get(col)
                                        if sv != tv:
                                            col_diffs.append(ColumnDifference(col, sv, tv))
                                samples.append(MismatchSample(key, "changed", col_diffs))
                        else:
                            matching += 1

                key_source = src_fp_map
                for key in key_source:
                    if key not in tgt_keys:
                        part_missing += 1
                        if len(samples) < sample_limit:
                            samples.append(MismatchSample(key, "missing"))

                missing += part_missing
                extra += part_extra
                changed += part_changed
                if part_missing or part_extra or part_changed:
                    mismatched_partitions += 1

        timings.total_seconds = time.perf_counter() - t0
        timings.network_transfer_seconds = (
            _adapter_network_seconds(self._source) + _adapter_network_seconds(self._target)
        )
        spill_path = "spill_binary"
        if lazy_drilldown:
            spill_path = "spill_binary_lazy_drilldown"
        elif self._config.use_columnar_spill:
            spill_path = "spill_columnar"
        return PipelineResult(
            schema_valid=len(schema_diffs) == 0,
            schema_differences=schema_diffs,
            source_row_count=src_rows,
            target_row_count=tgt_rows,
            row_count_match=(src_rows == tgt_rows),
            missing_count=missing,
            extra_count=extra,
            changed_count=changed,
            matching_count=matching,
            partitions_processed=len(active_pids),
            mismatched_partitions=mismatched_partitions,
            sample_mismatches=samples,
            compared_columns=list(compare_columns),
            execution_seconds=timings.total_seconds,
            extra_stats={
                "path": spill_path,
                "timings": timings.to_dict(),
                "fingerprint_algorithm": algo,
                "num_partitions": num_partitions,
                "active_partitions": len(active_pids),
                "lazy_column_drilldown": lazy_drilldown,
                "columnar_spill": self._config.use_columnar_spill,
            },
        )

    def _partition_side(
        self,
        adapter: TabularSourceAdapter,
        writer: PartitionWriter,
        chunk_rows: int,
        num_partitions: int,
        store_payload: bool,
        algorithm: str,
        timings: PipelineTimings,
        compare_columns: list[str],
        drilldown_cache: DrilldownCache | None,
        lazy_drilldown: bool,
        *,
        is_source: bool,
        use_polars: bool,
    ) -> int:
        spill_flags = {
            "drilldown_cache": drilldown_cache,
            "lazy_drilldown": lazy_drilldown,
            "use_columnar_spill": self._config.use_columnar_spill,
        }
        if use_polars:
            if can_use_polars_spill(adapter):
                return partition_side_polars(
                    adapter,  # type: ignore[arg-type]
                    writer,
                    identity_columns=self._identity_columns,
                    compare_columns=compare_columns,
                    num_partitions=num_partitions,
                    store_payload=store_payload,
                    timings=timings,
                    is_source=is_source,
                    **spill_flags,
                )
            polars_rows = try_partition_side_polars(
                adapter,
                writer,
                identity_columns=self._identity_columns,
                compare_columns=compare_columns,
                num_partitions=num_partitions,
                store_payload=store_payload,
                timings=timings,
                is_source=is_source,
                **spill_flags,
            )
            if polars_rows is not None:
                return polars_rows

        return self._partition_side_streaming(
            adapter,
            writer,
            chunk_rows,
            num_partitions,
            store_payload,
            algorithm,
            timings,
            compare_columns,
            is_source=is_source,
        )

    def _partition_side_streaming(
        self,
        adapter: TabularSourceAdapter,
        writer: PartitionWriter,
        chunk_rows: int,
        num_partitions: int,
        store_payload: bool,
        algorithm: str,
        timings: PipelineTimings,
        compare_columns: list[str],
        *,
        is_source: bool,
    ) -> int:
        part_field = "source_partition_seconds" if is_source else "target_partition_seconds"
        read_field = "source_read_seconds" if is_source else "target_read_seconds"
        total = 0

        with StageTimer(timings, part_field):
            with StageTimer(timings, read_field):
                chunks = adapter.stream_records(chunk_rows)
            id_cols = self._identity_columns
            cmp_cols = compare_columns
            for chunk in chunks:
                for record in chunk:
                    with StageTimer(timings, "canonicalization_seconds"):
                        id_parts = _canonical_parts(record, id_cols)
                        cmp_parts = _canonical_parts(record, cmp_cols)
                    with StageTimer(timings, "identity_generation_seconds"):
                        identity = identity_key_from_parts(id_parts)
                    with StageTimer(timings, "fingerprint_generation_seconds"):
                        fp = row_fingerprint_from_parts(cmp_parts, algorithm=algorithm)
                    with StageTimer(timings, "partition_calculation_seconds"):
                        pid = partition_id(identity, num_partitions)
                    with StageTimer(timings, "serialization_seconds"):
                        writer.write(pid, identity, fp, record)
                    with StageTimer(timings, "disk_write_seconds"):
                        pass
                    total += 1
        return total

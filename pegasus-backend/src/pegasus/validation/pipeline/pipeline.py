# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T05:34:17Z
# --- END GENERATED FILE METADATA ---

"""Six-stage tabular reconciliation pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
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
    _identity_parts,
)
from pegasus.validation.disk_guard import assert_disk_headroom, estimate_wave_disk_bytes
from pegasus.validation.lifecycle_profiler import lifecycle_span
from pegasus.validation.pipeline.mismatch_export import export_partitions_to_ndjson
from pegasus.validation.pipeline.in_memory import (
    should_try_in_memory_reconcile,
    try_in_memory_reconcile,
)
from pegasus.validation.pipeline.precheck import (
    spill_partitions_identical,
    try_identical_precheck,
)
from pegasus.validation.pipeline.drilldown_cache import DrilldownCache
from pegasus.validation.pipeline.live_progress import LiveProgressTracker
from pegasus.validation.pipeline.polars_spill import (
    try_partition_side_polars,
)
from pegasus.validation.pipeline.result import (
    MismatchSample,
    PipelineResult,
    SchemaDifference,
)
from pegasus.validation.pipeline.row_sanity import assert_reasonable_row_counts, estimate_min_rows_from_bytes
from pegasus.validation.pipeline.partition_reconcile import (
    reconcile_partition_vectorized,
    reconcile_partitions_parallel,
    resolved_reconcile_workers,
    should_parallel_reconcile,
)
from pegasus.validation.pipeline.spill import (
    PartitionWriter,
    delete_partition_files,
    list_partition_ids,
    partition_waves,
    workspace_spill_bytes,
)
from pegasus.validation.pipeline.timing import (
    PipelineIoStats,
    PipelineTimings,
    StageTimer,
    adapter_input_bytes,
    attach_stage_report,
    build_stage_metrics,
    publish_final_stages,
    publish_side_stages,
    publish_stage,
    reconcile_spill_bytes_read,
    spill_dir_bytes,
)


def _adapter_network_seconds(adapter: object) -> float:
    return float(getattr(adapter, "network_transfer_seconds", 0.0) or 0.0)


def _adapter_size_bytes(adapter: object) -> int:
    getter = getattr(adapter, "get_size_bytes", None)
    if callable(getter):
        return int(getter())
    return int(Path(getattr(adapter, "path")).stat().st_size)


def _estimate_row_count_from_bytes(file_bytes: int, *, column_count: int = 8) -> int:
    avg_row_bytes = max(48, 12 + 10 * max(1, column_count))
    return max(1, file_bytes // avg_row_bytes)


def _adaptive_partition_count(
    *,
    source_bytes: int,
    target_bytes: int,
    requested: int,
    compare_column_count: int = 8,
) -> int:
    """Use fewer buckets for small files to avoid empty-partition overhead."""
    file_bytes = source_bytes + target_bytes
    est_rows = _estimate_row_count_from_bytes(
        max(source_bytes, target_bytes),
        column_count=compare_column_count + 1,
    )
    rows_per_partition = 5_000 if est_rows >= 50_000_000 else (10_000 if est_rows >= 5_000_000 else 2000)
    max_partitions = 512
    if file_bytes >= 20 * 1024 * 1024 * 1024:
        max_partitions = 4096
    elif file_bytes >= 10 * 1024 * 1024 * 1024:
        max_partitions = 2048
    elif file_bytes >= 1024 * 1024 * 1024:
        max_partitions = 1024
    row_cap = max(
        4,
        min(max_partitions, (est_rows + rows_per_partition - 1) // rows_per_partition),
    )
    capped = min(requested, row_cap) if requested > 0 else row_cap
    if file_bytes <= 4 * 1024 * 1024:
        return min(capped, 16)
    if file_bytes <= 32 * 1024 * 1024:
        return min(capped, 64)
    if file_bytes <= 128 * 1024 * 1024:
        return min(capped, 256)
    return capped


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


def _adapter_uses_gcs(adapter: TabularSourceAdapter) -> bool:
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter

    return isinstance(adapter, GcsDelimitedAdapter)


def _delimiter_supports_fast_load(adapter: TabularSourceAdapter) -> bool:
    from pegasus.validation.readers.pyarrow_io import pyarrow_supports_delimiter

    delim = getattr(adapter, "_delimiter", "")
    return pyarrow_supports_delimiter(str(delim))


def _should_attempt_in_memory(
    source: TabularSourceAdapter,
    target: TabularSourceAdapter,
    *,
    source_bytes: int,
    target_bytes: int,
    config: TabularPipelineConfig,
) -> bool:
    """Skip auto in-memory for GCS streaming and multi-char delimiters (||, emoji, etc.)."""
    if config.gcs_streaming_only and (
        _adapter_uses_gcs(source) or _adapter_uses_gcs(target)
    ):
        # GCS always uses chunked streaming spill — never download full objects first.
        return False
    if not _delimiter_supports_fast_load(source) or not _delimiter_supports_fast_load(target):
        return should_try_in_memory_reconcile(
            enable_in_memory_reconcile=config.enable_in_memory_reconcile,
            auto_in_memory_max_bytes=config.auto_in_memory_max_bytes,
            source_bytes=source_bytes,
            target_bytes=target_bytes,
            memory_budget_bytes=config.memory_budget_bytes,
        )
    return should_try_in_memory_reconcile(
        enable_in_memory_reconcile=config.enable_in_memory_reconcile,
        auto_in_memory_max_bytes=config.auto_in_memory_max_bytes,
        source_bytes=source_bytes,
        target_bytes=target_bytes,
        memory_budget_bytes=config.memory_budget_bytes,
    )


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
        policy = self._config.compare_policy
        if policy is not None and policy.fields:
            return policy.compare_keys
        return filter_compare_columns(self._compare_columns, schema_names)

    def run(
        self,
        *,
        workspace: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> PipelineResult:
        from pegasus.validation.comparators.policy import compare_policy_context

        with compare_policy_context(self._config.compare_policy):
            return self._run_impl(
                workspace=workspace,
                progress_callback=progress_callback,
            )

    def _run_impl(
        self,
        *,
        workspace: Path | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> PipelineResult:
        source_bytes = _adapter_size_bytes(self._source)
        target_bytes = _adapter_size_bytes(self._target)
        with lifecycle_span("Schema And Planning"):
            compare_columns = self._resolved_compare_columns(
                self._source.get_schema().column_names
            )

        attempt_in_memory = not self._config.force_disk_spill and _should_attempt_in_memory(
            self._source,
            self._target,
            source_bytes=source_bytes,
            target_bytes=target_bytes,
            config=self._config,
        )
        if attempt_in_memory:
            with lifecycle_span("In-Memory Fast Path"):
                in_memory = try_in_memory_reconcile(
                    self._source,
                    self._target,
                    identity_columns=self._identity_columns,
                    compare_columns=compare_columns,
                    memory_budget_bytes=self._config.memory_budget_bytes,
                    auto_in_memory_max_bytes=self._config.auto_in_memory_max_bytes,
                    enable_column_drilldown=self._config.enable_column_drilldown,
                )
            if in_memory is not None:
                in_memory.extra_stats["path"] = "in_memory_polars"
                return in_memory

        if self._config.enable_merkle_fast_path:
            with lifecycle_span("Pipeline Precheck"):
                prechecked = try_identical_precheck(
                    self._source,
                    self._target,
                    compare_columns=compare_columns,
                    enable_metadata=True,
                    enable_content_digest=self._config.enable_content_digest_precheck,
                )
            if prechecked is not None:
                return prechecked

        combined_bytes = source_bytes + target_bytes
        uses_gcs = _adapter_uses_gcs(self._source) or _adapter_uses_gcs(self._target)
        if (
            not self._config.force_disk_spill
            and combined_bytes <= self._config.polars_spill_max_bytes
            and not attempt_in_memory
            and not uses_gcs
        ):
            with lifecycle_span("Polars Direct Fast Path"):
                direct = try_in_memory_reconcile(
                    self._source,
                    self._target,
                    identity_columns=self._identity_columns,
                    compare_columns=compare_columns,
                    memory_budget_bytes=self._config.memory_budget_bytes,
                    auto_in_memory_max_bytes=self._config.auto_in_memory_max_bytes,
                    enable_column_drilldown=self._config.enable_column_drilldown,
                )
            if direct is not None:
                direct.extra_stats["path"] = "polars_direct"
                return direct

        timings = PipelineTimings()
        process_cpu_start = time.process_time()
        t0 = time.perf_counter()
        io = PipelineIoStats(
            source_input_bytes=adapter_input_bytes(self._source),
            target_input_bytes=adapter_input_bytes(self._target),
        )

        num_partitions = _adaptive_partition_count(
            source_bytes=source_bytes,
            target_bytes=target_bytes,
            requested=self._config.resolved_partition_count(),
            compare_column_count=len(compare_columns) + len(self._identity_columns),
        )
        chunk_rows = self._config.chunk_rows
        enable_drilldown = self._config.enable_column_drilldown
        algo = self._config.fingerprint_algorithm

        src_schema = self._source.get_schema()
        tgt_schema = self._target.get_schema()
        schema_diffs = _compare_schemas(src_schema, tgt_schema)

        est_rows = _estimate_row_count_from_bytes(
            max(source_bytes, target_bytes),
            column_count=len(compare_columns) + len(self._identity_columns),
        )
        from pegasus.validation.readers import native_multichar

        native_disk_drilldown = (
            native_multichar.native_extension_available()
            and self._config.fingerprint_only_spill
            and self._config.force_native_multichar_spill
        )
        lazy_drilldown = enable_drilldown and (
            self._config.lazy_column_drilldown or self._config.fingerprint_only_spill
        )
        if lazy_drilldown and not native_disk_drilldown and est_rows > 250_000:
            lazy_drilldown = False
        drilldown_cache = (
            DrilldownCache(compare_columns)
            if lazy_drilldown and not native_disk_drilldown
            else None
        )
        spill_payload = (
            enable_drilldown
            and not lazy_drilldown
            and not self._config.fingerprint_only_spill
        )

        owned_workspace = workspace is None
        if owned_workspace:
            work = Path(tempfile.mkdtemp(prefix="pegasus_reconcile_"))
        else:
            work = workspace
            work.mkdir(parents=True, exist_ok=True)

        try:
            return self._run_spill_path(
                work=work,
                timings=timings,
                process_cpu_start=process_cpu_start,
                t0=t0,
                io=io,
                source_bytes=source_bytes,
                target_bytes=target_bytes,
                num_partitions=num_partitions,
                chunk_rows=chunk_rows,
                compare_columns=compare_columns,
                schema_diffs=schema_diffs,
                spill_payload=spill_payload,
                algo=algo,
                lazy_drilldown=lazy_drilldown,
                drilldown_cache=drilldown_cache,
                progress_callback=progress_callback,
                est_rows=est_rows,
                persist_drilldown=not owned_workspace,
                native_disk_drilldown=native_disk_drilldown,
            )
        finally:
            if owned_workspace:
                shutil.rmtree(work, ignore_errors=True)

    def _run_spill_path(
        self,
        *,
        work: Path,
        timings: PipelineTimings,
        process_cpu_start: float,
        t0: float,
        io: PipelineIoStats,
        source_bytes: int,
        target_bytes: int,
        num_partitions: int,
        chunk_rows: int,
        compare_columns: list[str],
        schema_diffs: list[SchemaDifference],
        spill_payload: bool,
        algo: str,
        lazy_drilldown: bool,
        drilldown_cache: DrilldownCache | None,
        progress_callback: Callable[[dict[str, Any]], None] | None,
        est_rows: int,
        persist_drilldown: bool = False,
        native_disk_drilldown: bool = False,
    ) -> PipelineResult:
        from pegasus.validation.pipeline.partition_merkle import PartitionMerkleAccumulator

        merkle_candidate = (
            self._config.enable_merkle_fast_path
            and source_bytes == target_bytes
            and source_bytes > 0
        )
        src_merkle = PartitionMerkleAccumulator() if merkle_candidate else None
        tgt_merkle = PartitionMerkleAccumulator() if merkle_candidate else None
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

        live_progress: LiveProgressTracker | None = None
        if progress_callback is not None:
            live_progress = LiveProgressTracker(
                progress_callback,
                chunk_rows=chunk_rows,
                column_count=len(compare_columns) + len(self._identity_columns),
                partition_buckets=num_partitions,
                partition_workers=2,
                est_rows=est_rows,
            )
            live_progress.begin_partition()

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
                    merkle=src_merkle,
                    live_progress=live_progress,
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
                    merkle=tgt_merkle,
                    live_progress=live_progress,
                ): "target",
            }
            counts: dict[str, int] = {}
            for fut in as_completed(futures):
                side = futures[fut]
                counts[side] = fut.result()
                if side == "source":
                    src_writer.close()
                    io.source_input_bytes = adapter_input_bytes(self._source)
                    io.source_spill_bytes = spill_dir_bytes(work, "source")
                    publish_side_stages(
                        timings, io, is_source=True, progress_callback=progress_callback
                    )
                else:
                    tgt_writer.close()
                    io.target_input_bytes = adapter_input_bytes(self._target)
                    io.target_spill_bytes = spill_dir_bytes(work, "target")
                    publish_side_stages(
                        timings, io, is_source=False, progress_callback=progress_callback
                    )
            try:
                assert_disk_headroom(
                    work,
                    required_bytes=max(
                        workspace_spill_bytes(work),
                        estimate_wave_disk_bytes(
                            combined_input_bytes=source_bytes + target_bytes,
                            num_partitions=num_partitions,
                            wave_size=num_partitions,
                            disk_multiplier=self._config.disk_headroom_multiplier,
                        ),
                    ),
                )
            except OSError as exc:
                raise RuntimeError(str(exc)) from exc
        src_rows = counts.get("source", 0)
        tgt_rows = counts.get("target", 0)

        missing = extra = changed = matching = 0
        mismatched_partitions = 0
        samples: list[MismatchSample] = []
        sample_limit = 1000

        active_pids = list_partition_ids(work, "source") | list_partition_ids(work, "target")

        if (
            self._config.enable_merkle_fast_path
            and src_merkle is not None
            and tgt_merkle is not None
            and src_rows == tgt_rows
            and src_rows > 0
            and src_merkle.identical_to(tgt_merkle, active_pids)
        ):
            timings.total_seconds = time.perf_counter() - t0
            timings.total_cpu_seconds = time.process_time() - process_cpu_start
            io.reconcile_spill_bytes_read = 0
            extra_stats = {
                "path": "precheck_chunk_merkle",
                "precheck_method": "chunk_merkle",
            }
            attach_stage_report(extra_stats, timings, io)
            publish_final_stages(
                timings, io, progress_callback=progress_callback, include_report=False
            )
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
                compared_columns=list(compare_columns),
                execution_seconds=timings.total_seconds,
                extra_stats=extra_stats,
            )

        spill_bytes = 0
        for pid in active_pids:
            sp = work / "source" / f"part_{pid:05d}.bin"
            tp = work / "target" / f"part_{pid:05d}.bin"
            if sp.is_file():
                spill_bytes += sp.stat().st_size
            if tp.is_file():
                spill_bytes += tp.stat().st_size

        input_bytes = io.source_input_bytes + io.target_input_bytes
        spill_suspiciously_small = (
            input_bytes > 512 * 1024
            and spill_bytes > 0
            and spill_bytes < max(4096, input_bytes // 500)
        )
        min_rows_floor = max(
            100,
            estimate_min_rows_from_bytes(
                max(io.source_input_bytes, io.target_input_bytes),
                column_count=len(compare_columns) + len(self._identity_columns),
            )
            // 20,
        )
        if (
            self._config.enable_merkle_fast_path
            and src_rows == tgt_rows
            and src_rows >= min_rows_floor
            and not spill_suspiciously_small
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
            timings.total_cpu_seconds = time.process_time() - process_cpu_start
            io.reconcile_spill_bytes_read = reconcile_spill_bytes_read(work, active_pids)
            extra_stats: dict[str, Any] = {
                "path": "precheck_spill_partitions",
                "precheck_method": "partition_digest",
            }
            attach_stage_report(extra_stats, timings, io)
            publish_final_stages(
                timings, io, progress_callback=progress_callback, include_report=False
            )
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
                extra_stats=extra_stats,
            )

        use_spill_payload = spill_payload
        reconcile_workers = resolved_reconcile_workers(self._config.partition_reconcile_workers)
        combined_bytes = source_bytes + target_bytes
        wave_size = self._config.partition_wave_size
        use_waves = (
            wave_size > 0
            and combined_bytes >= self._config.wave_min_bytes
            and len(active_pids) > wave_size
        )
        sorted_pids = sorted(active_pids)
        waves = partition_waves(sorted_pids, wave_size) if use_waves else [sorted_pids]
        mismatch_export_path = (
            work / "mismatches_partial.ndjson"
            if use_waves and self._config.stream_mismatches_to_disk
            else None
        )

        try:
            assert_disk_headroom(
                work,
                required_bytes=estimate_wave_disk_bytes(
                    combined_input_bytes=combined_bytes,
                    num_partitions=num_partitions,
                    wave_size=wave_size if use_waves else len(sorted_pids),
                    disk_multiplier=self._config.disk_headroom_multiplier,
                ),
            )
        except OSError as exc:
            raise RuntimeError(str(exc)) from exc

        if live_progress is not None:
            live_progress.begin_reconcile(
                partitions_total=len(active_pids),
                reconcile_workers=reconcile_workers,
            )
        elif progress_callback:
            progress_callback(
                {"phase": "reconciling", "message": "Reconciling partitions"}
            )

        reconcile_bytes_read = 0
        partitions_done = 0
        start_wave = 0
        if use_waves:
            ck_path = work / "wave_checkpoint.json"
            if ck_path.is_file():
                try:
                    ck = json.loads(ck_path.read_text(encoding="utf-8"))
                    start_wave = int(ck.get("completed_wave", -1)) + 1
                    if start_wave > 0:
                        missing = int(ck.get("missing", missing))
                        extra = int(ck.get("extra", extra))
                        changed = int(ck.get("changed", changed))
                        matching = int(ck.get("matching", matching))
                        mismatched_partitions = int(
                            ck.get("mismatched_partitions", mismatched_partitions)
                        )
                        partitions_done = int(ck.get("partitions_done", 0))
                        if progress_callback:
                            progress_callback(
                                {
                                    "phase": "reconciling",
                                    "message": f"Resuming from wave {start_wave + 1}/{len(waves)}",
                                    "wave_index": start_wave,
                                    "wave_total": len(waves),
                                }
                            )
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    start_wave = 0
        from pegasus.validation.workers.coordinator import DistributedReconciliationCoordinator

        use_distributed = DistributedReconciliationCoordinator.should_use(
            enabled=self._config.distributed_enabled,
            redis_url=self._config.distributed_redis_url,
            combined_bytes=combined_bytes,
            min_bytes=self._config.distributed_min_bytes,
        )
        distributed_job_id = self._config.distributed_job_id or "pegasus-local"

        for wave_idx, wave_pids in enumerate(waves):
            if wave_idx < start_wave:
                continue
            if use_waves:
                assert_disk_headroom(
                    work,
                    required_bytes=estimate_wave_disk_bytes(
                        combined_input_bytes=combined_bytes,
                        num_partitions=num_partitions,
                        wave_size=len(wave_pids),
                        disk_multiplier=self._config.disk_headroom_multiplier,
                    ),
                )
                if progress_callback:
                    progress_callback(
                        {
                            "phase": "reconciling",
                            "message": f"Reconciling wave {wave_idx + 1}/{len(waves)}",
                            "wave_index": wave_idx,
                            "wave_total": len(waves),
                        }
                    )
            wave_set = set(wave_pids)
            distributed_result = None
            if use_distributed:
                coordinator = DistributedReconciliationCoordinator(
                    redis_url=str(self._config.distributed_redis_url),
                    work_dir=work,
                )
                distributed_result = coordinator.reconcile_partitions(
                    distributed_job_id,
                    wave_pids,
                    timeout_seconds=max(300, int(self._config.memory_budget_bytes // (1024**2))),
                )

            if distributed_result is not None:
                w_missing, w_extra, w_changed, w_matching, w_mismatched = distributed_result
            elif should_parallel_reconcile(
                num_partitions=len(wave_set),
                workers=reconcile_workers,
                input_bytes=source_bytes + target_bytes,
            ):
                w_missing, w_extra, w_changed, w_matching, w_mismatched = reconcile_partitions_parallel(
                    work,
                    wave_set,
                    compare_columns=compare_columns,
                    enable_drilldown=self._config.enable_column_drilldown,
                    drilldown_cache=drilldown_cache,
                    sample_limit=sample_limit,
                    samples=samples,
                    timings=timings,
                    use_spill_payload=use_spill_payload,
                    max_workers=reconcile_workers,
                    live_progress=live_progress,
                    use_processes=self._config.partition_reconcile_use_processes,
                )
            else:
                w_missing = w_extra = w_changed = w_matching = w_mismatched = 0
                for pid in wave_pids:
                    src_path = work / "source" / f"part_{pid:05d}.bin"
                    tgt_path = work / "target" / f"part_{pid:05d}.bin"
                    part_missing, part_extra, part_changed, part_matching = reconcile_partition_vectorized(
                        src_path,
                        tgt_path,
                        compare_columns=compare_columns,
                        enable_drilldown=self._config.enable_column_drilldown,
                        drilldown_cache=drilldown_cache,
                        sample_limit=sample_limit,
                        samples=samples,
                        timings=timings,
                        use_spill_payload=use_spill_payload,
                    )
                    w_missing += part_missing
                    w_extra += part_extra
                    w_changed += part_changed
                    w_matching += part_matching
                    if part_missing or part_extra or part_changed:
                        w_mismatched += 1

            missing += w_missing
            extra += w_extra
            changed += w_changed
            matching += w_matching
            mismatched_partitions += w_mismatched
            reconcile_bytes_read += reconcile_spill_bytes_read(work, wave_set)
            partitions_done += len(wave_pids)
            if live_progress is not None:
                live_progress.on_reconcile_done(partitions_done=partitions_done)

            if use_waves:
                if mismatch_export_path is not None:
                    export_partitions_to_ndjson(
                        work,
                        mismatch_export_path,
                        compare_columns=compare_columns,
                        pids=wave_pids,
                        append=wave_idx > 0,
                    )
                delete_partition_files(work, wave_pids)
                checkpoint = {
                    "completed_wave": wave_idx,
                    "total_waves": len(waves),
                    "partitions_done": partitions_done,
                    "missing": missing,
                    "extra": extra,
                    "changed": changed,
                    "matching": matching,
                    "mismatched_partitions": mismatched_partitions,
                }
                (work / "wave_checkpoint.json").write_text(
                    json.dumps(checkpoint),
                    encoding="utf-8",
                )

        if not use_waves and live_progress is not None and partitions_done == 0:
            live_progress.on_reconcile_done(partitions_done=len(active_pids))

        timings.total_seconds = time.perf_counter() - t0
        timings.total_cpu_seconds = time.process_time() - process_cpu_start
        timings.network_transfer_seconds = (
            _adapter_network_seconds(self._source) + _adapter_network_seconds(self._target)
        )
        io.reconcile_spill_bytes_read = (
            reconcile_bytes_read if use_waves else reconcile_spill_bytes_read(work, active_pids)
        )
        io.source_input_bytes = adapter_input_bytes(self._source)
        io.target_input_bytes = adapter_input_bytes(self._target)
        reconcile_stage = next(
            s
            for s in build_stage_metrics(timings, io)
            if s.name == "Reconciliation"
        )
        publish_stage(reconcile_stage, progress_callback=progress_callback)
        spill_path = "spill_binary"
        if lazy_drilldown and native_disk_drilldown:
            spill_path = "spill_native_multichar_drilldown"
        elif self._config.use_arrow_ipc_spill and not spill_payload:
            spill_path = "spill_arrow_ipc"
        elif lazy_drilldown:
            spill_path = "spill_binary_lazy_drilldown"
        elif self._config.use_columnar_spill:
            spill_path = "spill_columnar"
        extra_stats = _build_extra_stats(
            path=spill_path,
            timings=timings,
            io=io,
            fingerprint_algorithm=algo,
            num_partitions=num_partitions,
            active_partitions=len(active_pids),
            lazy_column_drilldown=lazy_drilldown,
            columnar_spill=self._config.use_columnar_spill,
            arrow_ipc_spill=self._config.use_arrow_ipc_spill,
            fingerprint_only_spill=self._config.fingerprint_only_spill,
            chunk_rows=chunk_rows,
            reconcile_workers=reconcile_workers,
        )
        if use_waves:
            extra_stats["partition_waves"] = len(waves)
            extra_stats["partition_wave_size"] = wave_size
            if mismatch_export_path is not None and mismatch_export_path.is_file():
                extra_stats["mismatch_export_path"] = str(mismatch_export_path)
        if use_distributed:
            extra_stats["distributed_reconcile"] = True
        assert_reasonable_row_counts(
            self._source,
            self._target,
            source_rows=src_rows,
            target_rows=tgt_rows,
            compare_column_count=len(compare_columns),
        )

        publish_final_stages(
            timings, io, progress_callback=progress_callback, include_report=False
        )
        if persist_drilldown and drilldown_cache is not None:
            drilldown_cache.persist(work)
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
            extra_stats=extra_stats,
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
        merkle: object | None = None,
        live_progress: LiveProgressTracker | None = None,
    ) -> int:
        side = "source" if is_source else "target"
        if live_progress is not None:
            live_progress.side_started(side)
        spill_flags = {
            "drilldown_cache": drilldown_cache,
            "lazy_drilldown": lazy_drilldown,
            "use_columnar_spill": self._config.use_columnar_spill,
            "use_arrow_ipc_spill": self._config.use_arrow_ipc_spill,
            "merkle": merkle,
            "force_native_multichar_spill": self._config.force_native_multichar_spill,
        }
        polars_rows = try_partition_side_polars(
            adapter,
            writer,
            identity_columns=self._identity_columns,
            compare_columns=compare_columns,
            num_partitions=num_partitions,
            store_payload=store_payload,
            timings=timings,
            is_source=is_source,
            streaming_spill_min_bytes=self._config.streaming_spill_min_bytes,
            chunk_rows=self._config.chunk_rows,
            live_progress=live_progress,
            **spill_flags,
        )
        if polars_rows is not None:
            if live_progress is not None:
                live_progress.side_finished(side, total_rows=polars_rows)
            return polars_rows

        rows = self._partition_side_streaming(
            adapter,
            writer,
            chunk_rows,
            num_partitions,
            store_payload,
            algorithm,
            timings,
            compare_columns,
            is_source=is_source,
            live_progress=live_progress,
        )
        if live_progress is not None:
            live_progress.side_finished(side, total_rows=rows)
        return rows

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
        live_progress: LiveProgressTracker | None = None,
    ) -> int:
        side = "source" if is_source else "target"
        part_field = "source_partition_seconds" if is_source else "target_partition_seconds"
        read_field = "source_read_seconds" if is_source else "target_read_seconds"
        total = 0
        chunk_index = 0

        with StageTimer(timings, part_field):
            with StageTimer(timings, read_field):
                chunks = adapter.stream_records(chunk_rows)
            id_cols = self._identity_columns
            cmp_cols = compare_columns
            for chunk in chunks:
                if live_progress is not None:
                    live_progress.on_chunk(
                        side,
                        chunk_index=chunk_index,
                        rows_in_chunk=len(chunk),
                    )
                side_name = "source" if is_source else "target"
                for record in chunk:
                    with StageTimer(timings, "canonicalization_seconds"):
                        id_parts = _identity_parts(record, id_cols)
                        cmp_parts = _canonical_parts(record, cmp_cols, side=side_name)
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
                chunk_index += 1
        return total


def _build_extra_stats(
    *,
    path: str,
    timings: PipelineTimings,
    io: PipelineIoStats,
    fingerprint_algorithm: str,
    num_partitions: int,
    active_partitions: int,
    lazy_column_drilldown: bool,
    columnar_spill: bool,
    arrow_ipc_spill: bool,
    fingerprint_only_spill: bool,
    chunk_rows: int | None = None,
    reconcile_workers: int | None = None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "path": path,
        "fingerprint_algorithm": fingerprint_algorithm,
        "num_partitions": num_partitions,
        "partition_buckets": num_partitions,
        "active_partitions": active_partitions,
        "lazy_column_drilldown": lazy_column_drilldown,
        "columnar_spill": columnar_spill,
        "arrow_ipc_spill": arrow_ipc_spill,
        "fingerprint_only_spill": fingerprint_only_spill,
    }
    if chunk_rows is not None:
        extra["chunk_rows"] = chunk_rows
    if reconcile_workers is not None:
        extra["reconcile_workers"] = reconcile_workers
    attach_stage_report(extra, timings, io)
    return extra

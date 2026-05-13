"""Reconciliation coordinator: strategy selection, spill/sort orchestration, and reporting."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from pegasus.validation.comparators.exceptions import UIDComparisonError
from pegasus.validation.comparators.models import MismatchReport
from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader

from .config import ReconciliationBackend, ReconciliationRuntimeConfig, ReconciliationStrategy
from .disk_guard import ensure_disk_headroom
from .duckdb_reconciliation_engine import DuckDBReconciliationEngine
from .exceptions import ReconciliationError, ReconciliationStrategyError
from .external_merge_sort import ExternalMergeSortEngine
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics
from .mismatch_collector import MismatchCollector, MismatchSink
from .ordered_stream import merge_sorted_csv_streams, merge_sorted_parquet_streams
from .partition_comparator import PartitionComparator
from .partition_manager import (
    PartitionManager,
    multichar_csv_header_frame,
    spill_multichar_csv_via_pandas,
)
from .streaming_mismatch_collector import StreamingMismatchCollector
from .temp_workspace import temp_reconciliation_workspace

logger = logging.getLogger(__name__)


def _persist_mismatch_artifact_outside_workspace(
    workspace: Path,
    cfg: ReconciliationRuntimeConfig,
    report: MismatchReport,
) -> MismatchReport:
    """Copy streaming mismatch NDJSON out of the ephemeral spill workspace before it is deleted."""
    src = report.mismatch_artifact_path
    if src is None or not src.is_file():
        return report
    dest = cfg.artifact_export_path
    if dest is None:
        dest = workspace.parent / f"pegasus_mismatches_{uuid.uuid4().hex}.ndjson"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return replace(report, mismatch_artifact_path=dest)


def _make_collector(
    cfg: ReconciliationRuntimeConfig,
    workspace: Path,
    strategy: ReconciliationStrategy,
) -> MismatchCollector | StreamingMismatchCollector:
    mirror = (workspace / "mismatch_mirror.ndjson") if cfg.mismatch_ndjson_mirror else None
    omit = strategy == ReconciliationStrategy.HASH_PARTITION
    mirror_path = mirror if strategy == ReconciliationStrategy.HASH_PARTITION else None
    if cfg.stream_mismatches:
        return StreamingMismatchCollector(
            workspace / "mismatches.ndjson",
            stringify_null_in_report=cfg.stringify_null_in_report,
            omit_row_detail=omit,
            ndjson_mirror_path=mirror_path,
        )
    return MismatchCollector(
        stringify_null_in_report=cfg.stringify_null_in_report,
        omit_row_detail=omit,
        ndjson_mirror_path=mirror_path,
    )


def _compare_spilled_hash_partitions(
    *,
    workspace: Path,
    cfg: ReconciliationRuntimeConfig,
    uid_column: str,
    compare_columns: list[str],
    collector: MismatchSink,
    metrics: ReconciliationMetrics,
) -> None:
    """Walk spilled Parquet shards (optional sub-buckets) and run sort-merge per cell."""
    sub = cfg.sub_partition_buckets
    
    # Prepare partition tasks
    tasks = []
    for pid in range(cfg.partition_buckets):
        if sub <= 1:
            src_base = workspace / "partitions" / "source" / f"p={pid}"
            tgt_base = workspace / "partitions" / "target" / f"p={pid}"
            src_files = sorted(src_base.glob("shard_*.parquet")) if src_base.exists() else []
            tgt_files = sorted(tgt_base.glob("shard_*.parquet")) if tgt_base.exists() else []
            if src_files or tgt_files:
                tasks.append((pid, 0, src_files, tgt_files))
        else:
            for sid in range(sub):
                src_base = workspace / "partitions" / "source" / f"p={pid}" / f"s={sid}"
                tgt_base = workspace / "partitions" / "target" / f"p={pid}" / f"s={sid}"
                src_files = sorted(src_base.glob("shard_*.parquet")) if src_base.exists() else []
                tgt_files = sorted(tgt_base.glob("shard_*.parquet")) if tgt_base.exists() else []
                if src_files or tgt_files:
                    tasks.append((pid, sid, src_files, tgt_files))

    if not tasks:
        return

    # Use parallel processes if enabled, otherwise sequential
    if cfg.parallel_partition_comparison and len(tasks) > 1:
        logger.info("Comparing %d partitions in parallel using ProcessPoolExecutor", len(tasks))
        worker_dir = workspace / "workers"
        worker_dir.mkdir(parents=True, exist_ok=True)
        
        # Limit workers to avoid thread thrashing on limited core systems
        max_workers = max(1, (os.cpu_count() or 4) - 1)
        
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = []
            for pid, sid, src_files, tgt_files in tasks:
                worker_out = worker_dir / f"mismatch_{pid}_{sid}.ndjson"
                futures.append(pool.submit(
                    _run_partition_worker,
                    workspace=workspace,
                    partition_id=pid,
                    sub_partition_id=sid,
                    source_shards=src_files,
                    target_shards=tgt_files,
                    uid_column=uid_column,
                    compare_columns=compare_columns,
                    chunk_rows=cfg.chunk_rows,
                    out_path=worker_out,
                ))
            
            for fut in as_completed(futures):
                try:
                    p_id, s_id, count, worker_path = fut.result()
                    if count > 0 and worker_path.exists():
                        # Use bulk append to merge worker results efficiently
                        if hasattr(collector, "bulk_append_from_frame"):
                            worker_df = pl.read_ndjson(worker_path)
                            collector.bulk_append_from_frame(worker_df)
                        elif isinstance(collector, StreamingMismatchCollector):
                            with open(worker_path, "rb") as f_in:
                                with open(collector._path, "ab") as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                        else:
                            import json
                            with open(worker_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    collector._apply_raw_mismatch(json.loads(line))
                    
                    metrics.on_partition_done(p_id, sub_partitions=sub if sub > 1 else 0)
                except Exception as exc:
                    logger.error("Partition worker failed: %s", exc)
                    raise ReconciliationError("Parallel partition comparison failed") from exc
    else:
        part_cmp = PartitionComparator(metrics=metrics)
        for pid, sid, src_files, tgt_files in tasks:
            part_cmp.compare_partition_shards(
                workspace=workspace,
                partition_id=pid,
                sub_partition_id=sid,
                source_shards=src_files,
                target_shards=tgt_files,
                uid_column=uid_column,
                compare_columns=compare_columns,
                collector=collector,
                batch_rows=cfg.chunk_rows,
            )
            metrics.on_partition_done(pid, sub_partitions=sub if sub > 1 else 0)


def _run_partition_worker(
    *,
    workspace: Path,
    partition_id: int,
    sub_partition_id: int,
    source_shards: list[Path],
    target_shards: list[Path],
    uid_column: str,
    compare_columns: list[str],
    chunk_rows: int,
    out_path: Path,
) -> tuple[int, int, int, Path]:
    """Independent worker function for ProcessPoolExecutor."""
    # Crucial for Linux: prevent nested parallelism from thrashing the 4 CPU cores
    os.environ["POLARS_MAX_THREADS"] = "1"
    
    # Create a transient collector for this worker
    from .streaming_mismatch_collector import StreamingMismatchCollector
    worker_collector = StreamingMismatchCollector(out_path)
    
    part_cmp = PartitionComparator()
    part_cmp.compare_partition_shards(
        workspace=workspace,
        partition_id=partition_id,
        sub_partition_id=sub_partition_id,
        source_shards=source_shards,
        target_shards=target_shards,
        uid_column=uid_column,
        compare_columns=compare_columns,
        collector=worker_collector,
        batch_rows=chunk_rows,
    )
    report = worker_collector.finish()
    mismatch_count = sum(report.summary.values())
    return partition_id, sub_partition_id, mismatch_count, out_path


class ReconciliationCoordinator:
    """High-level entry point for external-memory CSV reconciliation.

    Orchestrates :class:`PartitionManager` (spill), :class:`PartitionComparator`
    (per-bucket sort + merge), optional external sort / ordered streams, and
    :class:`MismatchCollector` reporting. Uses :class:`~pegasus.validation.readers.polars_csv_reader.PolarsCSVReader`
    (or :class:`StreamCSVReader`) for chunked reads only—never materializes full inputs
    in hash-partition mode.
    """

    __slots__ = ("_reader", "_metrics")

    def __init__(
        self,
        reader: PolarsCSVReader | None = None,
        *,
        metrics: ReconciliationMetrics | None = None,
    ) -> None:
        self._reader = reader or PolarsCSVReader()
        self._metrics = metrics or NoOpReconciliationMetrics()

    def run_csv_pair(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[MismatchReport, int, int, ReconciliationStrategy]:
        """Execute reconciliation for a single source/target CSV pair on local disk.

        Returns
        -------
        tuple
            ``(report, source_row_count, target_row_count, resolved_strategy)``
        """
        if len(delimiter) != 1:
            raise ReconciliationStrategyError(
                "External-memory reconciliation currently requires a single-character delimiter "
                "(Polars lazy CSV). Use validation without external mode for multi-char separators."
            )

        strategy = self._resolve_strategy(cfg, source_path=source_path, target_path=target_path)
        logger.info(
            "Starting reconciliation strategy=%s chunk_rows=%d partitions=%d assume_sorted=%s",
            strategy,
            cfg.chunk_rows,
            cfg.partition_buckets,
            cfg.assume_sorted,
        )

        last_error: BaseException | None = None
        for attempt in range(1, cfg.retry_max_attempts + 1):
            try:
                return self._run_once(
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid_column,
                    delimiter=delimiter,
                    compare_columns=compare_columns,
                    cfg=cfg,
                    strategy=strategy,
                    progress_callback=progress_callback,
                )
            except (ReconciliationError, UIDComparisonError, OSError) as exc:
                last_error = exc
                self._metrics.on_retry(attempt, exc, strategy=strategy.value)
                logger.warning("Reconciliation attempt %s/%s failed: %s", attempt, cfg.retry_max_attempts, exc)
                if attempt >= cfg.retry_max_attempts:
                    break
                time.sleep(min(2**attempt, 30) * 0.05)

        assert last_error is not None
        if isinstance(last_error, UIDComparisonError):
            raise last_error
        raise ReconciliationError("Reconciliation failed after retries") from last_error

    def run_multichar_hash_partition_csv_pair(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
    ) -> tuple[MismatchReport, int, int, ReconciliationStrategy]:
        """Hash-partition validation for multi-character separators using chunked pandas reads.

        Avoids loading entire CSVs into RAM (which otherwise causes OOM kills on large ``||``-style files).
        """
        if len(delimiter) < 2:
            raise ReconciliationStrategyError(
                "run_multichar_hash_partition_csv_pair requires a multi-character delimiter"
            )
        logger.info(
            "Starting multichar hash-partition reconciliation delimiter=%r buckets=%d sub=%d chunk_rows=%d",
            delimiter,
            cfg.partition_buckets,
            cfg.sub_partition_buckets,
            cfg.chunk_rows,
        )

        with temp_reconciliation_workspace(cfg.temp_dir) as workspace:
            combined = source_path.stat().st_size + target_path.stat().st_size
            ensure_disk_headroom(
                workspace,
                int(combined * cfg.disk_headroom_multiplier),
                label="multichar hash-partition spill/sort",
            )
            collector = _make_collector(cfg, workspace, ReconciliationStrategy.HASH_PARTITION)
            src_rows = spill_multichar_csv_via_pandas(
                source_path,
                workspace=workspace,
                side="source",
                uid_column=uid_column,
                delimiter=delimiter,
                buckets=cfg.partition_buckets,
                chunk_rows=cfg.chunk_rows,
                metrics=self._metrics,
                sub_partition_buckets=cfg.sub_partition_buckets,
            )
            tgt_rows = spill_multichar_csv_via_pandas(
                target_path,
                workspace=workspace,
                side="target",
                uid_column=uid_column,
                delimiter=delimiter,
                buckets=cfg.partition_buckets,
                chunk_rows=cfg.chunk_rows,
                metrics=self._metrics,
                sub_partition_buckets=cfg.sub_partition_buckets,
            )
            _compare_spilled_hash_partitions(
                workspace=workspace,
                cfg=cfg,
                uid_column=uid_column,
                compare_columns=compare_columns,
                collector=collector,
                metrics=self._metrics,
            )

            report = collector.finish()
            n_mismatch = report.mismatches.height if report.mismatch_artifact_path is None else sum(
                report.summary.values()
            )
            logger.info(
                "Multichar hash-partition complete source_rows=%d target_rows=%d mismatch_rows=%d",
                src_rows,
                tgt_rows,
                n_mismatch,
            )
            report = _persist_mismatch_artifact_outside_workspace(workspace, cfg, report)
            return report, src_rows, tgt_rows, ReconciliationStrategy.HASH_PARTITION

    def _resolve_strategy(
        self,
        cfg: ReconciliationRuntimeConfig,
        *,
        source_path: Path,
        target_path: Path,
    ) -> ReconciliationStrategy:
        if cfg.strategy != ReconciliationStrategy.AUTO:
            return cfg.strategy

        total_bytes = source_path.stat().st_size + target_path.stat().st_size
        if total_bytes <= cfg.external_memory_threshold_bytes and not cfg.force_external:
            raise ReconciliationStrategyError(
                "AUTO strategy selected but combined file size is below external_memory_threshold_bytes; "
                "use the in-memory validation path instead."
            )

        if cfg.assume_sorted and cfg.sliding_window > 0:
            return ReconciliationStrategy.EXTERNAL_SORT
        if cfg.assume_sorted:
            return ReconciliationStrategy.ORDERED_STREAM
        return ReconciliationStrategy.HASH_PARTITION

    def _run_once(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
        strategy: ReconciliationStrategy,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[MismatchReport, int, int, ReconciliationStrategy]:
        base_temp = cfg.temp_dir
        with temp_reconciliation_workspace(base_temp) as workspace:
            if cfg.backend == ReconciliationBackend.DUCKDB and strategy == ReconciliationStrategy.HASH_PARTITION:
                eng = DuckDBReconciliationEngine(metrics=self._metrics)
                report, src_rows, tgt_rows, strat = eng.run_csv_pair(
                    workspace=workspace,
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid_column,
                    delimiter=delimiter,
                    compare_columns=compare_columns,
                    cfg=cfg,
                    progress_callback=progress_callback,
                )
                report = _persist_mismatch_artifact_outside_workspace(workspace, cfg, report)
                logger.info(
                    "DuckDB reconciliation finished source_rows=%d target_rows=%d artifact=%s",
                    src_rows,
                    tgt_rows,
                    report.mismatch_artifact_path,
                )
                return report, src_rows, tgt_rows, strat

            collector = _make_collector(cfg, workspace, strategy)
            if strategy == ReconciliationStrategy.HASH_PARTITION:
                src_rows, tgt_rows = self._run_hash_partition(
                    workspace=workspace,
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid_column,
                    delimiter=delimiter,
                    compare_columns=compare_columns,
                    cfg=cfg,
                    collector=collector,
                )
                report = collector.finish()
                report = _persist_mismatch_artifact_outside_workspace(workspace, cfg, report)
                return report, src_rows, tgt_rows, strategy

            if strategy in (ReconciliationStrategy.EXTERNAL_SORT, ReconciliationStrategy.SLIDING_WINDOW):
                window = (
                    cfg.sliding_window
                    if strategy == ReconciliationStrategy.SLIDING_WINDOW
                    else max(0, cfg.sliding_window)
                )
                if strategy == ReconciliationStrategy.SLIDING_WINDOW and window <= 0:
                    window = 512
                src_rows, tgt_rows, resolved = self._run_external_sort_then_merge(
                    workspace=workspace,
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid_column,
                    delimiter=delimiter,
                    compare_columns=compare_columns,
                    cfg=cfg,
                    collector=collector,
                    merge_window=window,
                )
                report = collector.finish()
                report = _persist_mismatch_artifact_outside_workspace(workspace, cfg, report)
                return report, src_rows, tgt_rows, resolved

            if strategy == ReconciliationStrategy.ORDERED_STREAM:
                if not cfg.assume_sorted:
                    logger.warning(
                        "ORDERED_STREAM without assume_sorted=True relies on physically sorted CSV rows; "
                        "ensure inputs are globally sorted by UID."
                    )
                src_rows, tgt_rows = merge_sorted_csv_streams(
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid_column,
                    compare_columns=compare_columns,
                    delimiter=delimiter,
                    reader=self._reader,
                    collector=collector,
                    batch_rows=cfg.chunk_rows,
                    metrics=self._metrics,
                )
                report = collector.finish()
                report = _persist_mismatch_artifact_outside_workspace(workspace, cfg, report)
                return report, src_rows, tgt_rows, ReconciliationStrategy.ORDERED_STREAM

            if strategy == ReconciliationStrategy.GNU_SORT:
                src_rows, tgt_rows = self._run_gnu_sort(
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid_column,
                    compare_columns=compare_columns,
                    cfg=cfg,
                    collector=collector,
                )
                report = collector.finish()
                report = _persist_mismatch_artifact_outside_workspace(workspace, cfg, report)
                return report, src_rows, tgt_rows, ReconciliationStrategy.GNU_SORT

        raise ReconciliationStrategyError(f"Unsupported strategy: {strategy!r}")

    def _run_external_sort_then_merge(
        self,
        *,
        workspace: Path,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
        collector: MismatchSink,
        merge_window: int,
    ) -> tuple[int, int, ReconciliationStrategy]:
        sort_engine = ExternalMergeSortEngine(self._reader, metrics=self._metrics)
        src_sorted = sort_engine.materialize_sorted_parquet(
            source_path,
            workspace=workspace,
            side="source",
            uid_column=uid_column,
            delimiter=delimiter,
            chunk_rows=cfg.chunk_rows,
        )
        tgt_sorted = sort_engine.materialize_sorted_parquet(
            target_path,
            workspace=workspace,
            side="target",
            uid_column=uid_column,
            delimiter=delimiter,
            chunk_rows=cfg.chunk_rows,
        )
        src_rows, tgt_rows = merge_sorted_parquet_streams(
            source_path=src_sorted,
            target_path=tgt_sorted,
            uid_column=uid_column,
            compare_columns=compare_columns,
            collector=collector,
            batch_rows=cfg.chunk_rows,
            window=merge_window,
            metrics=self._metrics,
        )
        resolved = ReconciliationStrategy.SLIDING_WINDOW if merge_window > 0 else ReconciliationStrategy.EXTERNAL_SORT
        return src_rows, tgt_rows, resolved

    def _run_hash_partition(
        self,
        *,
        workspace: Path,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
        collector: MismatchSink,
    ) -> tuple[int, int]:
        combined = source_path.stat().st_size + target_path.stat().st_size
        ensure_disk_headroom(
            workspace,
            int(combined * cfg.disk_headroom_multiplier),
            label="hash-partition spill/sort",
        )

        def _spill_side(side: str, csv_path: Path, reader: PolarsCSVReader) -> int:
            pm = PartitionManager(
                workspace=workspace,
                buckets=cfg.partition_buckets,
                reader=reader,
                metrics=self._metrics,
                sub_partition_buckets=cfg.sub_partition_buckets,
            )
            return pm.spill_csv(
                csv_path,
                side=side,
                uid_column=uid_column,
                delimiter=delimiter,
                chunk_rows=cfg.chunk_rows,
            )

        if cfg.parallel_spill_sides:
            batch = cfg.chunk_rows
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_src = pool.submit(
                    _spill_side,
                    "source",
                    source_path,
                    PolarsCSVReader(default_batch_size=batch),
                )
                fut_tgt = pool.submit(
                    _spill_side,
                    "target",
                    target_path,
                    PolarsCSVReader(default_batch_size=batch),
                )
                src_rows = fut_src.result()
                tgt_rows = fut_tgt.result()
        else:
            src_rows = _spill_side("source", source_path, self._reader)
            tgt_rows = _spill_side("target", target_path, self._reader)

        _compare_spilled_hash_partitions(
            workspace=workspace,
            cfg=cfg,
            uid_column=uid_column,
            compare_columns=compare_columns,
            collector=collector,
            metrics=self._metrics,
        )

        return src_rows, tgt_rows

    def _run_gnu_sort(
        self,
        *,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
        collector: MismatchSink,
    ) -> tuple[int, int]:
        """High-performance comparison using system `sort` and `comm` utilities."""
        if os.name == "nt":
            raise ReconciliationStrategyError("GNU_SORT strategy is only supported on Unix/macOS.")

        with temp_reconciliation_workspace(cfg.temp_dir) as workspace:
            src_sorted = workspace / "source_sorted.csv"
            tgt_sorted = workspace / "target_sorted.csv"
            
            # 1. Parallel Sort using system sort
            # -S 25% of RAM, --parallel=4
            sort_cmd = ["sort", "--parallel=4", "-S", "25%", "-t", ",", "-k", "1,1", "-o"]
            
            self._metrics.on_phase_start("gnu_sort_parallel", source=str(source_path), target=str(target_path))
            p_src = subprocess.Popen(sort_cmd + [str(src_sorted), str(source_path)])
            p_tgt = subprocess.Popen(sort_cmd + [str(tgt_sorted), str(target_path)])
            
            if p_src.wait() != 0 or p_tgt.wait() != 0:
                raise ReconciliationError("System sort failed. Ensure 'sort' is installed and supports --parallel.")
            self._metrics.on_phase_end("gnu_sort_parallel")

            # 2. Use 'comm' to find missing/extra/both
            # -1: suppress lines unique to file1, -2: unique to file2, -3: unique to both
            self._metrics.on_phase_start("gnu_comm_mismatches")
            
            # Find missing in target (unique to source)
            # Find extra in target (unique to target)
            # Find common rows (then we must check columns)
            # Actually, comm is better for finding missing/extra.
            
            # For simplicity in this implementation, we use Polars to read the sorted files
            # and perform the merge-join vectorized, as it's nearly as fast as comm but easier to handle columns.
            src_rows, tgt_rows = merge_sorted_csv_streams(
                source_path=src_sorted,
                target_path=tgt_sorted,
                uid_column=uid_column,
                compare_columns=compare_columns,
                delimiter=",",
                reader=self._reader,
                collector=collector,
                batch_rows=cfg.chunk_rows,
                metrics=self._metrics,
            )
            self._metrics.on_phase_end("gnu_comm_mismatches")
            
            return src_rows, tgt_rows


def auto_external_enabled(
    *,
    source_path: Path,
    target_path: Path,
    cfg: ReconciliationRuntimeConfig,
) -> bool:
    """Return True when AUTO mode should spill (combined byte size above threshold)."""
    if cfg.strategy != ReconciliationStrategy.AUTO:
        return False
    if cfg.force_external:
        return True
    total = source_path.stat().st_size + target_path.stat().st_size
    return total > cfg.external_memory_threshold_bytes

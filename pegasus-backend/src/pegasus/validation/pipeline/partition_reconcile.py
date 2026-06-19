# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-19T09:47:48Z
# --- END GENERATED FILE METADATA ---

"""Vectorized per-partition reconciliation from columnar spill files."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from pegasus.validation.comparators.policy import active_compare_policy
from pegasus.validation.pipeline.arrow_spill import partition_has_arrow, read_arrow_partition
from pegasus.validation.pipeline.fingerprint import canonical
from pegasus.validation.pipeline.result import ColumnDifference, MismatchSample
from pegasus.validation.pipeline.spill import iter_partition
from pegasus.validation.pipeline.timing import PipelineTimings, StageTimer

if TYPE_CHECKING:
    from pegasus.validation.pipeline.live_progress import LiveProgressTracker

if TYPE_CHECKING:
    from pegasus.validation.pipeline.drilldown_cache import DrilldownCache


@dataclass(slots=True)
class PartitionReconcileResult:
    missing: int
    extra: int
    changed: int
    matching: int
    missing_keys: list[str]
    extra_keys: list[str]
    changed_keys: list[str]


def _column_values_match(
    col: str,
    source: object,
    target: object,
    *,
    source_record: dict[str, object] | None = None,
    target_record: dict[str, object] | None = None,
) -> bool:
    pol = active_compare_policy()
    if pol is not None and pol.fields and source_record is not None and target_record is not None:
        fm = pol.field_for(col)
        if fm is not None and not any(c in source_record for c in fm.source_columns):
            return str(source_record.get(col, "")) == str(target_record.get(col, ""))
        return pol.values_equal_mapped(col, source_record, target_record)
    if pol is not None:
        return pol.values_equal(col, source, target)
    return canonical(source, column=col) == canonical(target, column=col)


def _frame_from_legacy(
    path: Path,
    *,
    compare_columns: list[str] | None,
    with_payload: bool,
) -> pl.DataFrame | None:
    keys: list[str] = []
    fps: list[bytes] = []
    for key, fp, _payload in iter_partition(
        path, compare_columns=compare_columns if with_payload else None
    ):
        keys.append(key)
        fps.append(fp)
    if not keys:
        return None
    fp_ints = [int.from_bytes(fp[:8].ljust(8, b"\x00"), "big") for fp in fps]
    return pl.DataFrame({"identity": keys, "fingerprint": fp_ints})


def load_partition_frame(
    path: Path,
    *,
    compare_columns: list[str] | None = None,
    with_payload: bool = False,
) -> pl.DataFrame | None:
    if partition_has_arrow(path):
        return read_arrow_partition(path)
    return _frame_from_legacy(path, compare_columns=compare_columns, with_payload=with_payload)


def reconcile_partition_core(
    src_path: Path,
    tgt_path: Path,
    *,
    sample_limit: int,
) -> PartitionReconcileResult:
    """Fingerprint compare only — safe for process pool workers."""
    src = load_partition_frame(src_path)
    tgt = load_partition_frame(tgt_path)

    if src is None and tgt is None:
        return PartitionReconcileResult(0, 0, 0, 0, [], [], [])
    if src is None:
        src = pl.DataFrame(schema={"identity": pl.Utf8, "fingerprint": pl.UInt64})
    if tgt is None:
        tgt = pl.DataFrame(schema={"identity": pl.Utf8, "fingerprint": pl.UInt64})

    src = src.rename({"identity": "_key", "fingerprint": "_fp"}).with_columns(
        pl.col("_fp").cast(pl.UInt64)
    )
    tgt = tgt.rename({"identity": "_key", "fingerprint": "_fp_tgt"}).with_columns(
        pl.col("_fp_tgt").cast(pl.UInt64)
    )

    extra_df = tgt.join(src.select("_key"), on="_key", how="anti")
    missing_df = src.join(tgt.select("_key"), on="_key", how="anti")
    inner = src.join(tgt, on="_key", how="inner")
    changed_df = inner.filter(pl.col("_fp") != pl.col("_fp_tgt"))
    matching = inner.height - changed_df.height

    cap = max(0, sample_limit)
    return PartitionReconcileResult(
        missing=missing_df.height,
        extra=extra_df.height,
        changed=changed_df.height,
        matching=matching,
        missing_keys=[str(k) for k in missing_df["_key"].head(cap).to_list()],
        extra_keys=[str(k) for k in extra_df["_key"].head(cap).to_list()],
        changed_keys=[str(k) for k in changed_df["_key"].head(cap).to_list()],
    )


def _apply_drilldown_samples(
    *,
    changed_keys: list[str],
    src_path: Path,
    tgt_path: Path,
    compare_columns: list[str],
    drilldown_cache: DrilldownCache | None,
    use_spill_payload: bool,
    samples: list[MismatchSample],
    sample_limit: int,
    timings: PipelineTimings,
) -> None:
    if not changed_keys or len(samples) >= sample_limit:
        return
    take = min(sample_limit - len(samples), len(changed_keys))
    keys = changed_keys[:take]
    if drilldown_cache is not None:
        src_lookup = drilldown_cache.values_for_keys("source", keys)
        tgt_lookup = drilldown_cache.values_for_keys("target", keys)
        with StageTimer(timings, "column_comparison_seconds"):
            for sk in keys:
                src_data = src_lookup.get(sk, {})
                tgt_data = tgt_lookup.get(sk, {})
                col_diffs = [
                    ColumnDifference(
                        col,
                        src_data.get(col),
                        tgt_data.get(col),
                    )
                    for col in compare_columns
                    if not _column_values_match(
                        col,
                        src_data.get(col),
                        tgt_data.get(col),
                        source_record=src_data,
                        target_record=tgt_data,
                    )
                ]
                samples.append(MismatchSample(sk, "changed", col_diffs))
        return

    if not use_spill_payload:
        return

    key_set = set(keys)
    src_payload: dict[str, dict] = {}
    for key, _fp, payload in iter_partition(src_path, compare_columns=compare_columns):
        if key in key_set and payload:
            src_payload[key] = payload
    with StageTimer(timings, "column_comparison_seconds"):
        tgt_payload: dict[str, dict] = {}
        for key, _fp, payload in iter_partition(tgt_path, compare_columns=compare_columns):
            if key in key_set:
                tgt_payload[key] = payload or {}
        for sk in keys:
            src_data = src_payload.get(sk, {})
            tgt_data = tgt_payload.get(sk, {})
            col_diffs = [
                ColumnDifference(col, src_data.get(col), tgt_data.get(col))
                for col in compare_columns
                if not _column_values_match(
                    col,
                    src_data.get(col),
                    tgt_data.get(col),
                    source_record=src_data,
                    target_record=tgt_data,
                )
            ]
            samples.append(MismatchSample(sk, "changed", col_diffs))


def reconcile_partition_vectorized(
    src_path: Path,
    tgt_path: Path,
    *,
    compare_columns: list[str],
    enable_drilldown: bool,
    drilldown_cache: DrilldownCache | None,
    sample_limit: int,
    samples: list[MismatchSample],
    timings: PipelineTimings,
    use_spill_payload: bool,
) -> tuple[int, int, int, int]:
    """Return (missing, extra, changed, matching) for one partition."""
    with StageTimer(timings, "disk_read_seconds"):
        with StageTimer(timings, "partition_reconciliation_seconds"):
            core = reconcile_partition_core(src_path, tgt_path, sample_limit=sample_limit)

    for key in core.missing_keys:
        if len(samples) < sample_limit:
            samples.append(MismatchSample(key, "missing"))
    for key in core.extra_keys:
        if len(samples) < sample_limit:
            samples.append(MismatchSample(key, "extra"))

    if enable_drilldown and core.changed_keys:
        _apply_drilldown_samples(
            changed_keys=core.changed_keys,
            src_path=src_path,
            tgt_path=tgt_path,
            compare_columns=compare_columns,
            drilldown_cache=drilldown_cache,
            use_spill_payload=use_spill_payload,
            samples=samples,
            sample_limit=sample_limit,
            timings=timings,
        )

    return core.missing, core.extra, core.changed, core.matching


def _worker_reconcile(args: tuple[str, str, int]) -> PartitionReconcileResult:
    src_s, tgt_s, sample_limit = args
    return reconcile_partition_core(Path(src_s), Path(tgt_s), sample_limit=sample_limit)


def reconcile_partitions_parallel(
    work: Path,
    active_pids: set[int],
    *,
    compare_columns: list[str],
    enable_drilldown: bool,
    drilldown_cache: DrilldownCache | None,
    sample_limit: int,
    samples: list[MismatchSample],
    timings: PipelineTimings,
    use_spill_payload: bool,
    max_workers: int,
    live_progress: LiveProgressTracker | None = None,
    use_processes: bool = True,
) -> tuple[int, int, int, int, int]:
    """Reconcile partitions in a worker pool; drilldown runs in the parent."""
    tasks = [
        (
            str(work / "source" / f"part_{pid:05d}.bin"),
            str(work / "target" / f"part_{pid:05d}.bin"),
            sample_limit,
        )
        for pid in sorted(active_pids)
    ]
    missing = extra = changed = matching = 0
    mismatched_partitions = 0

    with StageTimer(timings, "partition_reconciliation_seconds"):
        done = 0
        pool_kwargs: dict[str, object] = {}
        if use_processes and max_workers > 1 and len(tasks) >= 2:
            pool_cls: type = ProcessPoolExecutor
            pool_kwargs["mp_context"] = mp.get_context("spawn")
        else:
            pool_cls = ThreadPoolExecutor
        with pool_cls(max_workers=max_workers, **pool_kwargs) as pool:
            futures = {pool.submit(_worker_reconcile, t): i for i, t in enumerate(tasks)}
            ordered: list[PartitionReconcileResult | None] = [None] * len(tasks)
            for fut in as_completed(futures):
                ordered[futures[fut]] = fut.result()
                done += 1
                if live_progress is not None:
                    live_progress.on_reconcile_done(partitions_done=done)

    for i, pid in enumerate(sorted(active_pids)):
        core = ordered[i]
        if core is None:
            continue
        src_path = work / "source" / f"part_{pid:05d}.bin"
        tgt_path = work / "target" / f"part_{pid:05d}.bin"
        missing += core.missing
        extra += core.extra
        changed += core.changed
        matching += core.matching
        if core.missing or core.extra or core.changed:
            mismatched_partitions += 1
        for key in core.missing_keys:
            if len(samples) < sample_limit:
                samples.append(MismatchSample(key, "missing"))
        for key in core.extra_keys:
            if len(samples) < sample_limit:
                samples.append(MismatchSample(key, "extra"))
        if enable_drilldown and core.changed_keys:
            _apply_drilldown_samples(
                changed_keys=core.changed_keys,
                src_path=src_path,
                tgt_path=tgt_path,
                compare_columns=compare_columns,
                drilldown_cache=drilldown_cache,
                use_spill_payload=use_spill_payload,
                samples=samples,
                sample_limit=sample_limit,
                timings=timings,
            )

    return missing, extra, changed, matching, mismatched_partitions


def resolved_reconcile_workers(requested: int) -> int:
    """1 = sequential; 0 = auto (cpu-1 capped at 8); N>1 = explicit pool size."""
    if requested == 1:
        return 1
    if requested <= 0:
        cpus = os.cpu_count() or 1
        return max(1, min(8, cpus - 1 if cpus > 1 else 1))
    return max(1, requested)


def should_parallel_reconcile(
    *,
    num_partitions: int,
    workers: int,
    input_bytes: int = 0,
) -> bool:
    """Parallel reconcile when enough active partitions justify pool startup."""
    if workers <= 1:
        return False
    # Large GCS/local spill runs use more partitions — lower the bar.
    if input_bytes >= 512 * 1024 * 1024:
        return num_partitions >= max(8, workers * 2)
    if input_bytes >= 64 * 1024 * 1024:
        return num_partitions >= max(12, workers * 4)
    return num_partitions >= max(16, workers * 8)

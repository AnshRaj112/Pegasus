"""Memory-bounded comparison of one hash partition (sort + merge, spill-to-disk)."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.comparators.exceptions import UIDComparisonError

from .exceptions import ReconciliationError
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics
from .mismatch_collector import MismatchSink
from .ordered_stream import merge_sorted_parquet_streams

logger = logging.getLogger(__name__)


def _scan_many(shard_paths: list[Path]) -> pl.LazyFrame:
    """Build a lazy scan across one or more Parquet shard files."""
    if not shard_paths:
        raise ValueError("shard_paths must be non-empty")
    paths_str = [str(p) for p in shard_paths]
    if len(paths_str) == 1:
        return pl.scan_parquet(paths_str[0])
    return pl.concat([pl.scan_parquet(p) for p in paths_str], how="vertical_relaxed")


def assert_no_duplicate_uids_in_shards(shard_paths: list[Path], *, uid_column: str) -> None:
    """Raise :class:`UIDComparisonError` if any UID appears more than once in the shard set."""
    if not shard_paths:
        return
    lf = _scan_many(shard_paths).select(pl.col(uid_column))
    try:
        dup = (
            lf.group_by(uid_column)
            .len()
            .filter(pl.col("len") > 1)
            .limit(1)
            .collect(engine="streaming")
        )
    except pl_exc.PolarsError as exc:
        logger.exception("Duplicate-UID probe failed")
        raise ReconciliationError("Duplicate UID probe failed while scanning partition shards") from exc
    if dup.height > 0:
        raise UIDComparisonError(
            f"Duplicate uid values in partition for column {uid_column!r} (streaming group-by probe)"
        )


def materialize_sorted_uid_parquet(
    shard_paths: list[Path],
    out_path: Path,
    *,
    uid_column: str,
) -> None:
    """Sort all shards by *uid_column* and write a single Parquet file.

    Prefer :meth:`polars.LazyFrame.sink_parquet` so Polars can spill the sort; fall back
    to ``collect(engine=\"streaming\")`` when ``sink_parquet`` is unavailable.
    """
    if out_path.exists():
        out_path.unlink()
    if not shard_paths:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lf = _scan_many(shard_paths).sort(uid_column)
    try:
        lf.sink_parquet(str(out_path))
    except (AttributeError, TypeError, pl_exc.PolarsError) as exc:
        logger.warning(
            "sink_parquet unavailable or failed (%s); falling back to streaming collect + write_parquet",
            exc,
        )
        try:
            df = lf.collect(engine="streaming")
        except pl_exc.PolarsError:
            df = lf.collect()
        df.write_parquet(out_path)


def emit_one_sided_partition(
    shard_paths: list[Path],
    *,
    uid_column: str,
    side: str,
    collector: MismatchSink,
    batch_rows: int,
    metrics: ReconciliationMetrics | None,
) -> None:
    """Stream all rows from a single side as ``missing`` (source) or ``extra`` (target)."""
    m = metrics or NoOpReconciliationMetrics()
    if not shard_paths:
        return
    it = _scan_many(shard_paths).collect_batches(chunk_size=batch_rows, engine="streaming")
    phase = f"partition_one_side_{side}"
    m.on_phase_start(phase, shards=len(shard_paths))
    rows = 0
    try:
        for batch in it:
            for rec in batch.to_dicts():
                rows += 1
                uid = str(rec[uid_column])
                if side == "source":
                    collector.add_missing(uid=uid, source_record=rec)
                else:
                    collector.add_extra(uid=uid, target_record=rec)
    except pl_exc.PolarsError as exc:
        logger.exception("One-sided partition scan failed")
        raise ReconciliationError("Parquet shard scan failed for one-sided partition") from exc
    m.on_phase_end(phase, rows=rows)


class PartitionComparator:
    """Compare spilled Parquet shards for one hash bucket without a full in-memory join."""

    __slots__ = ("_metrics",)

    def __init__(self, *, metrics: ReconciliationMetrics | None = None) -> None:
        self._metrics = metrics or NoOpReconciliationMetrics()

    def compare_partition_shards(
        self,
        *,
        workspace: Path,
        partition_id: int,
        sub_partition_id: int,
        source_shards: list[Path],
        target_shards: list[Path],
        uid_column: str,
        compare_columns: list[str],
        collector: MismatchSink,
        batch_rows: int,
    ) -> None:
        """Sort-merge one (primary, sub) partition bucket; removes temp sorted Parquet files when done."""
        if not source_shards and not target_shards:
            return

        sort_dir = workspace / "partition_sorted"
        sort_dir.mkdir(parents=True, exist_ok=True)
        src_sorted = sort_dir / f"p{partition_id}_s{sub_partition_id}_source_sorted.parquet"
        tgt_sorted = sort_dir / f"p{partition_id}_s{sub_partition_id}_target_sorted.parquet"
        try:
            if not source_shards:
                emit_one_sided_partition(
                    target_shards,
                    uid_column=uid_column,
                    side="target",
                    collector=collector,
                    batch_rows=batch_rows,
                    metrics=self._metrics,
                )
                return
            if not target_shards:
                emit_one_sided_partition(
                    source_shards,
                    uid_column=uid_column,
                    side="source",
                    collector=collector,
                    batch_rows=batch_rows,
                    metrics=self._metrics,
                )
                return

            assert_no_duplicate_uids_in_shards(source_shards, uid_column=uid_column)
            assert_no_duplicate_uids_in_shards(target_shards, uid_column=uid_column)

            self._metrics.on_phase_start(
                "partition_sort_materialize",
                partition_id=partition_id,
                sub_partition_id=sub_partition_id,
                n_src_shards=len(source_shards),
                n_tgt_shards=len(target_shards),
            )
            materialize_sorted_uid_parquet(source_shards, src_sorted, uid_column=uid_column)
            materialize_sorted_uid_parquet(target_shards, tgt_sorted, uid_column=uid_column)
            self._metrics.on_phase_end(
                "partition_sort_materialize",
                partition_id=partition_id,
                sub_partition_id=sub_partition_id,
            )

            merge_sorted_parquet_streams(
                source_path=src_sorted,
                target_path=tgt_sorted,
                uid_column=uid_column,
                compare_columns=compare_columns,
                collector=collector,
                batch_rows=batch_rows,
                window=0,
                metrics=self._metrics,
            )
        finally:
            for p in (src_sorted, tgt_sorted):
                try:
                    if p.exists():
                        p.unlink()
                except OSError as exc:
                    logger.warning("Could not remove temp sorted file %s: %s", p, exc)

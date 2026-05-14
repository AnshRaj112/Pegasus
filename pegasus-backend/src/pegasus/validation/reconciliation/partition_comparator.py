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
                "partition_vectorized_join",
                partition_id=partition_id,
                sub_partition_id=sub_partition_id,
                n_src_shards=len(source_shards),
                n_tgt_shards=len(target_shards),
            )
            
            # Vectorized Outer Join using Polars
            # Since partitions are small, we can join them in memory for 100x speed vs Python loops.
            src_lf = _scan_many(source_shards)
            tgt_lf = _scan_many(target_shards)
            
            # Perform outer join to find missing, extra, and mismatched rows
            joined = src_lf.join(tgt_lf, on=uid_column, how="outer", suffix="_target")
            
            # 1. Missing in Target (Missing)
            missing = joined.filter(pl.col(f"{uid_column}_target").is_null()).select([
                pl.col(uid_column).cast(pl.String).alias("uid"),
                pl.lit("missing_in_target").alias("mismatch_type"),
                pl.lit(None, dtype=pl.String).alias("column_name"),
                pl.lit(None, dtype=pl.String).alias("source_value"),
                pl.lit(None, dtype=pl.String).alias("target_value"),
                pl.lit("{}", dtype=pl.String).alias("row_detail")
            ])
            
            # 2. Extra in Target (Extra)
            extra = joined.filter(pl.col(uid_column).is_null()).select([
                pl.col(f"{uid_column}_target").cast(pl.String).alias("uid"),
                pl.lit("extra_in_target").alias("mismatch_type"),
                pl.lit(None, dtype=pl.String).alias("column_name"),
                pl.lit(None, dtype=pl.String).alias("source_value"),
                pl.lit(None, dtype=pl.String).alias("target_value"),
                pl.lit("{}", dtype=pl.String).alias("row_detail")
            ])
            
            # 3. Value Mismatch
            both = joined.filter(pl.col(uid_column).is_not_null() & pl.col(f"{uid_column}_target").is_not_null())
            
            # For each column, find differences and melt them into rows
            mismatch_dfs = []
            for col in compare_columns:
                col_mismatch = both.filter(
                    (pl.col(col) != pl.col(f"{col}_target")) | (pl.col(col).is_null() != pl.col(f"{col}_target").is_null())
                ).select([
                    pl.col(uid_column).cast(pl.String).alias("uid"),
                    pl.lit("value_mismatch").alias("mismatch_type"),
                    pl.lit(col).alias("column_name"),
                    pl.col(col).cast(pl.String).alias("source_value"),
                    pl.col(f"{col}_target").cast(pl.String).alias("target_value"),
                    pl.lit("{}", dtype=pl.String).alias("row_detail")
                ])
                mismatch_dfs.append(col_mismatch)

            # Bulk append to collector
            if hasattr(collector, "bulk_append_from_frame"):
                collector.bulk_append_from_frame(missing.collect(engine="streaming"))
                collector.bulk_append_from_frame(extra.collect(engine="streaming"))
                for df in mismatch_dfs:
                    collector.bulk_append_from_frame(df.collect(engine="streaming"))
            else:
                # Fallback for collectors without bulk support
                for rec in missing.collect(engine="streaming").to_dicts():
                    collector.add_missing(uid=str(rec["uid"]), source_record=rec)
                for rec in extra.collect(engine="streaming").to_dicts():
                    collector.add_extra(uid=str(rec["uid"]), target_record=rec)
                for df in mismatch_dfs:
                    for rec in df.collect(engine="streaming").to_dicts():
                        collector.add_value_mismatch(
                            uid=str(rec["uid"]),
                            column_name=str(rec["column_name"]),
                            source_value=rec["source_value"],
                            target_value=rec["target_value"],
                            source_record={},
                            target_record={},
                        )

            self._metrics.on_phase_end(
                "partition_vectorized_join",
                partition_id=partition_id,
                sub_partition_id=sub_partition_id,
            )
        finally:
            for p in (src_sorted, tgt_sorted):
                try:
                    if p.exists():
                        p.unlink()
                except OSError as exc:
                    logger.warning("Could not remove temp sorted file %s: %s", p, exc)

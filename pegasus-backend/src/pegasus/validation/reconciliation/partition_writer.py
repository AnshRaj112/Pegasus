"""Append-only Parquet shard writer for hash partitions (spill-to-disk)."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl
import polars.exceptions as pl_exc

from .exceptions import ReconciliationError

logger = logging.getLogger(__name__)


class PartitionWriter:
    """Write Polars batches under ``workspace/partitions/<side>/p=<id>/`` or ``.../p=<id>/s=<j>/``."""

    __slots__ = ("_workspace", "_side", "_sub_buckets", "_counters", "_shard_total")

    def __init__(self, *, workspace: Path, side: str, sub_partition_buckets: int = 1) -> None:
        if sub_partition_buckets < 1:
            raise ValueError("sub_partition_buckets must be >= 1")
        self._workspace = workspace
        self._side = side
        self._sub_buckets = sub_partition_buckets
        self._counters: dict[tuple[int, int], int] = {}
        self._shard_total = 0

    def write_rows(self, partition_id: int, frame: pl.DataFrame, *, sub_partition_id: int = 0) -> int:
        """Persist *frame* under the hash bucket (and optional sub-bucket); return rows written.

        Raises
        ------
        ReconciliationError
            If Parquet serialization fails.
        """
        if frame.is_empty():
            return 0
        root = self._workspace / "partitions" / self._side
        if self._sub_buckets > 1:
            part_dir = root / f"p={partition_id}" / f"s={sub_partition_id}"
        else:
            part_dir = root / f"p={partition_id}"
        part_dir.mkdir(parents=True, exist_ok=True)
        key = (partition_id, sub_partition_id)
        n = self._counters.get(key, 0)
        shard_path = part_dir / f"shard_{n:06d}.parquet"
        self._counters[key] = n + 1
        try:
            frame.write_parquet(shard_path)
        except pl_exc.PolarsError as exc:
            logger.exception("Failed writing partition shard %s", shard_path)
            raise ReconciliationError(f"Cannot write partition shard: {shard_path}") from exc
        self._shard_total += 1
        rows = frame.height
        logger.debug(
            "Wrote partition shard side=%s pid=%d sub=%d rows=%d path=%s",
            self._side,
            partition_id,
            sub_partition_id,
            rows,
            shard_path.name,
        )
        return rows

    @property
    def shards_written(self) -> int:
        """Total number of shard files created across all buckets."""
        return self._shard_total

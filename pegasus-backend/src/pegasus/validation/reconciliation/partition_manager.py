"""Hash-partition spill and workspace layout for UID-keyed reconciliation."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

import pandas as pd
import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader

from .exceptions import ReconciliationError
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics
from .partition_writer import PartitionWriter
from .uid_partition import add_sha256_partition_column, add_sha256_two_level_partition_columns

logger = logging.getLogger(__name__)


def _write_partitioned_batch(
    parted: pl.DataFrame,
    *,
    writer: PartitionWriter,
    sub_buckets: int,
    side: str,
    metrics: ReconciliationMetrics,
) -> int:
    """Split *parted* by partition columns and append shards; return rows written."""
    rows_out = 0
    if sub_buckets <= 1:
        grouped = parted.partition_by("_pegasus_part", as_dict=True, include_key=False)
        for key, subdf in grouped.items():
            pid = int(key[0])
            rows = writer.write_rows(pid, subdf)
            rows_out += rows
            metrics.on_rows_processed(side, rows, partition_id=pid)
    else:
        grouped = parted.partition_by(["_pegasus_part", "_pegasus_sub"], as_dict=True, include_key=False)
        for key, subdf in grouped.items():
            pid, sub_id = int(key[0]), int(key[1])
            rows = writer.write_rows(pid, subdf, sub_partition_id=sub_id)
            rows_out += rows
            metrics.on_rows_processed(side, rows, partition_id=pid, sub_partition_id=sub_id)
    return rows_out


class PartitionManager:
    """Stream CSV batches, route rows by SHA-256 buckets, and append Parquet shards.

    Uses :meth:`polars.DataFrame.partition_by` so each input batch is split in O(rows)
    instead of scanning every bucket per row.
    """

    __slots__ = ("_buckets", "_sub_buckets", "_workspace", "_reader", "_metrics")

    def __init__(
        self,
        *,
        workspace: Path,
        buckets: int,
        reader: PolarsCSVReader,
        metrics: ReconciliationMetrics | None = None,
        sub_partition_buckets: int = 1,
    ) -> None:
        if buckets < 1:
            raise ValueError("buckets must be >= 1")
        if sub_partition_buckets < 1:
            raise ValueError("sub_partition_buckets must be >= 1")
        self._workspace = workspace
        self._buckets = buckets
        self._sub_buckets = sub_partition_buckets
        self._reader = reader
        self._metrics = metrics or NoOpReconciliationMetrics()

    def spill_csv(
        self,
        csv_path: Path,
        *,
        side: str,
        uid_column: str,
        delimiter: str,
        chunk_rows: int,
    ) -> int:
        """Write partitioned Parquet shards; return total rows written."""
        root = self._workspace / "partitions" / side
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        writer = PartitionWriter(
            workspace=self._workspace,
            side=side,
            sub_partition_buckets=self._sub_buckets,
        )
        read_opts: dict[str, object] = {
            "separator": delimiter,
            "encoding": "utf-8",
            "has_header": True,
        }
        total_rows = 0
        self._metrics.on_phase_start("hash_partition_spill", side=side, path=str(csv_path))
        try:
            for batch in self._reader.iter_batches(csv_path, batch_size=chunk_rows, read_options=read_opts):
                if uid_column not in batch.columns:
                    raise ReconciliationError(f"uid_column {uid_column!r} not in batch columns: {batch.columns}")
                if self._sub_buckets <= 1:
                    parted = add_sha256_partition_column(batch, uid_column, self._buckets)
                else:
                    parted = add_sha256_two_level_partition_columns(
                        batch, uid_column, self._buckets, self._sub_buckets
                    )
                total_rows += _write_partitioned_batch(
                    parted,
                    writer=writer,
                    sub_buckets=self._sub_buckets,
                    side=side,
                    metrics=self._metrics,
                )
        except pl_exc.PolarsError as exc:
            logger.exception("Partition spill failed for %s", csv_path)
            raise ReconciliationError(f"Partition spill failed for {csv_path}") from exc

        self._metrics.on_phase_end("hash_partition_spill", side=side, rows=total_rows)
        logger.info(
            "Partition spill complete side=%s buckets=%d sub_buckets=%d rows=%d shards=%d",
            side,
            self._buckets,
            self._sub_buckets,
            total_rows,
            writer.shards_written,
        )
        return total_rows


HashPartitionSpiller = PartitionManager


def spill_multichar_csv_via_pandas(
    csv_path: Path,
    *,
    workspace: Path,
    side: str,
    uid_column: str,
    delimiter: str,
    buckets: int,
    chunk_rows: int,
    metrics: ReconciliationMetrics | None = None,
    sub_partition_buckets: int = 1,
) -> int:
    """Stream a multi-separator UTF-8 CSV with pandas chunks and spill hash partitions to Parquet."""
    if buckets < 1:
        raise ValueError("buckets must be >= 1")
    if sub_partition_buckets < 1:
        raise ValueError("sub_partition_buckets must be >= 1")
    if len(delimiter) < 2:
        raise ValueError("spill_multichar_csv_via_pandas expects a multi-character delimiter")

    m = metrics or NoOpReconciliationMetrics()
    root = workspace / "partitions" / side
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    writer = PartitionWriter(workspace=workspace, side=side, sub_partition_buckets=sub_partition_buckets)
    sep = re.escape(delimiter)
    total_rows = 0
    chunk = max(1024, chunk_rows)

    m.on_phase_start("multichar_partition_spill", side=side, path=str(csv_path), chunk_rows=chunk)
    try:
        reader = pd.read_csv(
            csv_path,
            sep=sep,
            engine="python",
            encoding="utf-8",
            chunksize=chunk,
        )
        for pdf in reader:
            batch = pl.from_pandas(pdf, include_index=False)
            if uid_column not in batch.columns:
                raise ReconciliationError(f"uid_column {uid_column!r} not in batch columns: {batch.columns}")
            if sub_partition_buckets <= 1:
                parted = add_sha256_partition_column(batch, uid_column, buckets)
            else:
                parted = add_sha256_two_level_partition_columns(batch, uid_column, buckets, sub_partition_buckets)
            total_rows += _write_partitioned_batch(
                parted,
                writer=writer,
                sub_buckets=sub_partition_buckets,
                side=side,
                metrics=m,
            )
    except ReconciliationError:
        raise
    except Exception as exc:
        logger.exception("Multichar partition spill failed for %s", csv_path)
        raise ReconciliationError(f"Multichar partition spill failed for {csv_path}") from exc

    m.on_phase_end("multichar_partition_spill", side=side, rows=total_rows)
    logger.info(
        "Multichar partition spill complete side=%s buckets=%d sub=%d rows=%d",
        side,
        buckets,
        sub_partition_buckets,
        total_rows,
    )
    return total_rows


def multichar_csv_header_frame(csv_path: Path, *, delimiter: str) -> pl.DataFrame:
    """Return a zero-row Polars frame whose schema matches the CSV header (pandas ``nrows=0``)."""
    sep = re.escape(delimiter)
    try:
        pdf = pd.read_csv(csv_path, sep=sep, engine="python", encoding="utf-8", nrows=0)
    except Exception as exc:
        raise ReconciliationError(f"Cannot read CSV header for multichar path: {csv_path}") from exc
    if pdf.columns.empty:
        raise ReconciliationError(f"CSV has no columns: {csv_path}")
    return pl.from_pandas(pdf, include_index=False)

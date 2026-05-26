"""Hash-partition spill and workspace layout for UID-keyed reconciliation."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

import pandas as pd
import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.flat_file import csv_has_data_rows
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
        from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter

        if not polars_supports_csv_delimiter(delimiter):
            return spill_multichar_csv_via_polars(
                csv_path,
                workspace=self._workspace,
                side=side,
                uid_column=uid_column,
                delimiter=delimiter,
                buckets=self._buckets,
                chunk_rows=chunk_rows,
                metrics=self._metrics,
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


def spill_multichar_csv_via_polars(
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
    """Stream and partition a multi-character delimiter CSV using vectorized Polars string ops.

    Instead of per-row Python regex (which causes 10M+ Python calls on large files),
    this replaces the multi-char delimiter with a single rare char (\\x1f) using Polars'
    SIMD-optimized ``str.replace_all``, then splits via ``str.split`` — all in C++.
    """
    m = metrics or NoOpReconciliationMetrics()
    root = workspace / "partitions" / side
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    writer = PartitionWriter(workspace=workspace, side=side, sub_partition_buckets=sub_partition_buckets)
    total_rows = 0

    # A single byte that will never appear in real CSV data
    _UNIT_SEP = "\x1f"

    m.on_phase_start("vectorized_multichar_spill", side=side, path=str(csv_path))

    try:
        # 1. Read the header line to discover column names
        with open(csv_path, "r", encoding="utf-8") as f:
            raw_header = f.readline().rstrip("\n\r")

        from pegasus.validation.flat_file import replace_outside_quotes, split_line

        header_fields = split_line(raw_header, delimiter)
        columns = [c.strip() for c in header_fields]
        n_cols = len(columns)

        if n_cols == 0:
            raise ReconciliationError(f"CSV has no columns after splitting header with delimiter {delimiter!r}")

        logger.info(
            "Vectorized multichar spill side=%s delimiter=%r columns=%d path=%s",
            side, delimiter, n_cols, csv_path,
        )

        if not csv_has_data_rows(csv_path):
            m.on_phase_end("vectorized_multichar_spill", side=side, rows=0)
            logger.info(
                "Vectorized multichar spill complete (header-only) side=%s buckets=%d sub=%d rows=0",
                side,
                buckets,
                sub_partition_buckets,
            )
            return 0

        # 2. Iterate batches — read raw lines (1 column per row) using a dummy separator
        reader = PolarsCSVReader(default_batch_size=chunk_rows)
        read_opts = {"separator": _UNIT_SEP, "has_header": False, "skip_rows": 1}

        for batch in reader.iter_batches(csv_path, batch_size=chunk_rows, read_options=read_opts):
            # batch has 1 column containing the whole line
            line_col = batch.columns[0]

            # ---- Vectorized split (no Python loops) ----
            # Step A: replace multi-char delimiter → single char, entirely in Polars C++
            replaced = batch.select(
                pl.col(line_col).map_elements(
                    lambda line: replace_outside_quotes(line, delimiter, _UNIT_SEP),
                    return_dtype=pl.String,
                )
            )

            # Step B: split by the single char → produces a list column
            split_series = replaced.select(
                pl.col(line_col).str.split(_UNIT_SEP)
            ).to_series()

            # Step C: convert list-of-lists → DataFrame with named columns
            # `to_struct` names fields as field_0, field_1, …; we rename afterwards
            struct_series = split_series.list.to_struct(
                n_field_strategy="max_width",
            )
            split_df = struct_series.struct.unnest()

            # Trim or pad to expected number of columns
            actual_cols = split_df.columns
            if len(actual_cols) > n_cols:
                split_df = split_df.select(actual_cols[:n_cols])
            elif len(actual_cols) < n_cols:
                for i in range(len(actual_cols), n_cols):
                    split_df = split_df.with_columns(pl.lit("").alias(f"field_{i}"))

            # Rename to the real column names
            split_df.columns = columns

            # Ensure all columns are String type
            split_df = split_df.with_columns([
                pl.col(col).cast(pl.String) for col in split_df.columns
            ])

            # Now proceed with normal partitioning
            if uid_column not in split_df.columns:
                raise ReconciliationError(f"uid_column {uid_column!r} not in columns: {split_df.columns}")

            if sub_partition_buckets <= 1:
                parted = add_sha256_partition_column(split_df, uid_column, buckets)
            else:
                parted = add_sha256_two_level_partition_columns(split_df, uid_column, buckets, sub_partition_buckets)

            total_rows += _write_partitioned_batch(
                parted,
                writer=writer,
                sub_buckets=sub_partition_buckets,
                side=side,
                metrics=m,
            )

    except Exception as exc:
        logger.exception("Vectorized multichar partition spill failed for %s", csv_path)
        raise ReconciliationError(f"Vectorized multichar partition spill failed: {exc}") from exc

    m.on_phase_end("vectorized_multichar_spill", side=side, rows=total_rows)
    logger.info(
        "Vectorized multichar spill complete side=%s buckets=%d sub=%d rows=%d",
        side, buckets, sub_partition_buckets, total_rows,
    )
    return total_rows


def multichar_csv_header_frame(csv_path: Path, *, delimiter: str) -> pl.DataFrame:
    """Return a zero-row Polars frame whose schema matches the CSV header (pandas ``nrows=0``)."""
    sep = re.escape(delimiter)
    try:
        pdf = pd.read_csv(
            csv_path,
            sep=sep,
            engine="python",
            encoding="utf-8",
            nrows=0,
            quotechar='"',
            doublequote=True,
        )
    except Exception as exc:
        raise ReconciliationError(f"Cannot read CSV header for multichar path: {csv_path}") from exc
    if pdf.columns.empty:
        raise ReconciliationError(f"CSV has no columns: {csv_path}")
    frame = pl.from_pandas(pdf, include_index=False)
    rename_map = {col: col.strip() for col in frame.columns if col != col.strip()}
    if rename_map:
        frame = frame.rename(rename_map)
    return frame

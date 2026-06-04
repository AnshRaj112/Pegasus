# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:06:25+05:30
# --- END GENERATED FILE METADATA ---

"""Vectorized Polars spill path for delimited files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from pegasus.validation.pipeline.fingerprint import canonical
from pegasus.validation.pipeline.spill import PartitionWriter, encode_compare_payload, encode_record
from pegasus.validation.pipeline.timing import PipelineTimings, StageTimer
from pegasus.validation.readers.pyarrow_io import pyarrow_supports_delimiter, read_csv_table, table_to_polars

if TYPE_CHECKING:
    from pegasus.validation.adapters.base import TabularSourceAdapter
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter


def _canonical_expr(column: str) -> pl.Expr:
    c = pl.col(column).cast(pl.Utf8).str.strip_chars()
    lower = c.str.to_lowercase()
    return (
        pl.when(c.is_null() | (c.str.len_chars() == 0))
        .then(pl.lit("__NULL__"))
        .when(lower.is_in(["null", "none", "na", "n/a"]))
        .then(pl.lit("__NULL__"))
        .otherwise(c)
    )


def _identity_expr(columns: list[str]) -> pl.Expr:
    parts = [_canonical_expr(c) for c in columns]
    return pl.concat_str(parts, separator="|").alias("_identity")


def _fingerprint_expr(columns: list[str]) -> pl.Expr:
    parts = [_canonical_expr(c) for c in columns]
    if not parts:
        return pl.lit(0, dtype=pl.UInt64).alias("_fp_hash")
    joined = pl.concat_str(parts, separator="\x1f")
    return joined.hash(seed=0, seed_1=1, seed_2=2, seed_3=3).alias("_fp_hash")


def _partition_expr(num_partitions: int) -> pl.Expr:
    return (pl.col("_identity").hash(seed=0) % num_partitions).alias("_pid")


def _fp_hash_to_bytes(value: int) -> bytes:
    return int(value).to_bytes(8, "big", signed=False)


def _load_frame(adapter: TabularSourceAdapter) -> pl.DataFrame | None:
    from pegasus.validation.pipeline.in_memory import _load_frame as load_in_memory

    return load_in_memory(adapter)


def can_use_polars_spill(adapter: object) -> bool:
    adapter_type = type(adapter).__name__
    if adapter_type == "GcsDelimitedAdapter":
        if getattr(adapter, "cached_object_bytes", lambda: None)() is not None:
            delim = getattr(adapter, "_delimiter", "")
            return pyarrow_supports_delimiter(delim)
        return False
    if adapter_type != "FileDelimitedAdapter":
        return False
    delim = getattr(adapter, "_delimiter", "")
    return pyarrow_supports_delimiter(delim)


def _write_frame_partitions(
    frame: pl.DataFrame,
    writer: PartitionWriter,
    *,
    compare_columns: list[str],
    store_payload: bool,
    timings: PipelineTimings,
) -> int:
    if frame.is_empty():
        return 0

    payload_cols = compare_columns if store_payload else []
    select_cols = ["_identity", "_fp_hash", "_pid", *payload_cols]
    subset = frame.select(select_cols)

    with StageTimer(timings, "serialization_seconds"):
        for group in subset.partition_by("_pid", maintain_order=True):
            pid = int(group["_pid"][0])
            batch = bytearray()
            identities = group["_identity"].to_list()
            hashes = group["_fp_hash"].to_list()
            if store_payload and payload_cols:
                col_lists = {c: group[c].to_list() for c in payload_cols}
                n = len(identities)
                for i in range(n):
                    payload = {c: col_lists[c][i] for c in payload_cols}
                    payload_b = encode_compare_payload(payload_cols, payload)
                    batch.extend(
                        encode_record(identities[i], _fp_hash_to_bytes(hashes[i]), payload=payload_b)
                    )
            else:
                for identity, fp_hash in zip(identities, hashes, strict=True):
                    batch.extend(encode_record(identity, _fp_hash_to_bytes(fp_hash)))
            writer.write_bytes(pid, batch)
    return frame.height


def partition_side_polars(
    adapter: FileDelimitedAdapter,
    writer: PartitionWriter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    store_payload: bool,
    timings: PipelineTimings,
    is_source: bool,
) -> int:
    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"

    with StageTimer(timings, part_field):
        with StageTimer(timings, read_field):
            frame = table_to_polars(
                read_csv_table(
                    adapter.path,
                    delimiter=adapter._delimiter,
                    has_header=adapter._has_header,
                    skip_rows=adapter._skip_rows,
                )
            )
        frame = frame.with_columns([
            _identity_expr(identity_columns),
            _fingerprint_expr(compare_columns),
        ]).with_columns(_partition_expr(num_partitions))
        return _write_frame_partitions(
            frame,
            writer,
            compare_columns=compare_columns,
            store_payload=store_payload,
            timings=timings,
        )


def try_partition_side_polars(
    adapter: TabularSourceAdapter,
    writer: PartitionWriter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    store_payload: bool,
    timings: PipelineTimings,
    is_source: bool,
) -> int | None:
    """Load via in-memory frame loader (supports multi-char delimiters) and spill vectorized."""
    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"

    try:
        with StageTimer(timings, part_field):
            with StageTimer(timings, read_field):
                frame = _load_frame(adapter)
            if frame is None or frame.is_empty():
                return None
            frame = frame.with_columns([
                _identity_expr(identity_columns),
                _fingerprint_expr(compare_columns),
            ]).with_columns(_partition_expr(num_partitions))
            return _write_frame_partitions(
                frame,
                writer,
                compare_columns=compare_columns,
                store_payload=store_payload,
                timings=timings,
            )
    except Exception:
        return None

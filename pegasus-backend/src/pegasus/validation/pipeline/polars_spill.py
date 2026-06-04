# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T13:07:37+05:30
# --- END GENERATED FILE METADATA ---

"""Vectorized Polars spill path for delimited files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from pegasus.validation.pipeline.fingerprint import canonical
from pegasus.validation.pipeline.drilldown_cache import DrilldownCache
from pegasus.validation.pipeline.spill import PartitionWriter, encode_columnar_partition
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
    drilldown_cache: DrilldownCache | None = None,
    cache_side: str | None = None,
    lazy_drilldown: bool = False,
    use_columnar_spill: bool = True,
) -> int:
    if frame.is_empty():
        return 0

    if lazy_drilldown and drilldown_cache is not None and cache_side:
        drilldown_cache.register_side(cache_side, frame)

    embed_payload = store_payload and not lazy_drilldown
    payload_cols = compare_columns if embed_payload else []
    select_cols = ["_identity", "_fp_hash", "_pid", *payload_cols]
    subset = frame.select(select_cols)

    buckets: dict[int, dict[str, Any]] = {}
    for group in subset.partition_by("_pid", maintain_order=True):
        pid = int(group["_pid"][0])
        bucket = buckets.setdefault(
            pid,
            {
                "identities": [],
                "hashes": [],
                "col_lists": [[] for _ in payload_cols] if payload_cols else None,
            },
        )
        bucket["identities"].extend(group["_identity"].to_list())
        bucket["hashes"].extend(group["_fp_hash"].to_list())
        if payload_cols:
            for idx, col in enumerate(payload_cols):
                bucket["col_lists"][idx].extend(group[col].to_list())

    with StageTimer(timings, "serialization_seconds"):
        for pid, bucket in buckets.items():
            identities = bucket["identities"]
            hashes = bucket["hashes"]
            col_lists = bucket["col_lists"]
            if use_columnar_spill:
                batch = encode_columnar_partition(identities, hashes, col_lists=col_lists)
                writer.write_bytes(pid, batch)
                continue

            from pegasus.validation.pipeline.spill import encode_record, encode_compare_payload_values

            batch = bytearray()
            if col_lists:
                n = len(identities)
                for i in range(n):
                    values = [col_lists[j][i] for j in range(len(payload_cols))]
                    payload_b = encode_compare_payload_values(payload_cols, values)
                    batch.extend(
                        encode_record(identities[i], _fp_hash_to_bytes(hashes[i]), payload=payload_b)
                    )
            else:
                for identity, fp_hash in zip(identities, hashes, strict=True):
                    batch.extend(encode_record(identity, _fp_hash_to_bytes(fp_hash)))
            writer.write_bytes(pid, bytes(batch))
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
    drilldown_cache: DrilldownCache | None = None,
    lazy_drilldown: bool = False,
    use_columnar_spill: bool = True,
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
        canon_cols = compare_columns if (store_payload or lazy_drilldown) else []
        frame = frame.with_columns([
            _identity_expr(identity_columns),
            _fingerprint_expr(compare_columns),
            *([_canonical_expr(c).alias(c) for c in canon_cols]),
        ]).with_columns(_partition_expr(num_partitions))
        return _write_frame_partitions(
            frame,
            writer,
            compare_columns=compare_columns,
            store_payload=store_payload,
            timings=timings,
            drilldown_cache=drilldown_cache,
            cache_side="source" if is_source else "target",
            lazy_drilldown=lazy_drilldown,
            use_columnar_spill=use_columnar_spill,
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
    drilldown_cache: DrilldownCache | None = None,
    lazy_drilldown: bool = False,
    use_columnar_spill: bool = True,
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
            canon_cols = compare_columns if (store_payload or lazy_drilldown) else []
            frame = frame.with_columns([
                _identity_expr(identity_columns),
                _fingerprint_expr(compare_columns),
                *([_canonical_expr(c).alias(c) for c in canon_cols]),
            ]).with_columns(_partition_expr(num_partitions))
            return _write_frame_partitions(
                frame,
                writer,
                compare_columns=compare_columns,
                store_payload=store_payload,
                timings=timings,
                drilldown_cache=drilldown_cache,
                cache_side="source" if is_source else "target",
                lazy_drilldown=lazy_drilldown,
                use_columnar_spill=use_columnar_spill,
            )
    except Exception:
        return None

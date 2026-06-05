# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T15:00:33+05:30
# --- END GENERATED FILE METADATA ---

"""Vectorized Polars spill path for delimited files."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from pegasus.validation.pipeline.fingerprint import canonical
from pegasus.validation.pipeline.drilldown_cache import DrilldownCache
from pegasus.validation.pipeline.partition_merkle import PartitionMerkleAccumulator
from pegasus.validation.pipeline.arrow_spill import encode_arrow_partition, encode_arrow_partition_series
from pegasus.validation.pipeline.spill import PartitionWriter, encode_columnar_partition
from pegasus.validation.pipeline.timing import PipelineTimings, StageTimer
from pegasus.validation.readers.pyarrow_io import (
    iter_csv_batches,
    pyarrow_supports_delimiter,
    read_csv_binary,
    read_csv_table,
    table_to_polars,
)

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
        delim = getattr(adapter, "_delimiter", "")
        return pyarrow_supports_delimiter(delim)
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
    use_arrow_ipc_spill: bool = True,
    merkle: PartitionMerkleAccumulator | None = None,
) -> int:
    if frame.is_empty():
        return 0

    if lazy_drilldown and drilldown_cache is not None and cache_side:
        drilldown_cache.register_side(cache_side, frame)

    return _spill_partition_groups(
        frame,
        writer,
        compare_columns=compare_columns,
        store_payload=store_payload,
        timings=timings,
        drilldown_cache=drilldown_cache,
        cache_side=cache_side,
        lazy_drilldown=lazy_drilldown,
        use_columnar_spill=use_columnar_spill,
        use_arrow_ipc_spill=use_arrow_ipc_spill,
        merkle=merkle,
    )


def _spill_partition_groups(
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
    use_arrow_ipc_spill: bool = True,
    merkle: PartitionMerkleAccumulator | None = None,
) -> int:
    embed_payload = store_payload and not lazy_drilldown
    payload_cols = compare_columns if embed_payload else []
    select_cols = ["_identity", "_fp_hash", "_pid", *payload_cols]
    subset = frame.select(select_cols)

    with StageTimer(timings, "serialization_seconds"):
        grouped = subset.group_by("_pid", maintain_order=True).agg(
            pl.col("_identity"),
            pl.col("_fp_hash"),
            *([pl.col(col) for col in payload_cols]),
        )
        for row in grouped.iter_rows(named=True):
            pid = int(row["_pid"])
            identities = row["_identity"]
            hashes = row["_fp_hash"]
            if merkle is not None:
                merkle.add_group(pid, pl.Series(identities), pl.Series(hashes))
            if use_arrow_ipc_spill and not payload_cols:
                writer.write_bytes(
                    pid,
                    encode_arrow_partition_series(pl.Series(identities), pl.Series(hashes)),
                )
                continue
            col_lists = [row[col] for col in payload_cols] if payload_cols else None
            if use_columnar_spill:
                writer.write_bytes(
                    pid,
                    encode_columnar_partition(
                        list(identities),
                        list(hashes),
                        col_lists=[list(cols) for cols in col_lists] if col_lists else None,
                    ),
                )
                continue
            raise RuntimeError("legacy per-row spill disabled; enable use_arrow_ipc_spill")
    return frame.height


def partition_side_streaming_batches(
    adapter: FileDelimitedAdapter,
    writer: PartitionWriter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    store_payload: bool,
    timings: PipelineTimings,
    chunk_rows: int,
    is_source: bool,
    drilldown_cache: DrilldownCache | None = None,
    lazy_drilldown: bool = False,
    use_columnar_spill: bool = True,
    use_arrow_ipc_spill: bool = True,
    merkle: PartitionMerkleAccumulator | None = None,
) -> int:
    """PyArrow RecordBatch streaming — bounded RAM for large local files."""
    import pyarrow as pa

    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"
    project_cols = list(dict.fromkeys([*identity_columns, *compare_columns]))
    canon_cols = compare_columns if (store_payload or lazy_drilldown) else []
    cache_side = "source" if is_source else "target"
    drilldown_parts: list[pl.DataFrame] = []
    total = 0

    with StageTimer(timings, part_field):
        with StageTimer(timings, read_field):
            batches = iter_csv_batches(
                adapter.path,
                delimiter=adapter._delimiter,
                chunk_rows=chunk_rows,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
                include_columns=project_cols,
            )
        for batch in batches:
            if batch.num_rows == 0:
                continue
            frame = table_to_polars(pa.Table.from_batches([batch]))
            frame = frame.with_columns([
                _identity_expr(identity_columns),
                _fingerprint_expr(compare_columns),
                *([_canonical_expr(c).alias(c) for c in canon_cols]),
            ]).with_columns(_partition_expr(num_partitions))
            if lazy_drilldown and drilldown_cache is not None:
                drilldown_parts.append(frame.select(["_identity", *canon_cols]))
            total += _spill_partition_groups(
                frame,
                writer,
                compare_columns=compare_columns,
                store_payload=store_payload,
                timings=timings,
                lazy_drilldown=False,
                use_columnar_spill=use_columnar_spill,
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )

    if lazy_drilldown and drilldown_cache is not None and drilldown_parts:
        drilldown_cache.register_side(cache_side, pl.concat(drilldown_parts, how="vertical"))

    return total


def _iter_multichar_batches_for_adapter(
    adapter: TabularSourceAdapter,
    *,
    chunk_rows: int,
) -> Iterator[pl.DataFrame]:
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
    from pegasus.validation.readers.multichar_csv import iter_multichar_csv_batches

    if isinstance(adapter, FileDelimitedAdapter):
        yield from iter_multichar_csv_batches(
            adapter.path,
            delimiter=adapter._delimiter,
            has_header=adapter._has_header,
            skip_rows=adapter._skip_rows,
            chunk_rows=chunk_rows,
        )
        return
    if isinstance(adapter, GcsDelimitedAdapter):
        with adapter._stream_session().open_binary(read_ahead=True) as handle:
            yield from iter_multichar_csv_batches(
                handle,
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
                chunk_rows=chunk_rows,
            )
        return
    raise TypeError(f"unsupported adapter for multichar batches: {type(adapter).__name__}")


def partition_side_multichar_batches(
    adapter: TabularSourceAdapter,
    writer: PartitionWriter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    store_payload: bool,
    timings: PipelineTimings,
    chunk_rows: int,
    is_source: bool,
    drilldown_cache: DrilldownCache | None = None,
    lazy_drilldown: bool = False,
    use_columnar_spill: bool = True,
    use_arrow_ipc_spill: bool = True,
    merkle: PartitionMerkleAccumulator | None = None,
) -> int:
    """Batched multichar line reader → native inline spill or Polars fallback."""
    from pegasus.validation.pipeline.native_spill import (
        can_use_native_multichar_spill,
        partition_side_native_multichar,
    )

    if can_use_native_multichar_spill(
        store_payload=store_payload,
        lazy_drilldown=lazy_drilldown,
        use_arrow_ipc_spill=use_arrow_ipc_spill,
    ):
        return partition_side_native_multichar(
            adapter,
            writer,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            num_partitions=num_partitions,
            timings=timings,
            chunk_rows=chunk_rows,
            is_source=is_source,
            merkle=merkle,
        )

    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"
    canon_cols = compare_columns if (store_payload or lazy_drilldown) else []
    total = 0

    with StageTimer(timings, part_field):
        with StageTimer(timings, read_field):
            batches = _iter_multichar_batches_for_adapter(adapter, chunk_rows=chunk_rows)
        for frame in batches:
            if frame.is_empty():
                continue
            _validate_frame_columns(
                frame,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                adapter=adapter,
            )
            frame = frame.with_columns([
                _identity_expr(identity_columns),
                _fingerprint_expr(compare_columns),
                *([_canonical_expr(c).alias(c) for c in canon_cols]),
            ]).with_columns(_partition_expr(num_partitions))
            total += _spill_partition_groups(
                frame,
                writer,
                compare_columns=compare_columns,
                store_payload=store_payload,
                timings=timings,
                lazy_drilldown=False,
                use_columnar_spill=use_columnar_spill,
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )
    return total


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
    use_arrow_ipc_spill: bool = True,
) -> int:
    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"

    with StageTimer(timings, part_field):
        with StageTimer(timings, read_field):
            project_cols = list(dict.fromkeys([*identity_columns, *compare_columns]))
            frame = table_to_polars(
                read_csv_table(
                    adapter.path,
                    delimiter=adapter._delimiter,
                    has_header=adapter._has_header,
                    skip_rows=adapter._skip_rows,
                    include_columns=project_cols,
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
            use_arrow_ipc_spill=use_arrow_ipc_spill,
        )


def _validate_frame_columns(
    frame: pl.DataFrame,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    adapter: TabularSourceAdapter,
) -> None:
    missing = [
        c
        for c in (*identity_columns, *compare_columns)
        if c not in frame.columns
    ]
    if missing:
        delim = getattr(adapter, "_delimiter", "?")
        raise ValueError(
            f"Column(s) {missing} not found in input (delimiter={delim!r}); "
            f"headers={list(frame.columns)}. Use delimiter '||' for generated-100k fixtures."
        )


def _load_gcs_frame_from_session_cache(adapter: TabularSourceAdapter) -> pl.DataFrame | None:
    """Reuse bytes already downloaded for the in-memory fast path (GCS only)."""
    from io import BytesIO

    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
    from pegasus.validation.gcs_stream import get_gcs_stream_session
    from pegasus.validation.readers.multichar_csv import (
        can_use_fast_multichar_load_bytes,
        load_multichar_csv_fast,
    )

    if not isinstance(adapter, GcsDelimitedAdapter):
        return None
    data = get_gcs_stream_session(adapter._ref).cached_object_body()
    if not data:
        return None
    stream = BytesIO(data)
    if pyarrow_supports_delimiter(adapter._delimiter):
        return table_to_polars(
            read_csv_binary(
                stream,
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
            )
        )
    if can_use_fast_multichar_load_bytes(data, adapter._delimiter):
        return load_multichar_csv_fast(
            stream,
            delimiter=adapter._delimiter,
            has_header=adapter._has_header,
            skip_rows=adapter._skip_rows,
        )
    return None


def _partition_cached_gcs_frame(
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
    use_arrow_ipc_spill: bool = True,
    merkle: PartitionMerkleAccumulator | None = None,
) -> int | None:
    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"
    frame = _load_gcs_frame_from_session_cache(adapter)
    if frame is None:
        return None
    canon_cols = compare_columns if (store_payload or lazy_drilldown) else []
    with StageTimer(timings, part_field):
        with StageTimer(timings, read_field):
            _validate_frame_columns(
                frame,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                adapter=adapter,
            )
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
            use_arrow_ipc_spill=use_arrow_ipc_spill,
            merkle=merkle,
        )


def _should_use_streaming_spill(adapter: TabularSourceAdapter, threshold_bytes: int) -> bool:
    adapter_type = type(adapter).__name__
    if adapter_type == "GcsDelimitedAdapter":
        return True
    if adapter_type != "FileDelimitedAdapter":
        return False
    delim = getattr(adapter, "_delimiter", "")
    if not pyarrow_supports_delimiter(delim):
        return True
    if threshold_bytes <= 0:
        return False
    try:
        size = int(adapter.get_size_bytes())
    except OSError:
        return False
    return size >= threshold_bytes or size >= 16 * 1024 * 1024


def partition_side_adapter_stream(
    adapter: TabularSourceAdapter,
    writer: PartitionWriter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    store_payload: bool,
    timings: PipelineTimings,
    chunk_rows: int,
    is_source: bool,
    drilldown_cache: DrilldownCache | None = None,
    lazy_drilldown: bool = False,
    use_columnar_spill: bool = True,
    use_arrow_ipc_spill: bool = True,
    merkle: PartitionMerkleAccumulator | None = None,
) -> int:
    """Chunked stream_records → Polars spill (multi-char delimiters and GCS)."""
    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"
    canon_cols = compare_columns if (store_payload or lazy_drilldown) else []
    cache_side = "source" if is_source else "target"
    drilldown_parts: list[pl.DataFrame] = []
    total = 0

    with StageTimer(timings, part_field):
        with StageTimer(timings, read_field):
            chunks = adapter.stream_records(chunk_rows)
        for chunk in chunks:
            if not chunk:
                continue
            frame = pl.DataFrame(chunk)
            _validate_frame_columns(
                frame,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                adapter=adapter,
            )
            frame = frame.with_columns([
                _identity_expr(identity_columns),
                _fingerprint_expr(compare_columns),
                *([_canonical_expr(c).alias(c) for c in canon_cols]),
            ]).with_columns(_partition_expr(num_partitions))
            if lazy_drilldown and drilldown_cache is not None:
                drilldown_parts.append(frame.select(["_identity", *canon_cols]))
            total += _spill_partition_groups(
                frame,
                writer,
                compare_columns=compare_columns,
                store_payload=store_payload,
                timings=timings,
                lazy_drilldown=False,
                use_columnar_spill=use_columnar_spill,
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )

    if lazy_drilldown and drilldown_cache is not None and drilldown_parts:
        drilldown_cache.register_side(cache_side, pl.concat(drilldown_parts, how="vertical"))

    return total


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
    use_arrow_ipc_spill: bool = True,
    streaming_spill_min_bytes: int = 64 * 1024 * 1024,
    chunk_rows: int = 50_000,
    merkle: PartitionMerkleAccumulator | None = None,
) -> int | None:
    """Spill via streaming batches or a single in-memory frame (PyArrow-friendly delimiters)."""
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
    from pegasus.validation.readers.multichar_csv import (
        can_use_fast_multichar_load,
        can_use_fast_multichar_load_bytes,
    )

    if isinstance(adapter, GcsDelimitedAdapter):
        try:
            cached = _partition_cached_gcs_frame(
                adapter,
                writer,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                num_partitions=num_partitions,
                store_payload=store_payload,
                timings=timings,
                is_source=is_source,
                drilldown_cache=drilldown_cache,
                lazy_drilldown=lazy_drilldown,
                use_columnar_spill=use_columnar_spill,
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )
            if cached is not None:
                return cached
            if not pyarrow_supports_delimiter(adapter._delimiter) and can_use_fast_multichar_load_bytes(
                adapter._load_header_prefix(),
                adapter._delimiter,
            ):
                return partition_side_multichar_batches(
                    adapter,
                    writer,
                    identity_columns=identity_columns,
                    compare_columns=compare_columns,
                    num_partitions=num_partitions,
                    store_payload=store_payload,
                    timings=timings,
                    chunk_rows=chunk_rows,
                    is_source=is_source,
                    drilldown_cache=drilldown_cache,
                    lazy_drilldown=lazy_drilldown,
                    use_columnar_spill=use_columnar_spill,
                    use_arrow_ipc_spill=use_arrow_ipc_spill,
                    merkle=merkle,
                )
            return partition_side_adapter_stream(
                adapter,
                writer,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                num_partitions=num_partitions,
                store_payload=store_payload,
                timings=timings,
                chunk_rows=chunk_rows,
                is_source=is_source,
                drilldown_cache=drilldown_cache,
                lazy_drilldown=lazy_drilldown,
                use_columnar_spill=use_columnar_spill,
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )
        except Exception:
            return None

    if _should_use_streaming_spill(adapter, streaming_spill_min_bytes):
        try:
            cached = _partition_cached_gcs_frame(
                adapter,
                writer,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                num_partitions=num_partitions,
                store_payload=store_payload,
                timings=timings,
                is_source=is_source,
                drilldown_cache=drilldown_cache,
                lazy_drilldown=lazy_drilldown,
                use_columnar_spill=use_columnar_spill,
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )
            if cached is not None:
                return cached
            if (
                not pyarrow_supports_delimiter(getattr(adapter, "_delimiter", ""))
                and (
                    (
                        isinstance(adapter, FileDelimitedAdapter)
                        and can_use_fast_multichar_load(adapter.path, adapter._delimiter)
                    )
                    or (
                        isinstance(adapter, GcsDelimitedAdapter)
                        and can_use_fast_multichar_load_bytes(
                            adapter._load_header_prefix(),
                            adapter._delimiter,
                        )
                    )
                )
            ):
                return partition_side_multichar_batches(
                    adapter,
                    writer,
                    identity_columns=identity_columns,
                    compare_columns=compare_columns,
                    num_partitions=num_partitions,
                    store_payload=store_payload,
                    timings=timings,
                    chunk_rows=chunk_rows,
                    is_source=is_source,
                    drilldown_cache=drilldown_cache,
                    lazy_drilldown=lazy_drilldown,
                    use_columnar_spill=use_columnar_spill,
                    use_arrow_ipc_spill=use_arrow_ipc_spill,
                    merkle=merkle,
                )
            if isinstance(adapter, FileDelimitedAdapter) and pyarrow_supports_delimiter(
                adapter._delimiter
            ):
                return partition_side_streaming_batches(
                    adapter,
                    writer,
                    identity_columns=identity_columns,
                    compare_columns=compare_columns,
                    num_partitions=num_partitions,
                    store_payload=store_payload,
                    timings=timings,
                    chunk_rows=chunk_rows,
                    is_source=is_source,
                    drilldown_cache=drilldown_cache,
                    lazy_drilldown=lazy_drilldown,
                    use_columnar_spill=use_columnar_spill,
                    use_arrow_ipc_spill=use_arrow_ipc_spill,
                    merkle=merkle,
                )
            return partition_side_adapter_stream(
                adapter,
                writer,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                num_partitions=num_partitions,
                store_payload=store_payload,
                timings=timings,
                chunk_rows=chunk_rows,
                is_source=is_source,
                drilldown_cache=drilldown_cache,
                lazy_drilldown=lazy_drilldown,
                use_columnar_spill=use_columnar_spill,
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )
        except Exception:
            pass

    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"

    try:
        with StageTimer(timings, part_field):
            with StageTimer(timings, read_field):
                frame = _load_frame(adapter)
            if frame is None or frame.is_empty():
                return None
            _validate_frame_columns(
                frame,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
                adapter=adapter,
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
                use_arrow_ipc_spill=use_arrow_ipc_spill,
                merkle=merkle,
            )
    except Exception:
        return None

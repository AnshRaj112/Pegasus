# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:29:35Z
# --- END GENERATED FILE METADATA ---

"""Inline hash → partition spill for multichar CSV (Rust splitter, no Polars frames)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pegasus.validation.pipeline.partition_merkle import PartitionMerkleAccumulator
from pegasus.validation.pipeline.spill import PartitionWriter
from pegasus.validation.pipeline.timing import PipelineTimings, StageTimer
from pegasus.validation.readers import native_multichar

if TYPE_CHECKING:
    from pegasus.validation.adapters.base import TabularSourceAdapter

from pegasus.validation.pipeline.drilldown_cache import DRILLDOWN_SUFFIX


def native_drilldown_path(workspace: Path, side: str) -> Path:
    return Path(workspace) / f"drilldown_{side}{DRILLDOWN_SUFFIX}"


def can_use_native_single_char_spill(
    *,
    store_payload: bool,
    use_arrow_ipc_spill: bool,
    delimiter: str,
    file_bytes: int,
    streaming_spill_min_bytes: int,
) -> bool:
    """Prefer Rust native spill for large single-char delimiter files."""
    if file_bytes < streaming_spill_min_bytes:
        return False
    if len(delimiter) != 1:
        return False
    return can_use_native_multichar_spill(
        store_payload=store_payload,
        use_arrow_ipc_spill=use_arrow_ipc_spill,
    )


def can_use_native_multichar_spill(
    *,
    store_payload: bool,
    use_arrow_ipc_spill: bool,
) -> bool:
    from pegasus.validation.comparators.policy import active_compare_policy

    pol = active_compare_policy()
    if pol is not None and (pol.needs_smart_canonical or pol.has_non_trivial_mapping):
        return False
    return (
        native_multichar.native_extension_available()
        and not store_payload
        and use_arrow_ipc_spill
    )


def partition_side_native_multichar(
    adapter: TabularSourceAdapter,
    writer: PartitionWriter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    timings: PipelineTimings,
    chunk_rows: int,
    is_source: bool,
    merkle: PartitionMerkleAccumulator | None = None,
    lazy_drilldown: bool = False,
) -> int:
    """Rust line splitter → inline canonical/hash/partition → direct partition spill."""
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter

    read_field = "source_read_seconds" if is_source else "target_read_seconds"
    part_field = "source_partition_seconds" if is_source else "target_partition_seconds"
    track_merkle = merkle is not None
    side = "source" if is_source else "target"
    workspace = writer.base.parent
    drilldown_path: str | None = None
    if lazy_drilldown:
        drilldown_path = str(native_drilldown_path(workspace, side))

    with StageTimer(timings, part_field):
        with StageTimer(timings, read_field):
            if isinstance(adapter, FileDelimitedAdapter):
                result = native_multichar.spill_mmap_file(
                    adapter.path,
                    writer.base,
                    delimiter=adapter._delimiter,
                    has_header=adapter._has_header,
                    skip_rows=adapter._skip_rows,
                    chunk_rows=chunk_rows,
                    identity_columns=identity_columns,
                    compare_columns=compare_columns,
                    num_partitions=num_partitions,
                    track_merkle=track_merkle,
                    drilldown_path=drilldown_path,
                )
            elif isinstance(adapter, GcsDelimitedAdapter):
                with adapter._stream_session().open_binary(read_ahead=True) as handle:
                    result = native_multichar.spill_stream_file(
                        handle,
                        writer.base,
                        delimiter=adapter._delimiter,
                        has_header=adapter._has_header,
                        skip_rows=adapter._skip_rows,
                        chunk_rows=chunk_rows,
                        identity_columns=identity_columns,
                        compare_columns=compare_columns,
                        num_partitions=num_partitions,
                        track_merkle=track_merkle,
                        drilldown_path=drilldown_path,
                    )
            else:
                raise TypeError(
                    f"unsupported adapter for native multichar spill: {type(adapter).__name__}"
                )
        if merkle is not None:
            merkle.absorb_native_spill(result.get("merkle_xor") or {}, int(result.get("rows", 0)))
    return int(result.get("rows", 0))

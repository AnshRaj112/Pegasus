# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T00:00:00+00:00
# --- END GENERATED FILE METADATA ---

"""GCS objects must always use chunked adapter streaming (never full-object load)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.pipeline.polars_spill import (
    _should_use_streaming_spill,
    try_partition_side_polars,
)
from pegasus.validation.pipeline.spill import PartitionWriter
from pegasus.validation.pipeline.timing import PipelineTimings


def _gcs_adapter(*, size_bytes: int = 1024) -> GcsDelimitedAdapter:
    ref = GcsObjectRef(
        bucket="b",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "p"},
    )
    return GcsDelimitedAdapter(ref, delimiter=",", size_bytes=size_bytes)


def test_gcs_always_uses_streaming_spill() -> None:
    adapter = _gcs_adapter()
    assert _should_use_streaming_spill(adapter, 64 * 1024 * 1024)


def test_gcs_partition_side_never_calls_full_load() -> None:
    adapter = _gcs_adapter(size_bytes=512)
    writer = MagicMock(spec=PartitionWriter)
    timings = PipelineTimings()
    with (
        patch(
            "pegasus.validation.pipeline.polars_spill.partition_side_adapter_stream",
            return_value=42,
        ) as stream_mock,
        patch("pegasus.validation.pipeline.polars_spill._load_frame") as load_mock,
    ):
        result = try_partition_side_polars(
            adapter,
            writer,
            identity_columns=["id"],
            compare_columns=["amount"],
            num_partitions=4,
            store_payload=False,
            timings=timings,
            is_source=True,
            chunk_rows=1000,
        )
    assert result == 42
    stream_mock.assert_called_once()
    load_mock.assert_not_called()

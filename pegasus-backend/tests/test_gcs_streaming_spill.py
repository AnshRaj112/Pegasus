# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T07:10:42Z
# --- END GENERATED FILE METADATA ---

"""GCS objects use PyArrow batch streaming (never full-object load or dict round-trip)."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.pipeline.polars_spill import (
    _should_use_streaming_spill,
    try_partition_side_polars,
)
from pegasus.validation.pipeline.spill import PartitionWriter
from pegasus.validation.pipeline.timing import PipelineTimings
from pegasus.validation.readers.pyarrow_io import iter_csv_batches_stream


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


def test_iter_csv_batches_stream_reads_bytes() -> None:
    payload = b"uid,amount\n10,5\n20,6\n"
    batches = list(
        iter_csv_batches_stream(
            BytesIO(payload),
            delimiter=",",
            chunk_rows=10,
        )
    )
    assert sum(b.num_rows for b in batches) == 2


def test_gcs_partition_side_uses_pyarrow_batches_not_dict_stream() -> None:
    adapter = _gcs_adapter(size_bytes=512)
    writer = MagicMock(spec=PartitionWriter)
    timings = PipelineTimings()
    with (
        patch(
            "pegasus.validation.pipeline.polars_spill.partition_side_streaming_batches",
            return_value=42,
        ) as batch_mock,
        patch(
            "pegasus.validation.pipeline.polars_spill.partition_side_adapter_stream",
        ) as dict_stream_mock,
        patch("pegasus.validation.pipeline.polars_spill._load_frame") as load_mock,
    ):
        result = try_partition_side_polars(
            adapter,
            writer,
            identity_columns=["uid"],
            compare_columns=["amount"],
            num_partitions=4,
            store_payload=False,
            timings=timings,
            is_source=True,
            chunk_rows=1000,
        )
    assert result == 42
    batch_mock.assert_called_once()
    dict_stream_mock.assert_not_called()
    load_mock.assert_not_called()

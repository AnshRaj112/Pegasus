# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:22:13Z
# --- END GENERATED FILE METADATA ---

"""GCS small-file validation streams into Polars (no full-object cache)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import GcsStreamSession, clear_gcs_stream_sessions
from pegasus.validation.pipeline import in_memory as in_memory_module
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline


@contextmanager
def _patch_local_gcs_stream(src: Path, tgt: Path):
    def _resolve_path(ref: GcsObjectRef) -> Path:
        return src if ref.object_name.endswith("source.csv") else tgt

    @contextmanager
    def _local_stream(self, **kwargs):
        with open(_resolve_path(self._ref), "rb") as handle:
            yield handle

    def _local_prefix(self, *, max_bytes: int) -> bytes:
        path = _resolve_path(self._ref)
        with open(path, "rb") as handle:
            return handle.read(max_bytes)

    with patch.object(GcsStreamSession, "open_binary", _local_stream):
        with patch.object(GcsStreamSession, "read_prefix", _local_prefix):
            yield


def test_gcs_load_delimited_frame_generated_100k() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-100k/source.csv")
    if not src.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    adapter = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)

    clear_gcs_stream_sessions()
    try:
        with _patch_local_gcs_stream(src, src):
            frame = in_memory_module._load_gcs_delimited_frame(adapter)
    finally:
        clear_gcs_stream_sessions()

    assert frame.height == 100_000


def test_gcs_load_delimited_frame_from_stream() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    if not src.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    adapter = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)

    clear_gcs_stream_sessions()
    try:
        with _patch_local_gcs_stream(src, src):
            frame = in_memory_module._load_gcs_delimited_frame(adapter)
    finally:
        clear_gcs_stream_sessions()

    assert frame.height == 10_000
    assert "id" in frame.columns
    assert adapter.cached_object_bytes() is None


def test_gcs_small_files_use_in_memory_without_explicit_flag() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    target_ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="target.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    cols = [
        "sku",
        "amount",
        "region",
        "attr4",
        "attr5",
        "attr6",
        "attr7",
        "attr8",
        "attr9",
        "attr10",
        "attr11",
    ]
    source_adapter = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)
    target_adapter = GcsDelimitedAdapter(target_ref, delimiter="||", size_bytes=tgt.stat().st_size)

    cfg = TabularPipelineConfig(enable_in_memory_reconcile=False, auto_in_memory_max_bytes=256 * 1024 * 1024)

    clear_gcs_stream_sessions()
    try:
        with _patch_local_gcs_stream(src, tgt):
            t0 = time.perf_counter()
            result = TabularReconciliationPipeline(
                source_adapter,
                target_adapter,
                identity_columns=["id"],
                compare_columns=cols,
                config=cfg,
            ).run()
            elapsed = time.perf_counter() - t0
    finally:
        clear_gcs_stream_sessions()

    assert result.source_row_count == 10_000
    assert result.target_row_count == 9_700
    assert result.partitions_processed == 0
    assert elapsed < 5.0


def test_validation_service_gcs_delimited_under_five_seconds() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    target_ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="target.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    source_adapter = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)
    target_adapter = GcsDelimitedAdapter(target_ref, delimiter="||", size_bytes=tgt.stat().st_size)

    get_settings.cache_clear()
    service = ValidationService(get_settings())

    clear_gcs_stream_sessions()
    try:
        with _patch_local_gcs_stream(src, tgt):
            t0 = time.perf_counter()
            result = service._validate_delimited_adapters_sync(  # noqa: SLF001
                source_adapter,
                target_adapter,
                "id",
                "||",
                source_label="gs://demo-bucket/source.csv",
                target_label="gs://demo-bucket/target.csv",
            )
            elapsed = time.perf_counter() - t0
    finally:
        clear_gcs_stream_sessions()

    assert result.source_row_count == 10_000
    assert elapsed < 5.0

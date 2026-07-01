# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T08:46:25Z
# --- END GENERATED FILE METADATA ---

"""GCS reconciliation must stream objects (no full-object download)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import GcsStreamSession, clear_gcs_stream_sessions
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline

COMPARE_COLS = [
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


def test_gcs_100k_no_full_object_download() -> None:
    src_path = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/source.csv")
    tgt_path = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/target.csv")
    if not src_path.is_file() or not tgt_path.is_file():
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
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter, prefetch_gcs_delimited_pair

    source = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src_path.stat().st_size)
    target = GcsDelimitedAdapter(target_ref, delimiter="||", size_bytes=tgt_path.stat().st_size)

    full_download_attempts = {"count": 0}

    def _forbidden_full_download(ref: GcsObjectRef) -> bytes:
        full_download_attempts["count"] += 1
        raise AssertionError("read_gcs_object_bytes must not be called")

    def _resolve_path(ref: GcsObjectRef) -> Path:
        return src_path if ref.object_name.endswith("source.csv") else tgt_path

    @contextmanager
    def _local_stream(self, **kwargs):
        with open(_resolve_path(self._ref), "rb") as handle:
            yield handle

    def _local_prefix(self, *, max_bytes: int) -> bytes:
        with open(_resolve_path(self._ref), "rb") as handle:
            return handle.read(max_bytes)

    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=256 * 1024 * 1024,
    )

    clear_gcs_stream_sessions()
    try:
        with patch("pegasus.validation.gcs_object.read_gcs_object_bytes", side_effect=_forbidden_full_download):
            with patch.object(GcsStreamSession, "open_binary", _local_stream):
                with patch.object(GcsStreamSession, "read_prefix", _local_prefix):
                    prefetch_gcs_delimited_pair(source, target)
                    t0 = time.perf_counter()
                    result = TabularReconciliationPipeline(
                        source,
                        target,
                        identity_columns=["id"],
                        compare_columns=COMPARE_COLS,
                        config=cfg,
                    ).run()
                    elapsed = time.perf_counter() - t0
    finally:
        clear_gcs_stream_sessions()

    assert result.source_row_count == 100_000
    assert full_download_attempts["count"] == 0
    assert elapsed < 15.0, f"GCS 100k stream reconcile took {elapsed:.2f}s"

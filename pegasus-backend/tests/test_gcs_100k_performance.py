# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:06:25+05:30
# --- END GENERATED FILE METADATA ---

"""GCS reconciliation must not re-download objects many times (100K regression)."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from pegasus.validation.gcs_object import GcsObjectRef
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


def test_gcs_100k_single_download_per_object() -> None:
    src_path = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/source.csv")
    tgt_path = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/target.csv")
    if not src_path.is_file() or not tgt_path.is_file():
        return

    src_bytes = src_path.read_bytes()
    tgt_bytes = tgt_path.read_bytes()
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

    source = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=len(src_bytes))
    target = GcsDelimitedAdapter(target_ref, delimiter="||", size_bytes=len(tgt_bytes))

    download_calls = {"count": 0}

    def _download(ref: GcsObjectRef) -> bytes:
        download_calls["count"] += 1
        return src_bytes if ref.object_name.endswith("source.csv") else tgt_bytes

    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=256 * 1024 * 1024,
    )

    with patch(
        "pegasus.validation.adapters.gcs_delimited.read_gcs_object_bytes",
        side_effect=_download,
    ):
        with patch(
            "pegasus.validation.adapters.gcs_delimited.read_gcs_prefix",
        ) as read_prefix:
            read_prefix.side_effect = lambda r, **kwargs: _download(r)[: kwargs.get("max_bytes", 512 * 1024)]
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

    assert result.source_row_count == 100_000
    assert download_calls["count"] == 2, f"expected 2 full downloads, got {download_calls['count']}"
    assert elapsed < 12.0, f"GCS 100k reconcile took {elapsed:.2f}s"

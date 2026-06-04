# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-04T06:59:09Z
# --- END GENERATED FILE METADATA ---

"""GCS small-file validation uses in-memory reconcile (not line-by-line spill)."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.pipeline import in_memory as in_memory_module
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline


def test_gcs_load_delimited_frame_from_cached_prefix() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    if not src.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    adapter = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)

    payload = src.read_bytes()
    with patch("pegasus.validation.adapters.gcs_delimited.read_gcs_object_bytes", return_value=payload):
        adapter.ensure_object_cached()
        frame = in_memory_module._load_gcs_delimited_frame(adapter)

    assert frame.height == 10_000
    assert "id" in frame.columns


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

    def _open_local(r: GcsObjectRef):
        return open(src if r.object_name.endswith("source.csv") else tgt, "rb")

    def _full_download(ref: GcsObjectRef) -> bytes:
        return src.read_bytes() if ref.object_name.endswith("source.csv") else tgt.read_bytes()

    with patch("pegasus.validation.adapters.gcs_delimited.read_gcs_object_bytes", side_effect=_full_download):
        with patch("pegasus.validation.adapters.gcs_delimited.read_gcs_prefix") as read_prefix:
            read_prefix.side_effect = lambda r, **kwargs: _full_download(r)[: kwargs.get("max_bytes", 512 * 1024)]
            t0 = time.perf_counter()
            result = TabularReconciliationPipeline(
                source_adapter,
                target_adapter,
                identity_columns=["id"],
                compare_columns=cols,
                config=cfg,
            ).run()
            elapsed = time.perf_counter() - t0

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

    def _open_local(r: GcsObjectRef):
        return open(src if r.object_name.endswith("source.csv") else tgt, "rb")

    def _full_download(ref: GcsObjectRef) -> bytes:
        return src.read_bytes() if ref.object_name.endswith("source.csv") else tgt.read_bytes()

    with patch("pegasus.validation.adapters.gcs_delimited.read_gcs_object_bytes", side_effect=_full_download):
        with patch("pegasus.validation.adapters.gcs_delimited.read_gcs_prefix") as read_prefix:
            read_prefix.side_effect = lambda r, **kwargs: _full_download(r)[: kwargs.get("max_bytes", 512 * 1024)]
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

    assert result.source_row_count == 10_000
    assert elapsed < 5.0

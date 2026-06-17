# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:46:02Z
# --- END GENERATED FILE METADATA ---

"""GCS streaming-only config must not auto-load full objects for in-memory reconcile."""

from __future__ import annotations

from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import _should_attempt_in_memory


def test_gcs_streaming_only_skips_auto_in_memory() -> None:
    ref = GcsObjectRef(
        bucket="b",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "p"},
    )
    source = GcsDelimitedAdapter(ref, delimiter=",", size_bytes=1024)
    target = GcsDelimitedAdapter(ref, delimiter=",", size_bytes=2048)
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        gcs_streaming_only=True,
        auto_in_memory_max_bytes=256 * 1024 * 1024,
    )
    assert not _should_attempt_in_memory(source, target, source_bytes=1024, target_bytes=2048, config=cfg)


def test_gcs_streaming_only_never_in_memory_even_when_explicitly_enabled() -> None:
    ref = GcsObjectRef(
        bucket="b",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "p"},
    )
    source = GcsDelimitedAdapter(ref, delimiter=",", size_bytes=1024)
    target = GcsDelimitedAdapter(ref, delimiter=",", size_bytes=2048)
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=True,
        gcs_streaming_only=True,
        auto_in_memory_max_bytes=256 * 1024 * 1024,
    )
    assert not _should_attempt_in_memory(source, target, source_bytes=1024, target_bytes=2048, config=cfg)

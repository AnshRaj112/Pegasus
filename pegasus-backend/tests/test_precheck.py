# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-09T09:33:27Z
# --- END GENERATED FILE METADATA ---

"""Tests for reconciliation precheck (metadata, digest, spill partitions)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import get_gcs_stream_session
from pegasus.validation.pipeline.precheck import try_identical_precheck


def test_metadata_digest_precheck_gcs() -> None:
    src_path = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    if not src_path.is_file():
        return

    ref = GcsObjectRef(
        bucket="b",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "p"},
    )
    digest = "md5:deadbeef"
    source = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src_path.stat().st_size)
    target = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src_path.stat().st_size)
    source._metadata_digest = digest
    target._metadata_digest = digest
    source._md5_hex = "deadbeef"
    target._md5_hex = "deadbeef"
    get_gcs_stream_session(ref).store_cached_object_body(src_path.read_bytes())

    result = try_identical_precheck(
        source,
        target,
        compare_columns=["sku"],
        enable_metadata=False,
        enable_content_digest=True,
    )
    assert result is not None
    assert result.extra_stats.get("precheck_method") == "content_digest"
    assert result.changed_count == 0
    assert result.source_row_count > 0


def test_metadata_precheck_different_size_skips() -> None:
    src_path = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt_path = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src_path.is_file() or not tgt_path.is_file():
        return

    source = FileDelimitedAdapter(src_path, delimiter="||")
    target = FileDelimitedAdapter(tgt_path, delimiter="||")
    assert try_identical_precheck(
        source,
        target,
        compare_columns=["sku"],
        enable_metadata=True,
        enable_content_digest=False,
    ) is None

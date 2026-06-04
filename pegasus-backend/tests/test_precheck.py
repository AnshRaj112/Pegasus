"""Tests for reconciliation precheck (metadata, digest, spill partitions)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.pipeline.precheck import try_identical_precheck


def test_content_digest_precheck_after_gcs_cache() -> None:
    src_path = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    if not src_path.is_file():
        return

    payload = src_path.read_bytes()
    ref = GcsObjectRef(
        bucket="b",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "p"},
    )
    source = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=len(payload))
    target = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=len(payload))

    with patch("pegasus.validation.adapters.gcs_delimited.read_gcs_object_bytes", return_value=payload):
        source.ensure_object_cached()
        target.ensure_object_cached()

    result = try_identical_precheck(
        source,
        target,
        compare_columns=["sku"],
        enable_metadata=False,
        enable_content_digest=True,
    )
    assert result is not None
    assert result.extra_stats.get("precheck_method") == "content_digest"
    assert result.matching_count > 0
    assert result.changed_count == 0


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

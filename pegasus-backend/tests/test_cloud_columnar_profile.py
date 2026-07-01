# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T09:36:09Z
# --- END GENERATED FILE METADATA ---

"""Cloud columnar profile and preview for Parquet objects on GCS."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import polars as pl

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.gcs_columnar import GcsColumnarAdapter
from pegasus.validation.cloud_profile import build_columnar_profile, resolve_gcs_columnar_format
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import clear_gcs_stream_sessions


def _write_parquet(path: Path) -> None:
    pl.DataFrame({"id": [1, 2], "name": ["alice", "bob"]}).write_parquet(path)


def test_resolve_gcs_columnar_format_parquet(tmp_path: Path) -> None:
    parquet_path = tmp_path / "case2_src.parquet"
    _write_parquet(parquet_path)
    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="case2_src.parquet",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    with patch("pegasus.validation.cloud_profile.read_gcs_prefix") as read_prefix:
        read_prefix.return_value = parquet_path.read_bytes()
        assert resolve_gcs_columnar_format(ref) == "parquet"


def test_build_columnar_profile_parquet(tmp_path: Path) -> None:
    src = tmp_path / "case2_src.parquet"
    _write_parquet(src)
    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="case2_src.parquet",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    adapter = GcsColumnarAdapter(ref, file_format="parquet", size_bytes=src.stat().st_size)
    clear_gcs_stream_sessions()

    with patch("pegasus.validation.adapters.gcs_columnar.get_gcs_stream_session") as get_session:
        session = get_session.return_value
        session.cached_object_body.return_value = None
        session.open_binary.return_value.__enter__.return_value.read.return_value = src.read_bytes()
        session.network_transfer_seconds = 0.0

        profile = build_columnar_profile(
            adapter,
            object_name="case2_src.parquet",
            gcs_uri="gs://demo-bucket/case2_src.parquet",
            file_format="parquet",
        )

    assert profile.file_format == "parquet"
    assert profile.column_count == 2
    assert profile.row_count == 2
    adapter.cleanup()


def test_cloud_parquet_column_preview(tmp_path: Path) -> None:
    src = tmp_path / "case2_src.parquet"
    tgt = tmp_path / "case2_tgt.parquet"
    _write_parquet(src)
    pl.DataFrame({"id": [1, 2], "name": ["alice", "bob"]}).write_parquet(tgt)

    source_ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="case2_src.parquet",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    target_ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="case2_tgt.parquet",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    source_adapter = GcsColumnarAdapter(
        source_ref,
        file_format="parquet",
        size_bytes=src.stat().st_size,
    )
    target_adapter = GcsColumnarAdapter(
        target_ref,
        file_format="parquet",
        size_bytes=tgt.stat().st_size,
    )
    clear_gcs_stream_sessions()
    get_settings.cache_clear()

    def _read_side_effect() -> bytes:
        return src.read_bytes()

    def _read_side_effect_target() -> bytes:
        return tgt.read_bytes()

    with patch("pegasus.validation.adapters.gcs_columnar.get_gcs_stream_session") as get_session:
        session = get_session.return_value
        session.cached_object_body.return_value = None
        read_handle = session.open_binary.return_value.__enter__.return_value
        read_handle.read.side_effect = [_read_side_effect(), _read_side_effect_target()]
        session.network_transfer_seconds = 0.0

        preview = ValidationService(get_settings()).preview_column_headers_from_columnar_adapters(
            source=source_adapter,
            target=target_adapter,
            uid_column="id",
            file_format="parquet",
        )

    assert preview["source_columns"] == ["id", "name"]
    assert preview["target_columns"] == ["id", "name"]
    assert any(m["source_column"] == "name" for m in preview["auto_mappings"])
    assert preview["source_samples"]["name"]

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:20:06Z
# --- END GENERATED FILE METADATA ---

"""GCS Parquet validation routing and mismatch detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import polars as pl

from pegasus.core.config import get_settings
from pegasus.schemas.validation import GoogleCloudStorageConfig, ValidationTestMode
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.gcs_columnar import GcsColumnarAdapter
from pegasus.validation.cloud_profile import resolve_cloud_pair_file_format
from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import clear_gcs_stream_sessions
from pegasus.validation.test_mode_policy import validation_run_is_match


def _write_case2_pair(tmp_path: Path) -> tuple[Path, Path]:
    """case2: value mismatch, missing row, extra row."""
    src = tmp_path / "case2_src.parquet"
    tgt = tmp_path / "case2_tgt.parquet"
    pl.DataFrame({"id": [1, 2, 3, 4, 5], "value": ["A", "B", "C", "D", "E"]}).write_parquet(src)
    pl.DataFrame({"id": [1, 2, 3, 5, 6], "value": ["A", "X", "C", "E", "F"]}).write_parquet(tgt)
    return src, tgt


def test_resolve_cloud_pair_file_format_parquet_extension() -> None:
    source = GoogleCloudStorageConfig(
        bucket="b",
        object_name="test-data/case2_src.parquet",
        credentials_json='{"type":"service_account"}',
    )
    target = GoogleCloudStorageConfig(
        bucket="b",
        object_name="test-data/case2_tgt.parquet",
        credentials_json='{"type":"service_account"}',
    )
    assert resolve_cloud_pair_file_format(source, target, declared="auto") == "parquet"


def test_gcs_parquet_case2_detects_mismatches(tmp_path: Path) -> None:
    src, tgt = _write_case2_pair(tmp_path)
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

    def _read_source() -> bytes:
        return src.read_bytes()

    def _read_target() -> bytes:
        return tgt.read_bytes()

    def _session_for_ref(ref: GcsObjectRef):
        from unittest.mock import MagicMock

        session = MagicMock()
        session.cached_object_body.return_value = None
        read_handle = session.open_binary.return_value.__enter__.return_value
        if ref.object_name.endswith("case2_src.parquet"):
            read_handle.read.return_value = _read_source()
        else:
            read_handle.read.return_value = _read_target()
        session.network_transfer_seconds = 0.0
        return session

    with patch("pegasus.validation.adapters.gcs_columnar.get_gcs_stream_session") as get_session:
        get_session.side_effect = _session_for_ref

        result = ValidationService(get_settings()).validate_columnar_pair_sync(
            source_adapter,
            target_adapter,
            uid_column="id",
            file_format="parquet",
            test_mode=ValidationTestMode.FULL,
        )

    summary = result.report.summary
    assert summary[MismatchType.VALUE_MISMATCH.value] >= 1
    assert summary[MismatchType.MISSING_IN_TARGET.value] >= 1
    assert summary[MismatchType.EXTRA_IN_TARGET.value] >= 1
    assert validation_run_is_match(
        summary,
        total_mismatch_records=result.report.mismatches.height,
        test_mode=ValidationTestMode.FULL.value,
        source_row_count=result.source_row_count,
        target_row_count=result.target_row_count,
    ) is False
    source_adapter.cleanup()
    target_adapter.cleanup()


def test_load_frame_supports_gcs_columnar_after_materialize(tmp_path: Path) -> None:
    from pegasus.validation.pipeline.in_memory import _load_frame

    src, _tgt = _write_case2_pair(tmp_path)
    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="case2_src.parquet",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    adapter = GcsColumnarAdapter(ref, file_format="parquet", size_bytes=src.stat().st_size)
    clear_gcs_stream_sessions()

    def _session_for_ref(ref: GcsObjectRef):
        from unittest.mock import MagicMock

        session = MagicMock()
        session.cached_object_body.return_value = None
        read_handle = session.open_binary.return_value.__enter__.return_value
        read_handle.read.return_value = src.read_bytes()
        session.network_transfer_seconds = 0.0
        return session

    with patch("pegasus.validation.adapters.gcs_columnar.get_gcs_stream_session") as get_session:
        get_session.side_effect = _session_for_ref
        frame = _load_frame(adapter, identity_columns=["id"], compare_columns=["value"])

    assert frame is not None
    assert frame.height == 5
    assert set(frame.columns) == {"id", "value"}
    adapter.cleanup()

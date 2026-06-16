# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T13:34:40Z
# --- END GENERATED FILE METADATA ---

"""Cloud file profile: detection and row/column counts."""

from __future__ import annotations

from pathlib import Path
from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.cloud_profile import build_delimited_profile, count_adapter_rows
from pegasus.validation.gcs_object import GcsObjectRef


def test_count_adapter_rows_from_local_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

    adapter = FileDelimitedAdapter(csv_path, delimiter=",", has_header=True)
    assert count_adapter_rows(adapter) == 2


def test_build_delimited_profile_detects_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

    adapter = FileDelimitedAdapter(csv_path, delimiter=",", has_header=True)
    profile = build_delimited_profile(
        adapter,
        object_name="sample.csv",
        gcs_uri=f"gs://bucket/{csv_path.name}",
        resolved_delimiter=",",
    )
    assert profile.file_format == "csv"
    assert profile.column_count == 2
    assert profile.row_count == 2


def test_profile_gcs_adapter_streams_without_full_download(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    src.write_text("employee_id,name\n1,alice\n2,bob\n", encoding="utf-8")
    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    adapter = GcsDelimitedAdapter(ref, delimiter=",", size_bytes=src.stat().st_size)
    from pegasus.validation.gcs_stream import get_gcs_stream_session

    get_gcs_stream_session(ref).store_cached_object_body(src.read_bytes())

    get_settings.cache_clear()
    profile = ValidationService(get_settings()).profile_delimited_adapter(
        adapter,
        object_name="source.csv",
        gcs_uri="gs://demo-bucket/source.csv",
        delimiter=",",
    )

    assert profile.file_format == "csv"
    assert profile.column_count == 2
    assert profile.row_count == 2

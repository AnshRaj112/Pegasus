# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:26:33Z
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


def test_build_profile_csv_wrong_extension(tmp_path: Path) -> None:
    path = tmp_path / "data.abc"
    path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

    adapter = FileDelimitedAdapter(path, delimiter=",", has_header=True)
    profile = build_delimited_profile(
        adapter,
        object_name="data.abc",
        gcs_uri="gs://bucket/data.abc",
        resolved_delimiter=",",
    )
    assert profile.file_format == "csv"
    assert profile.suggested_file_format == "csv"


def test_build_profile_fixed_width_custom_extension(tmp_path: Path) -> None:
    lines = [
        "ID      NAME                AMOUNT",
        "00000001ALICE SMITH          00001234",
        "00000002BOB JONES            00005678",
    ]
    path = tmp_path / "payroll.verizon"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

    adapter = FileDelimitedAdapter(path, delimiter=",", has_header=True)
    profile = build_delimited_profile(
        adapter,
        object_name="payroll.verizon",
        gcs_uri="gs://bucket/payroll.verizon",
        resolved_delimiter=",",
    )
    assert profile.file_format == "fixed-width"
    assert profile.suggested_file_format == "fixed-width"


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

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T09:36:09Z
# --- END GENERATED FILE METADATA ---

"""Cloud file profile: detection and row/column counts."""

from __future__ import annotations

from pathlib import Path
from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.cloud_profile import build_delimited_profile, count_adapter_rows
from pegasus.validation.gcs_object import GcsObjectRef


def test_build_profile_json_document(tmp_path: Path) -> None:
    path = tmp_path / "doc.json"
    path.write_text('{"items": ["a"], "meta": {"x": 1}}', encoding="utf-8")
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

    adapter = FileDelimitedAdapter(path, delimiter=",", has_header=True)
    profile = build_delimited_profile(
        adapter,
        object_name="doc.json",
        gcs_uri="gs://bucket/doc.json",
        resolved_delimiter=",",
    )
    assert profile.suggested_file_format == "json"
    assert profile.column_count == 1
    assert profile.row_count == 1
    assert profile.json_preview is not None
    assert '"items"' in profile.json_preview


def test_profile_json_skips_auto_delimiter(tmp_path: Path) -> None:
    path = tmp_path / "doc.json"
    path.write_text('{"items": ["a"], "meta": {"x": 1}}', encoding="utf-8")
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

    adapter = FileDelimitedAdapter(path, delimiter="auto", has_header=True)
    profile = ValidationService(get_settings()).profile_delimited_adapter(
        adapter,
        object_name="doc.json",
        gcs_uri="gs://bucket/doc.json",
        delimiter="auto",
    )
    assert profile.suggested_file_format == "json"
    assert profile.json_preview is not None


def test_resolve_cloud_pair_file_format_declared_json() -> None:
    from pegasus.schemas.validation import GoogleCloudStorageConfig
    from pegasus.validation.cloud_profile import resolve_cloud_pair_file_format

    source = GoogleCloudStorageConfig(
        bucket="b",
        object_name="source.json",
        credentials_json='{"type":"service_account"}',
    )
    target = GoogleCloudStorageConfig(
        bucket="b",
        object_name="target.json",
        credentials_json='{"type":"service_account"}',
    )
    assert resolve_cloud_pair_file_format(source, target, declared="json") == "json"


def test_resolve_cloud_pair_file_format_parquet_extension() -> None:
    from pegasus.schemas.validation import GoogleCloudStorageConfig
    from pegasus.validation.cloud_profile import resolve_cloud_pair_file_format

    source = GoogleCloudStorageConfig(
        bucket="b",
        object_name="case2_src.parquet",
        credentials_json='{"type":"service_account"}',
    )
    target = GoogleCloudStorageConfig(
        bucket="b",
        object_name="case2_tgt.parquet",
        credentials_json='{"type":"service_account"}',
    )
    assert resolve_cloud_pair_file_format(source, target, declared="auto") == "parquet"


def test_resolve_cloud_pair_file_format_declared_zip() -> None:
    from pegasus.schemas.validation import GoogleCloudStorageConfig
    from pegasus.validation.cloud_profile import resolve_cloud_pair_file_format

    source = GoogleCloudStorageConfig(
        bucket="b",
        object_name="nested.tar",
        credentials_json='{"type":"service_account"}',
    )
    target = GoogleCloudStorageConfig(
        bucket="b",
        object_name="nested.tar",
        credentials_json='{"type":"service_account"}',
    )
    assert resolve_cloud_pair_file_format(source, target, declared="tar") == "tar"
    assert resolve_cloud_pair_file_format(source, target, declared="zip") == "zip"


def test_resolve_cloud_pair_file_format_declared_fixed_width() -> None:
    from pegasus.schemas.validation import GoogleCloudStorageConfig
    from pegasus.validation.cloud_profile import resolve_cloud_pair_file_format

    source = GoogleCloudStorageConfig(
        bucket="b",
        object_name="payroll.dat",
        credentials_json='{"type":"service_account"}',
    )
    target = GoogleCloudStorageConfig(
        bucket="b",
        object_name="payroll.dat",
        credentials_json='{"type":"service_account"}',
    )
    assert resolve_cloud_pair_file_format(source, target, declared="fixed-width") == "fixed-width"


def test_resolve_cloud_pair_file_format_dat_uses_content_detection(monkeypatch) -> None:
    from pegasus.schemas.validation import GoogleCloudStorageConfig
    from pegasus.validation.cloud_profile import resolve_cloud_pair_file_format
    from pegasus.validation.file_detection.types import FileDetectionReport

    def _fw_report(_ref: object) -> FileDetectionReport:
        return FileDetectionReport(
            path="/tmp/sample.dat",
            file_size_bytes=128,
            bytes_read=128,
            dataset_model="tabular",
            suggested_file_format="fixed-width",
        )

    monkeypatch.setattr(
        "pegasus.validation.cloud_profile.detect_gcs_object_format",
        _fw_report,
    )

    source = GoogleCloudStorageConfig(
        bucket="b",
        object_name="payroll.dat",
        credentials_json='{"type":"service_account"}',
    )
    target = GoogleCloudStorageConfig(
        bucket="b",
        object_name="payroll.dat",
        credentials_json='{"type":"service_account"}',
    )
    assert resolve_cloud_pair_file_format(source, target, declared="auto") == "fixed-width"


def test_build_delimited_profile_includes_inferred_has_header(tmp_path) -> None:
    path = tmp_path / "headerless.csv"
    path.write_text("ID001,John Doe,05/19/2026\nID002,Jane Doe,06/01/2026\n", encoding="utf-8")
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

    adapter = FileDelimitedAdapter(path, delimiter=",", has_header=True)
    profile = build_delimited_profile(
        adapter,
        object_name="headerless.csv",
        gcs_uri="gs://bucket/headerless.csv",
        resolved_delimiter=",",
        has_header=True,
    )
    assert profile.inferred_has_header is False


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

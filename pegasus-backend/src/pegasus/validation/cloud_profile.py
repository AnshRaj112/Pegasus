# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:03:13Z
# --- END GENERATED FILE METADATA ---

"""Profile GCS delimited objects: format detection, column count, row count."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.schemas.validation import CloudFileProfileResponse
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.types import FileDetectionReport
from pegasus.validation.file_format import format_hint_from_suffix


def format_display_label(
    report: FileDetectionReport,
    *,
    object_name: str,
) -> str:
    """Return a short UI label (csv, fixed-width, parquet, …)."""
    if report.suggested_file_format:
        return report.suggested_file_format
    suffix = Path(object_name).suffix
    return format_hint_from_suffix(suffix) or "unknown"


def detect_format_from_adapter(
    adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
) -> FileDetectionReport:
    """Run the multi-layer detection pipeline on a bounded prefix sample."""
    if isinstance(adapter, FileDelimitedAdapter):
        return detect_file(adapter.path)

    prefix = adapter._ensure_prefix_bytes(64 * 1024)
    suffix = adapter.path.suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(prefix)
        tmp_path = Path(tmp.name)
    try:
        return detect_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def count_adapter_rows(adapter: FileDelimitedAdapter | GcsDelimitedAdapter) -> int:
    """Estimate data rows from a prefix sample (GCS) or exact count for small local files."""
    from pegasus.validation.row_count import profile_delimited_data_rows

    return profile_delimited_data_rows(adapter)


def build_delimited_profile(
    adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
    *,
    object_name: str,
    gcs_uri: str,
    resolved_delimiter: str,
    has_header: bool = True,
) -> CloudFileProfileResponse:
    """Build a cloud file profile from a warmed delimited adapter."""
    if isinstance(adapter, GcsDelimitedAdapter):
        adapter.warm_metadata()
    report = detect_format_from_adapter(adapter)
    schema = adapter.get_schema()
    column_count = len(schema.columns)
    row_count = count_adapter_rows(adapter)
    size_bytes = adapter.get_size_bytes() if hasattr(adapter, "get_size_bytes") else 0

    return CloudFileProfileResponse(
        object_name=object_name,
        gcs_uri=gcs_uri,
        file_size_bytes=int(size_bytes or 0),
        file_format=format_display_label(report, object_name=object_name),
        suggested_file_format=report.suggested_file_format,
        dataset_model=report.dataset_model,
        column_count=column_count,
        row_count=row_count,
        delimiter=resolved_delimiter,
        has_header=has_header,
    )

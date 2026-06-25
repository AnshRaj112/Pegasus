# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:27:35Z
# --- END GENERATED FILE METADATA ---

"""Profile GCS delimited objects: format detection, column count, row count."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.schemas.validation import CloudFileProfileResponse
from pegasus.validation.adapters.file_columnar import FileColumnarAdapter
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_columnar import GcsColumnarAdapter, columnar_row_count
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.display_label import build_format_display_label
from pegasus.validation.file_detection.types import FileDetectionReport
from pegasus.validation.file_format import infer_file_format_from_path, is_columnar_format, normalize_file_format
from pegasus.validation.gcs_object import GcsObjectRef, read_gcs_prefix


def format_display_label(
    report: FileDetectionReport,
    *,
    object_name: str,
    path: str | Path | None = None,
) -> str:
    """Return a short UI label (csv, fixed-width, zip -> csv, …)."""
    resolved_path = Path(path) if path is not None else Path(report.path)
    return build_format_display_label(
        report,
        path=resolved_path,
        object_name=object_name,
    )


def detect_gcs_object_format(ref: GcsObjectRef) -> FileDetectionReport:
    """Run the detection pipeline on a bounded GCS prefix sample."""
    prefix = read_gcs_prefix(ref, max_bytes=64 * 1024)
    suffix = Path(ref.object_name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(prefix)
        tmp_path = Path(tmp.name)
    try:
        return detect_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def resolve_gcs_columnar_format(ref: GcsObjectRef) -> str | None:
    """Return a canonical columnar format token when the GCS object is columnar."""
    report = detect_gcs_object_format(ref)
    fmt = normalize_file_format(report.suggested_file_format)
    if is_columnar_format(fmt):
        return fmt
    ext_fmt = infer_file_format_from_path(Path(ref.object_name), "auto")
    if is_columnar_format(ext_fmt):
        return ext_fmt
    return None


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
    size_bytes = int(adapter.get_size_bytes() if hasattr(adapter, "get_size_bytes") else 0)
    if size_bytes == 0:
        return CloudFileProfileResponse(
            object_name=object_name,
            gcs_uri=gcs_uri,
            file_size_bytes=0,
            file_format="empty",
            suggested_file_format="empty",
            dataset_model=None,
            column_count=0,
            row_count=0,
            delimiter=resolved_delimiter,
            has_header=has_header,
        )
    if isinstance(adapter, FileDelimitedAdapter):
        from pegasus.validation.empty_inputs import file_has_no_content

        if file_has_no_content(adapter.path):
            return CloudFileProfileResponse(
                object_name=object_name,
                gcs_uri=gcs_uri,
                file_size_bytes=size_bytes,
                file_format="empty",
                suggested_file_format="empty",
                dataset_model=None,
                column_count=0,
                row_count=0,
                delimiter=resolved_delimiter,
                has_header=has_header,
            )

    report = detect_format_from_adapter(adapter)
    schema = adapter.get_schema()
    column_count = len(schema.columns)
    if report.suggested_file_format == "fixed-width":
        from pegasus.validation.fixed_width_layout import build_column_previews, sample_lines_from_adapter

        lines = sample_lines_from_adapter(adapter)
        inferred = build_column_previews(lines, lines)
        if inferred:
            column_count = len(inferred)
    row_count = count_adapter_rows(adapter)

    detect_path = adapter.path if isinstance(adapter, FileDelimitedAdapter) else Path(object_name)

    return CloudFileProfileResponse(
        object_name=object_name,
        gcs_uri=gcs_uri,
        file_size_bytes=size_bytes,
        file_format=format_display_label(
            report,
            object_name=object_name,
            path=detect_path,
        ),
        suggested_file_format=report.suggested_file_format,
        dataset_model=report.dataset_model,
        column_count=column_count,
        row_count=row_count,
        delimiter=resolved_delimiter,
        has_header=has_header,
    )


def build_columnar_profile(
    adapter: GcsColumnarAdapter | FileColumnarAdapter,
    *,
    object_name: str,
    gcs_uri: str,
    file_format: str,
) -> CloudFileProfileResponse:
    """Build a cloud file profile from a columnar adapter (local or GCS)."""
    if isinstance(adapter, GcsColumnarAdapter):
        adapter.warm_metadata()
        size_bytes = adapter.get_size_bytes()
    elif isinstance(adapter, FileColumnarAdapter):
        size_bytes = adapter.path.stat().st_size
    else:
        size_bytes = 0
    fmt = normalize_file_format(file_format)
    if size_bytes == 0:
        return CloudFileProfileResponse(
            object_name=object_name,
            gcs_uri=gcs_uri,
            file_size_bytes=0,
            file_format="empty",
            suggested_file_format="empty",
            dataset_model="columnar",
            column_count=0,
            row_count=0,
            delimiter=None,
            has_header=True,
        )

    schema = adapter.get_schema()
    row_count = (
        adapter.get_row_count()
        if isinstance(adapter, GcsColumnarAdapter)
        else columnar_row_count(adapter.path, fmt)
    )
    if isinstance(adapter, GcsColumnarAdapter):
        assert adapter._local_path is not None
        report = detect_file(adapter._local_path)
        detect_path = Path(object_name)
    else:
        report = detect_file(adapter.path)
        detect_path = adapter.path

    return CloudFileProfileResponse(
        object_name=object_name,
        gcs_uri=gcs_uri,
        file_size_bytes=size_bytes,
        file_format=format_display_label(
            report,
            object_name=object_name,
            path=detect_path,
        ),
        suggested_file_format=report.suggested_file_format or fmt,
        dataset_model=report.dataset_model or "columnar",
        column_count=len(schema.columns),
        row_count=int(row_count),
        delimiter=None,
        has_header=True,
    )

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:26:33Z
# --- END GENERATED FILE METADATA ---

"""Profile GCS delimited objects: format detection, column count, row count."""

from __future__ import annotations

import json
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
from pegasus.validation.gcs_object import GcsObjectRef, gcs_object_ref_from_config, read_gcs_prefix


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


def resolve_gcs_json_format(ref: GcsObjectRef) -> bool:
    """Return whether a GCS object sample is detected as JSON."""
    report = detect_gcs_object_format(ref)
    fmt = normalize_file_format(report.suggested_file_format)
    if fmt == "json":
        return True
    ext_fmt = infer_file_format_from_path(Path(ref.object_name), "auto")
    return ext_fmt == "json"


def resolve_cloud_pair_file_format(
    source_cloud: object,
    target_cloud: object,
    *,
    declared: str | None,
) -> str:
    """Resolve canonical format for a GCS source/target pair."""
    from pegasus.schemas.validation import GoogleCloudStorageConfig

    if not isinstance(source_cloud, GoogleCloudStorageConfig) or not isinstance(target_cloud, GoogleCloudStorageConfig):
        raise ValueError("source_cloud and target_cloud are required")

    declared_norm = normalize_file_format(declared) if declared else "auto"
    if declared_norm == "json":
        return "json"
    if declared_norm == "fixed-width":
        return "fixed-width"
    if declared_norm not in {"auto", "csv"}:
        return declared_norm

    src_ref = gcs_object_ref_from_config(source_cloud)
    tgt_ref = gcs_object_ref_from_config(target_cloud)
    src_json = resolve_gcs_json_format(src_ref)
    tgt_json = resolve_gcs_json_format(tgt_ref)
    if src_json or tgt_json:
        if src_json != tgt_json:
            raise ValueError("Source and target must both be JSON documents")
        return "json"

    src_ext = infer_file_format_from_path(Path(src_ref.object_name), "auto")
    tgt_ext = infer_file_format_from_path(Path(tgt_ref.object_name), "auto")
    if src_ext != tgt_ext:
        raise ValueError("Source and target must use the same file format")
    if src_ext == "json":
        return "json"
    return "csv"


def _json_profile_detected(
    report: FileDetectionReport,
    *,
    object_name: str,
    detect_path: Path,
) -> bool:
    if report.suggested_file_format == "json":
        return True
    if infer_file_format_from_path(Path(object_name), "auto") == "json":
        return True
    return infer_file_format_from_path(detect_path, "auto") == "json"


def build_json_preview_sample(
    adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
    *,
    max_bytes: int = 64 * 1024,
    max_chars: int = 8000,
) -> str | None:
    """Return a pretty-printed JSON prefix for overview preview."""
    try:
        if isinstance(adapter, FileDelimitedAdapter):
            raw = adapter.path.read_bytes()[:max_bytes]
        else:
            adapter.warm_metadata()
            size = int(adapter.get_size_bytes())
            raw = adapter._ensure_prefix_bytes(min(size, max_bytes))
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:5]
            parts: list[str] = []
            for line in lines:
                try:
                    parts.append(json.dumps(json.loads(line), indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    parts.append(line)
            pretty = "\n\n".join(parts)
        if len(pretty) > max_chars:
            return pretty[:max_chars].rstrip() + "\n…"
        return pretty
    except Exception:
        return None


def is_json_delimited_adapter(
    adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
    *,
    object_name: str | None = None,
) -> bool:
    """Return whether an adapter points at a JSON document (sample or extension)."""
    if isinstance(adapter, GcsDelimitedAdapter):
        adapter.warm_metadata()
    detect_path = adapter.path if isinstance(adapter, FileDelimitedAdapter) else Path(object_name or adapter.path)
    name = object_name or detect_path.name
    if infer_file_format_from_path(Path(name), "auto") == "json":
        return True
    report = detect_format_from_adapter(adapter)
    return _json_profile_detected(report, object_name=name, detect_path=detect_path)


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
    detect_path = adapter.path if isinstance(adapter, FileDelimitedAdapter) else Path(object_name)
    if _json_profile_detected(report, object_name=object_name, detect_path=detect_path):
        return CloudFileProfileResponse(
            object_name=object_name,
            gcs_uri=gcs_uri,
            file_size_bytes=size_bytes,
            file_format=format_display_label(
                report,
                object_name=object_name,
                path=detect_path,
            ),
            suggested_file_format="json",
            dataset_model=report.dataset_model or "hierarchical",
            column_count=1,
            row_count=1,
            delimiter=resolved_delimiter,
            has_header=has_header,
            json_preview=build_json_preview_sample(adapter),
        )

    schema = adapter.get_schema()
    column_count = len(schema.columns)
    if report.suggested_file_format == "fixed-width":
        from pegasus.validation.fixed_width_layout import build_column_previews, sample_lines_from_adapter

        lines = sample_lines_from_adapter(adapter)
        inferred = build_column_previews(lines, lines)
        if inferred:
            column_count = len(inferred)
    row_count = count_adapter_rows(adapter)

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

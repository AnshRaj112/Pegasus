# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T07:10:42Z
# --- END GENERATED FILE METADATA ---

"""GCS helpers for archive manifest listing without full-object download."""

from __future__ import annotations

from pegasus.validation.archive_compare import (
    MAX_ARCHIVE_NEST_DEPTH,
    ArchiveEntry,
    iter_tar_manifest_nested_from_stream,
    zip_manifest_from_gcs_seekable,
    zip_manifest_from_suffix_bytes,
)
from pegasus.validation.file_format import normalize_archive_format
from pegasus.validation.gcs_object import GcsObjectRef, gcs_blob_size, read_gcs_suffix
from pegasus.validation.gcs_stream import get_gcs_stream_session

_SUFFIX_READ_BYTES = 256 * 1024


def _resolve_ref(adapter: object) -> GcsObjectRef:
    if isinstance(adapter, GcsObjectRef):
        return adapter
    ref = getattr(adapter, "_ref", None)
    if isinstance(ref, GcsObjectRef):
        return ref
    raise TypeError("expected GcsObjectRef or adapter with _ref")


def load_gcs_archive_manifest(
    adapter: object,
    *,
    archive_format: str,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    """Load archive entry metadata from GCS, expanding nested members when bounded."""
    ref = _resolve_ref(adapter)
    fmt = normalize_archive_format(archive_format)
    size = gcs_blob_size(ref)
    if size <= 0:
        return []
    if fmt == "zip":
        try:
            return zip_manifest_from_gcs_seekable(
                ref,
                size,
                max_nest_depth=max_nest_depth,
                max_nested_member_bytes=max_nested_member_bytes,
                max_declared_bytes=max_declared_bytes,
                max_compression_ratio=max_compression_ratio,
                warnings=warnings,
            )
        except Exception:
            suffix = read_gcs_suffix(ref, max_bytes=_SUFFIX_READ_BYTES)
            return zip_manifest_from_suffix_bytes(suffix, size)
    with get_gcs_stream_session(ref).open_binary(read_ahead=False) as handle:
        return iter_tar_manifest_nested_from_stream(
            handle,
            depth=0,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=warnings,
        )

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T10:14:13Z
# --- END GENERATED FILE METADATA ---

"""Google Cloud Storage prefix browsing for the validation file picker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pegasus.validation.file_format import extensions_for_format, object_name_matches_format


def parse_gcs_credentials_json(raw_json: str) -> dict[str, object]:
    import json

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Cloud credential payload must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Cloud credential payload must be a JSON object")
    return parsed


@dataclass(frozen=True)
class GcsBrowseEntry:
    name: str
    path: str
    is_dir: bool
    size_bytes: int | None = None


@dataclass(frozen=True)
class GcsBrowseResult:
    bucket: str
    prefix: str
    parent_prefix: str | None
    entries: list[GcsBrowseEntry]
    truncated: bool


def _normalize_prefix(prefix: str) -> str:
    text = (prefix or "").strip()
    if text and not text.endswith("/"):
        text = f"{text}/"
    return text


def _parent_prefix(prefix: str) -> str | None:
    norm = _normalize_prefix(prefix)
    if not norm:
        return None
    parts = norm.rstrip("/").split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1]) + "/"


def coerce_gcs_object_size(raw: object) -> int | None:
    """Normalize GCS object size metadata (API may return int or numeric string)."""
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _blob_size_bytes(blob: object) -> int | None:
    size = coerce_gcs_object_size(getattr(blob, "size", None))
    if size is not None:
        return size
    reload = getattr(blob, "reload", None)
    if not callable(reload):
        return None
    try:
        reload()
    except Exception:
        return None
    return coerce_gcs_object_size(getattr(blob, "size", None))


def _file_allowed(name: str, allowed: frozenset[str]) -> bool:
    return object_name_matches_format(name, allowed)


def browse_gcs_prefix(
    *,
    bucket: str,
    prefix: str,
    credentials_info: dict[str, object],
    project_id: str | None,
    file_format: str | None = None,
    max_entries: int = 5000,
) -> GcsBrowseResult:
    """List immediate child prefixes and blobs under *prefix* (delimiter='/')."""
    from google.cloud import storage as gcs_storage
    from google.oauth2 import service_account

    bucket_name = bucket.strip()
    if not bucket_name:
        raise ValueError("bucket is required")

    norm_prefix = _normalize_prefix(prefix)
    allowed = extensions_for_format(file_format)

    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    client = gcs_storage.Client(credentials=credentials, project=project_id or credentials_info.get("project_id"))
    iterator = client.list_blobs(
        bucket_name,
        prefix=norm_prefix or None,
        delimiter="/",
        projection="full",
    )

    rows: list[tuple[bool, str, str, str, int | None]] = []
    truncated = False

    for page in iterator.pages:
        for folder_prefix in page.prefixes:
            name = folder_prefix[len(norm_prefix):].rstrip("/")
            if not name:
                continue
            rows.append((False, name.lower(), folder_prefix, name, None))
        for blob in page:
            if blob.name.endswith("/"):
                continue
            rel_name = blob.name[len(norm_prefix):] if norm_prefix else blob.name
            if "/" in rel_name:
                continue
            if not _file_allowed(blob.name, allowed):
                continue
            rows.append((True, rel_name.lower(), blob.name, rel_name, _blob_size_bytes(blob)))

    rows.sort(key=lambda t: (t[0], t[1]))
    if len(rows) > max_entries:
        truncated = True
        rows = rows[:max_entries]

    entries = [
        GcsBrowseEntry(
            name=display_name,
            path=path,
            is_dir=not is_file,
            size_bytes=size_bytes,
        )
        for is_file, _, path, display_name, size_bytes in rows
    ]
    return GcsBrowseResult(
        bucket=bucket_name,
        prefix=norm_prefix,
        parent_prefix=_parent_prefix(norm_prefix),
        entries=entries,
        truncated=truncated,
    )


def list_gcs_files_under_prefix(
    *,
    bucket: str,
    prefix: str,
    credentials_info: dict[str, object],
    project_id: str | None,
    file_format: str | None = None,
    recursive: bool = False,
    max_files: int = 10_000,
) -> list[str]:
    """Return object names under *prefix* (recursive optional)."""
    from google.cloud import storage as gcs_storage
    from google.oauth2 import service_account

    bucket_name = bucket.strip()
    norm_prefix = _normalize_prefix(prefix)
    allowed = extensions_for_format(file_format)

    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    client = gcs_storage.Client(credentials=credentials, project=project_id or credentials_info.get("project_id"))

    names: list[str] = []
    if recursive:
        for blob in client.list_blobs(bucket_name, prefix=norm_prefix or None):
            if blob.name.endswith("/"):
                continue
            if not _file_allowed(blob.name, allowed):
                continue
            names.append(blob.name)
            if len(names) >= max_files:
                break
    else:
        result = browse_gcs_prefix(
            bucket=bucket_name,
            prefix=norm_prefix,
            credentials_info=credentials_info,
            project_id=project_id,
            file_format=file_format,
            max_entries=max_files,
        )
        names = [e.path for e in result.entries if not e.is_dir]

    return sorted(names, key=str.lower)


def download_gcs_objects(
    *,
    bucket: str,
    object_names: list[str],
    credentials_info: dict[str, object],
    project_id: str | None,
    dest_dir: Path,
) -> list[Path]:
    """Download GCS objects into *dest_dir*; return local paths in the same order."""
    from google.cloud import storage as gcs_storage
    from google.oauth2 import service_account

    dest_dir.mkdir(parents=True, exist_ok=True)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    client = gcs_storage.Client(credentials=credentials, project=project_id or credentials_info.get("project_id"))
    bucket_ref = client.bucket(bucket.strip())
    local_paths: list[Path] = []
    for object_name in object_names:
        name = object_name.strip().lstrip("/")
        if not name:
            continue
        safe_name = name.replace("/", "__")
        dest = dest_dir / safe_name
        blob = bucket_ref.blob(name)
        _stream_blob_to_path(blob, dest)
        local_paths.append(dest.resolve())


def _stream_blob_to_path(blob: Any, dest: Path, *, chunk_bytes: int = 256 * 1024) -> None:
    """Write object to *dest* via chunked streaming (no download_to_filename)."""
    with blob.open("rb") as src, open(dest, "wb") as out:
        while True:
            block = src.read(chunk_bytes)
            if not block:
                break
            out.write(block)

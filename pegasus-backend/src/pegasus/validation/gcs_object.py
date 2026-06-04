# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:06:25+05:30
# --- END GENERATED FILE METADATA ---

"""GCS object references and bounded streaming reads (no full download)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from pegasus.schemas.validation import GoogleCloudStorageConfig

_DEFAULT_PREFIX_BYTES = 512 * 1024
_DEFAULT_PREFIX_LINES = 500


@dataclass(frozen=True, slots=True)
class GcsObjectRef:
    bucket: str
    object_name: str
    credentials_info: dict[str, object]
    project_id: str | None = None

    @property
    def uri(self) -> str:
        return f"gs://{self.bucket.strip()}/{self.object_name.strip().lstrip('/')}"

    @property
    def display_path(self) -> Path:
        safe = self.object_name.strip().lstrip("/").replace("/", "__")
        return Path(f"/gcs/{self.bucket.strip()}/{safe}")


def gcs_object_ref_from_config(cloud: GoogleCloudStorageConfig) -> GcsObjectRef:
    from pegasus.validation.cloud_credentials import resolve_cloud_credentials

    info = resolve_cloud_credentials(cloud.credentials_json or "")
    bucket = (cloud.bucket or "").strip()
    if not bucket:
        raise ValueError("Cloud bucket is required")
    object_name = cloud.object_name.strip()
    if not object_name:
        raise ValueError("Cloud object_name is required")
    project_id = (cloud.project_id or "").strip() or None
    if not project_id and isinstance(info.get("project_id"), str):
        project_id = str(info["project_id"])
    return GcsObjectRef(
        bucket=bucket,
        object_name=object_name,
        credentials_info=info,
        project_id=project_id,
    )


def gcs_object_ref_from_meta(raw: dict[str, object]) -> GcsObjectRef:
    creds = raw.get("credentials_json")
    if not isinstance(creds, str) or not creds.strip():
        raise ValueError("Cloud credentials_json is required in job metadata")
    try:
        info = json.loads(creds)
    except json.JSONDecodeError as exc:
        raise ValueError("Cloud credentials_json must be valid JSON") from exc
    if not isinstance(info, dict):
        raise ValueError("Cloud credentials_json must be a JSON object")
    bucket = str(raw.get("bucket") or "").strip()
    object_name = str(raw.get("object_name") or "").strip()
    if not bucket or not object_name:
        raise ValueError("Cloud bucket and object_name are required in job metadata")
    project_id = str(raw.get("project_id") or "").strip() or None
    if not project_id and isinstance(info.get("project_id"), str):
        project_id = str(info["project_id"])
    return GcsObjectRef(
        bucket=bucket,
        object_name=object_name,
        credentials_info=info,
        project_id=project_id,
    )


def cloud_config_to_meta(cloud: GoogleCloudStorageConfig) -> dict[str, object]:
    """Serialize a resolved cloud config for job metadata (streamed in worker)."""
    return {
        "provider": cloud.provider,
        "bucket": (cloud.bucket or "").strip(),
        "object_name": cloud.object_name.strip(),
        "credentials_json": cloud.credentials_json or "",
        "project_id": (cloud.project_id or "").strip() or None,
    }


def _storage_client(ref: GcsObjectRef):
    from google.cloud import storage as gcs_storage
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(ref.credentials_info)
    return gcs_storage.Client(credentials=credentials, project=ref.project_id)


def _blob(ref: GcsObjectRef):
    client = _storage_client(ref)
    return client.bucket(ref.bucket.strip()).blob(ref.object_name.strip().lstrip("/"))


def gcs_blob_size(ref: GcsObjectRef) -> int:
    return gcs_blob_fingerprints(ref)[0]


def gcs_blob_fingerprints(ref: GcsObjectRef) -> tuple[int, str | None, str | None]:
    """Return ``(size_bytes, crc32c, md5_hex)`` from GCS object metadata."""
    blob = _blob(ref)
    blob.reload()
    size = blob.size
    if size is None:
        raise ValueError(f"Could not determine size for {ref.uri}")
    crc = getattr(blob, "crc32c", None)
    md5 = getattr(blob, "md5_hash", None)
    return int(size), str(crc) if crc else None, str(md5) if md5 else None


def open_gcs_binary(ref: GcsObjectRef) -> IO[bytes]:
    return _blob(ref).open("rb")


def read_gcs_prefix(
    ref: GcsObjectRef,
    *,
    max_bytes: int = _DEFAULT_PREFIX_BYTES,
) -> bytes:
    with open_gcs_binary(ref) as handle:
        return handle.read(max_bytes)


def read_gcs_object_bytes(ref: GcsObjectRef) -> bytes:
    """Download the full object in one request (preferred for objects that fit in RAM)."""
    blob = _blob(ref)
    payload = blob.download_as_bytes()
    if not payload:
        return b""
    return payload


def sample_gcs_lines(
    ref: GcsObjectRef,
    *,
    max_bytes: int = _DEFAULT_PREFIX_BYTES,
    max_lines: int = _DEFAULT_PREFIX_LINES,
) -> list[str]:
    out: list[str] = []
    consumed = 0
    with open_gcs_binary(ref) as handle:
        while consumed < max_bytes and len(out) < max_lines:
            raw = handle.readline()
            if not raw:
                break
            consumed += len(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                out.append(line)
    return out

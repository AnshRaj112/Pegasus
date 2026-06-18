# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T07:02:42Z
# --- END GENERATED FILE METADATA ---

"""Build local or GCS streaming delimited inputs (no full-object download)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from pegasus.core.config import Settings
from pegasus.core.local_paths import resolve_local_path_on_disk, to_display_path
from pegasus.schemas.validation import GoogleCloudStorageConfig
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter, create_delimited_adapter
from pegasus.validation.cloud_credentials import load_cloud_connection_or_404
from pegasus.repositories.cloud_connection_repository import CloudConnectionRepository
from pegasus.validation.gcs_object import GcsObjectRef, gcs_object_ref_from_config, parse_gs_uri
from pegasus.validation.local_browse import require_local_path_access


@dataclass(slots=True)
class ResolvedDelimitedInput:
    adapter: FileDelimitedAdapter | GcsDelimitedAdapter
    display_name: str
    is_cloud: bool


async def coerce_cloud_storage_reference(
    session: AsyncSession,
    *,
    label: str,
    path: str | None,
    cloud: GoogleCloudStorageConfig | None,
) -> tuple[GoogleCloudStorageConfig | None, str | None]:
    """Normalize local paths vs GCS URIs into ``(cloud_config, local_path)``."""
    if cloud is not None:
        resolved = await resolve_cloud_config_with_saved_connection(cloud, session=session)
        parsed = parse_gs_uri(path or "")
        if parsed is not None:
            bucket, object_name = parsed
            updates: dict[str, object] = {}
            if not (resolved.bucket or "").strip():
                updates["bucket"] = bucket
            if object_name and not resolved.object_name.strip():
                updates["object_name"] = object_name
            if updates:
                resolved = resolved.model_copy(update=updates)
        return resolved, None

    text = (path or "").strip()
    if not text:
        return None, None

    parsed = parse_gs_uri(text)
    if parsed is None:
        return None, text

    bucket, object_name = parsed
    if not object_name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"{label.capitalize()} GCS URI must include an object path: {text!r}",
        )

    saved = await CloudConnectionRepository.get_active_connection_by_bucket(session, bucket)
    if saved is not None:
        return (
            await resolve_cloud_config_with_saved_connection(
                GoogleCloudStorageConfig(
                    bucket=bucket,
                    object_name=object_name,
                    connection_id=saved.id,
                    project_id=(saved.project_id or "").strip() or None,
                ),
                session=session,
            ),
            None,
        )

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail=(
            f"{label.capitalize()} path {text!r} is a Google Cloud Storage URI. "
            f"Send {label}_cloud with credentials_json or connection_id, or save an admin "
            f"cloud connection for bucket {bucket!r}."
        ),
    )


def _inline_credentials_usable(raw: str | None) -> str | None:
    """Return *raw* when it is non-empty valid JSON; otherwise None."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return text


async def resolve_cloud_config_with_saved_connection(
    cloud: GoogleCloudStorageConfig,
    *,
    session: AsyncSession,
) -> GoogleCloudStorageConfig:
    if cloud.connection_id is None:
        return cloud
    saved = await load_cloud_connection_or_404(session, cloud.connection_id)
    inline = _inline_credentials_usable(cloud.credentials_json)
    saved_creds = (saved.credentials_json or "").strip()
    credentials_json = inline or saved_creds
    if not credentials_json:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Saved cloud connection {saved.name!r} has no credentials. "
                "Update the connection in Admin with a valid service account JSON key."
            ),
        )
    return GoogleCloudStorageConfig(
        provider="google-cloud-storage",
        bucket=(cloud.bucket or "").strip() or str(saved.bucket).strip(),
        object_name=cloud.object_name,
        credentials_json=credentials_json,
        connection_id=cloud.connection_id,
        project_id=(cloud.project_id or "").strip() or (str(saved.project_id).strip() if saved.project_id else None) or None,
    )


async def ensure_resolved_cloud_config(
    session: AsyncSession,
    cloud: GoogleCloudStorageConfig | None,
) -> GoogleCloudStorageConfig | None:
    """Load saved credentials whenever *connection_id* is set."""
    if cloud is None or cloud.connection_id is None:
        return cloud
    if _inline_credentials_usable(cloud.credentials_json):
        return cloud
    return await resolve_cloud_config_with_saved_connection(cloud, session=session)


def resolve_delimited_input(
    *,
    settings: Settings,
    label: str,
    path: str | None,
    cloud: GoogleCloudStorageConfig | None,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
) -> ResolvedDelimitedInput:
    """Return a streaming delimited adapter for a local path or GCS object."""
    if cloud is not None:
        try:
            ref = gcs_object_ref_from_config(cloud)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        adapter = create_delimited_adapter(
            path=None,
            ref=ref,
            delimiter=delimiter,
            has_header=has_header,
            skip_rows=skip_rows,
        )
        return ResolvedDelimitedInput(adapter=adapter, display_name=ref.uri, is_cloud=True)

    if path is None or not path.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"{label.capitalize()} path or cloud reference is required",
        )
    require_local_path_access(settings)
    resolved = resolve_local_path_on_disk(path, settings, must_be_file=True)
    adapter = create_delimited_adapter(
        path=resolved,
        ref=None,
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=skip_rows,
    )
    return ResolvedDelimitedInput(
        adapter=adapter,
        display_name=Path(to_display_path(resolved, settings)).name or resolved.name,
        is_cloud=False,
    )


def delimited_input_from_meta(
    meta: dict[str, object],
    *,
    side: str,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
) -> ResolvedDelimitedInput | None:
    cloud_raw = meta.get(f"{side}_cloud")
    path_raw = meta.get(f"{side}_path")
    if isinstance(cloud_raw, dict):
        from pegasus.validation.gcs_object import gcs_object_ref_from_meta

        ref = gcs_object_ref_from_meta(cloud_raw)
        adapter = create_delimited_adapter(
            path=None,
            ref=ref,
            delimiter=delimiter,
            has_header=has_header,
            skip_rows=skip_rows,
        )
        return ResolvedDelimitedInput(adapter=adapter, display_name=ref.uri, is_cloud=True)
    if path_raw:
        path_str = str(path_raw).strip()
        parsed = parse_gs_uri(path_str)
        if parsed is not None:
            bucket, object_name = parsed
            if bucket and object_name:
                creds_raw = meta.get(f"{side}_cloud_credentials_json") or meta.get("credentials_json")
                if isinstance(creds_raw, str) and creds_raw.strip():
                    ref = gcs_object_ref_from_meta(
                        {
                            "bucket": bucket,
                            "object_name": object_name,
                            "credentials_json": creds_raw,
                            "project_id": meta.get("project_id"),
                        }
                    )
                else:
                    raise ValueError(
                        f"Job metadata has GCS path {path_str!r} but no {side}_cloud credentials"
                    )
                adapter = create_delimited_adapter(
                    path=None,
                    ref=ref,
                    delimiter=delimiter,
                    has_header=has_header,
                    skip_rows=skip_rows,
                )
                return ResolvedDelimitedInput(adapter=adapter, display_name=ref.uri, is_cloud=True)
        path = Path(path_str).resolve()
        adapter = create_delimited_adapter(
            path=path,
            ref=None,
            delimiter=delimiter,
            has_header=has_header,
            skip_rows=skip_rows,
        )
        return ResolvedDelimitedInput(adapter=adapter, display_name=path.name, is_cloud=False)
    return None

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:42:20Z
# --- END GENERATED FILE METADATA ---

"""Resolve GCS credentials from inline JSON or saved cloud connections."""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from pegasus.models.cloud_connection import CloudConnection
from pegasus.repositories.cloud_connection_repository import CloudConnectionRepository


def resolve_cloud_credentials(raw_json: str) -> dict[str, object]:
    text = (raw_json or "").strip()
    if not text:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cloud credentials are missing. Provide credentials_json, a saved connection_id, "
                "or configure an admin cloud connection for this bucket."
            ),
        )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cloud credential payload must be valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cloud credential payload must be a JSON object",
        )
    return parsed


async def load_cloud_connection_or_404(
    session: AsyncSession,
    connection_id: uuid.UUID,
) -> CloudConnection:
    row = await CloudConnectionRepository.get_connection(session, connection_id)
    if row is None or not row.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Saved cloud connection not found")
    return row


async def resolve_gcs_auth(
    session: AsyncSession,
    *,
    bucket: str | None,
    project_id: str | None,
    credentials_json: str | None,
    connection_id: uuid.UUID | None,
    allow_empty_bucket: bool = False,
) -> tuple[str, str | None, dict[str, object]]:
    """Return (bucket, project_id, credentials_info) for GCS API calls."""
    resolved_bucket = (bucket or "").strip()
    resolved_project = (project_id or "").strip() or None
    resolved_json = (credentials_json or "").strip()

    if connection_id is not None:
        saved = await load_cloud_connection_or_404(session, connection_id)
        if not resolved_bucket:
            resolved_bucket = (saved.bucket or "").strip()
        if not resolved_project:
            resolved_project = (saved.project_id or "").strip() or None
        if not resolved_json:
            resolved_json = saved.credentials_json

    info = resolve_cloud_credentials(resolved_json)
    if not resolved_bucket and not allow_empty_bucket:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cloud bucket is required")
    return resolved_bucket, resolved_project, info

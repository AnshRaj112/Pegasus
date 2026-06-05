# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-04T06:59:09Z
# --- END GENERATED FILE METADATA ---

"""Admin APIs to manage reusable cloud connection profiles."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status

from pegasus.api.deps import DbSession
from pegasus.api.v1.admin_auth import get_current_admin_user
from pegasus.models.cloud_connection import CloudConnection
from pegasus.repositories.cloud_connection_repository import CloudConnectionRepository
from pegasus.schemas.cloud_connection import (
    CloudConnectionCreateRequest,
    CloudConnectionResponse,
    CloudConnectionUpdateRequest,
)

router = APIRouter(prefix="/admin/cloud-connections", tags=["admin"])


def _to_response(model: CloudConnection) -> CloudConnectionResponse:
    return CloudConnectionResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        bucket=model.bucket,
        project_id=model.project_id,
        active=model.active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("", response_model=list[CloudConnectionResponse], dependencies=[Depends(get_current_admin_user)])
async def list_cloud_connections(session: DbSession) -> list[CloudConnectionResponse]:
    rows = await CloudConnectionRepository.list_connections(session)
    return [_to_response(r) for r in rows]


@router.post("", response_model=CloudConnectionResponse, dependencies=[Depends(get_current_admin_user)])
async def create_cloud_connection(
    session: DbSession,
    body: Annotated[CloudConnectionCreateRequest, Body()],
) -> CloudConnectionResponse:
    exists = await CloudConnectionRepository.get_connection_by_name(session, body.name)
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Connection name already exists.")
    row = CloudConnection(
        name=body.name.strip(),
        provider=body.provider.strip() or "google-cloud-storage",
        bucket=body.bucket.strip(),
        project_id=(body.project_id or "").strip() or None,
        credentials_json=body.credentials_json,
        active=bool(body.active),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_response(row)


@router.patch(
    "/{connection_id}",
    response_model=CloudConnectionResponse,
    dependencies=[Depends(get_current_admin_user)],
)
async def update_cloud_connection(
    session: DbSession,
    connection_id: uuid.UUID,
    body: Annotated[CloudConnectionUpdateRequest, Body()],
) -> CloudConnectionResponse:
    row = await CloudConnectionRepository.get_connection(session, connection_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    if body.name is not None:
        next_name = body.name.strip()
        exists = await CloudConnectionRepository.get_connection_by_name(session, next_name)
        if exists is not None and exists.id != row.id:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Connection name already exists.")
        row.name = next_name
    if body.provider is not None:
        row.provider = body.provider.strip() or "google-cloud-storage"
    if body.bucket is not None:
        row.bucket = body.bucket.strip()
    if body.project_id is not None:
        row.project_id = (body.project_id or "").strip() or None
    if body.credentials_json is not None:
        row.credentials_json = body.credentials_json
    if body.active is not None:
        row.active = bool(body.active)
    await session.commit()
    await session.refresh(row)
    return _to_response(row)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_admin_user)])
async def delete_cloud_connection(session: DbSession, connection_id: uuid.UUID) -> None:
    row = await CloudConnectionRepository.get_connection(session, connection_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    await session.delete(row)
    await session.commit()

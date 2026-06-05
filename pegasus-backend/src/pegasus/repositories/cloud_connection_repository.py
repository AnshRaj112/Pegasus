# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-04T06:59:09Z
# --- END GENERATED FILE METADATA ---

"""Database access helpers for cloud credential profiles."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pegasus.models.cloud_connection import CloudConnection


class CloudConnectionRepository:
    @staticmethod
    async def list_connections(session: AsyncSession) -> list[CloudConnection]:
        stmt = select(CloudConnection).order_by(CloudConnection.updated_at.desc())
        rows = await session.execute(stmt)
        return list(rows.scalars().all())

    @staticmethod
    async def get_connection(session: AsyncSession, connection_id: uuid.UUID) -> CloudConnection | None:
        stmt = select(CloudConnection).where(CloudConnection.id == connection_id)
        row = await session.execute(stmt)
        return row.scalar_one_or_none()

    @staticmethod
    async def get_connection_by_name(session: AsyncSession, name: str) -> CloudConnection | None:
        stmt = select(CloudConnection).where(CloudConnection.name == name.strip())
        row = await session.execute(stmt)
        return row.scalar_one_or_none()


# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:50:11Z
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

    @staticmethod
    async def get_active_connection_by_bucket(
        session: AsyncSession,
        bucket: str,
    ) -> CloudConnection | None:
        """Return the most recently updated active connection for *bucket*."""
        target = (bucket or "").strip()
        if not target:
            return None
        for row in await CloudConnectionRepository.list_connections(session):
            if not row.active:
                continue
            if str(row.bucket).strip() == target:
                return row
        return None


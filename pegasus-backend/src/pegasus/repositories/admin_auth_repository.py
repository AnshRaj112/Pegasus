# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T09:23:50Z
# --- END GENERATED FILE METADATA ---

"""Persistence helpers for admin auth users/sessions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pegasus.models.admin_session import AdminSession
from pegasus.models.admin_user import AdminUser


class AdminAuthRepository:
    @staticmethod
    async def count_users(session: AsyncSession) -> int:
        res = await session.execute(select(func.count(AdminUser.id)))
        return int(res.scalar() or 0)

    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> AdminUser | None:
        res = await session.execute(select(AdminUser).where(AdminUser.email == email.strip().lower()))
        return res.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> AdminUser | None:
        res = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
        return res.scalar_one_or_none()

    @staticmethod
    async def create_user(session: AsyncSession, *, email: str, password_hash: str) -> AdminUser:
        row = AdminUser(email=email.strip().lower(), password_hash=password_hash)
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def create_session(
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> AdminSession:
        row = AdminSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def get_session_by_hash(session: AsyncSession, token_hash: str) -> AdminSession | None:
        res = await session.execute(select(AdminSession).where(AdminSession.token_hash == token_hash))
        return res.scalar_one_or_none()

    @staticmethod
    async def delete_session_by_hash(session: AsyncSession, token_hash: str) -> None:
        await session.execute(delete(AdminSession).where(AdminSession.token_hash == token_hash))

    @staticmethod
    async def delete_expired_sessions(session: AsyncSession, now: datetime) -> None:
        await session.execute(delete(AdminSession).where(AdminSession.expires_at < now))

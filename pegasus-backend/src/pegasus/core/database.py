# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T10:14:13Z
# --- END GENERATED FILE METADATA ---

"""Async SQLAlchemy engine and session factory (PostgreSQL + asyncpg)."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pegasus.core.config import get_settings
from pegasus.core.database_url import (
    postgres_search_path,
    resolve_database_schema,
    resolve_database_url,
)
from pegasus.models.base import Base

_settings = get_settings()
_database_url = resolve_database_url()
_database_schema = resolve_database_schema()

if _database_schema:
    Base.metadata.schema = _database_schema

_connect_args: dict[str, object] = {}
if _database_schema:
    _connect_args["server_settings"] = {
        "search_path": postgres_search_path(_database_schema),
    }

engine = create_async_engine(
    _database_url,
    echo=_settings.debug,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session; caller should ``commit`` when work succeeds."""
    async with AsyncSessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:56:05+05:30
# --- END GENERATED FILE METADATA ---

"""Async SQLAlchemy engine and session factory (PostgreSQL + asyncpg)."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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


def create_isolated_async_sessionmaker(
    *,
    echo: bool | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Return a dedicated engine + session factory for ``asyncio.run()`` callers.

    Validation workers call ``asyncio.run()`` after each job. Reusing the module-level
    async engine across closed event loops leaves asyncpg connections bound to the
    wrong loop, so worker-side persistence must use a fresh engine per run.
    """
    settings = get_settings()
    database_url = resolve_database_url()
    database_schema = resolve_database_schema()
    connect_args: dict[str, object] = {}
    if database_schema:
        connect_args["server_settings"] = {
            "search_path": postgres_search_path(database_schema),
        }
    isolated_engine = create_async_engine(
        database_url,
        echo=settings.debug if echo is None else echo,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    session_factory = async_sessionmaker(
        isolated_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return isolated_engine, session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session; caller should ``commit`` when work succeeds."""
    async with AsyncSessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()

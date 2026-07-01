# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:53:09Z
# --- END GENERATED FILE METADATA ---

"""Alembic environment (async SQLAlchemy + asyncpg)."""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure `pegasus` is importable when running `alembic` from repo root
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pegasus.core.database_url import (  # noqa: E402
    postgres_search_path,
    resolve_database_schema,
    resolve_database_url,
)
from pegasus.models import Base  # noqa: E402
from pegasus.models import mismatch_report as _mismatch_report  # noqa: E402, F401
from pegasus.models import validation_run as _validation_run  # noqa: E402, F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_schema = resolve_database_schema()
if _schema:
    Base.metadata.schema = _schema

target_metadata = Base.metadata


def get_database_url() -> str:
    return resolve_database_url()


def _configure_context(**kwargs: object) -> None:
    if _schema:
        kwargs.setdefault("version_table_schema", _schema)
    context.configure(**kwargs)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL only)."""
    url = get_database_url()
    _configure_context(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    _configure_context(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        if _schema:
            connection.execute(text(f"SET search_path TO {postgres_search_path(_schema)}"))
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to PostgreSQL via asyncpg)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

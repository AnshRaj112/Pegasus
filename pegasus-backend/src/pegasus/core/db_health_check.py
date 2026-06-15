# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:44:13Z
# --- END GENERATED FILE METADATA ---

"""Database health check utility for startup verification."""

from __future__ import annotations

import logging

from sqlalchemy import text

from pegasus.core.database import engine
from pegasus.core.database_url import resolve_database_schema, resolve_database_url

logger = logging.getLogger(__name__)


def format_database_target() -> str:
    """Human-readable target (no password): ``user@host:port/db (schema: …)``."""
    from sqlalchemy.engine import make_url

    raw = resolve_database_url()
    # make_url expects a sync driver name
    sync_url = raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    url = make_url(sync_url)
    host = url.host or "localhost"
    port = url.port or 5432
    database = url.database or "postgres"
    user = url.username or "?"
    label = f"{user}@{host}:{port}/{database}"
    schema = resolve_database_schema()
    if schema:
        label += f" (schema: {schema})"
    return label


async def check_postgres_connection() -> bool:
    """Test the runtime database connection using the app engine."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.debug("Database connection check failed", exc_info=True)
        return False


async def log_database_connection_status() -> bool:
    """Log and print whether PostgreSQL is reachable (called at app startup)."""
    target = format_database_target()
    ok = await check_postgres_connection()
    if ok:
        message = f"Database connection: SUCCESS — {target}"
        logger.info(message)
    else:
        message = f"Database connection: FAILED — {target}"
        logger.error(message)
    print(message, flush=True)
    return ok

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T06:13:44Z
# --- END GENERATED FILE METADATA ---

"""Resolve SQLAlchemy async URL and PostgreSQL schema from env / dotenv."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from pegasus.core.config import DOTENV_FILES_LOADED, get_settings


def _parse_dotenv_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _merged_dotenv() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in DOTENV_FILES_LOADED:
        merged.update(_parse_dotenv_file(path))
    return merged


_dotenv_cache: dict[str, str] | None = None


def _dotenv() -> dict[str, str]:
    global _dotenv_cache
    if _dotenv_cache is None:
        _dotenv_cache = _merged_dotenv()
    return _dotenv_cache


def clear_dotenv_cache() -> None:
    """Reset cached dotenv reads (for tests)."""
    global _dotenv_cache
    _dotenv_cache = None


def _lookup_env(name: str) -> str | None:
    if name in os.environ:
        return os.environ[name]
    return _dotenv().get(name)


def postgres_search_path(schema: str) -> str:
    """PostgreSQL ``search_path`` value (quoted schema + public)."""
    escaped = schema.replace('"', '""')
    return f'"{escaped}",public'


def resolve_database_schema() -> str | None:
    """Schema name from ``DB_SCHEMA`` or ``PEGASUS_DATABASE_SCHEMA`` (dotenv or process env)."""
    raw = _lookup_env("PEGASUS_DATABASE_SCHEMA") or _lookup_env("DB_SCHEMA")
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def build_database_url_from_legacy_vars() -> str | None:
    """Build ``postgresql+asyncpg://…`` from ``DB_USER``, ``DB_PASSWORD``, etc."""
    user = _lookup_env("DB_USER")
    if user is None:
        return None
    password = _lookup_env("DB_PASSWORD") or ""
    host = _lookup_env("DB_HOST") or "localhost"
    port = _lookup_env("DB_PORT") or "5432"
    name = _lookup_env("DB_NAME") or "postgres"
    return (
        f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}"
    )


def resolve_database_url() -> str:
    """Connection URL: shell ``PEGASUS_DATABASE_URL`` > ``DB_*`` vars > Settings default.

  ``PEGASUS_DATABASE_URL`` is read only from the process environment (``export`` /
  ``-e``), not from ``.env``, so ``DB_USER`` / ``DB_HOST`` / … in ``.env`` can be
  used without commenting out a template ``PEGASUS_DATABASE_URL`` line. The URL from
  ``.env`` is still applied via :func:`get_settings` when neither source above applies.
    """
    explicit = os.environ.get("PEGASUS_DATABASE_URL")
    if explicit:
        return explicit
    legacy = build_database_url_from_legacy_vars()
    if legacy:
        return legacy
    return get_settings().database_url

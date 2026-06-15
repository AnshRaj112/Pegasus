# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:43:26Z
# --- END GENERATED FILE METADATA ---

from __future__ import annotations

import pytest

from cryptography.fernet import Fernet

from pegasus.core.config import get_settings
from pegasus.core.database import resolve_database_url
from pegasus.core.db_health_check import format_database_target
from pegasus.core.database_url import (
    clear_dotenv_cache,
    postgres_search_path,
    resolve_database_schema,
)
from pegasus.core.field_encryption import decrypt_value, encrypt_value, get_database_fernet


def _reset_config_cache() -> None:
    get_settings.cache_clear()
    clear_dotenv_cache()
    get_database_fernet.cache_clear()


def test_resolve_database_url_prefers_pegasus_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.setenv("PEGASUS_DATABASE_URL", "postgresql+asyncpg://alice:secret@dbhost:5432/pegasus")

    _reset_config_cache()

    assert resolve_database_url() == "postgresql+asyncpg://alice:secret@dbhost:5432/pegasus"


def test_resolve_database_url_supports_legacy_db_vars(monkeypatch) -> None:
    monkeypatch.setenv("DB_USER", "bob")
    monkeypatch.setenv("DB_PASSWORD", "hunter2")
    monkeypatch.setenv("DB_HOST", "legacy-host")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "legacydb")
    monkeypatch.delenv("PEGASUS_DATABASE_URL", raising=False)

    _reset_config_cache()

    assert resolve_database_url() == "postgresql+asyncpg://bob:hunter2@legacy-host:5433/legacydb"


def test_format_database_target_includes_schema(monkeypatch) -> None:
    monkeypatch.setenv("DB_USER", "bob")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_HOST", "db.example")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "mydb")
    monkeypatch.setenv("DB_SCHEMA", "Pegasus")
    monkeypatch.delenv("PEGASUS_DATABASE_URL", raising=False)

    _reset_config_cache()

    assert format_database_target() == "bob@db.example:5432/mydb (schema: Pegasus)"


def test_resolve_database_schema_from_db_schema(monkeypatch) -> None:
    monkeypatch.setenv("DB_SCHEMA", "Pegasus")
    monkeypatch.delenv("PEGASUS_DATABASE_SCHEMA", raising=False)

    _reset_config_cache()

    assert resolve_database_schema() == "Pegasus"
    assert postgres_search_path("Pegasus") == '"Pegasus",public'


def test_validation_persistence_requires_database_encryption_key(monkeypatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    monkeypatch.setenv("PEGASUS_DATABASE_ENCRYPTION_KEY", "")
    _reset_config_cache()

    with pytest.raises(ValueError, match="PEGASUS_DATABASE_ENCRYPTION_KEY"):
        get_settings()


def test_database_encryption_round_trip(monkeypatch) -> None:
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    monkeypatch.setenv("PEGASUS_DATABASE_ENCRYPTION_KEY", key)
    _reset_config_cache()

    secret = {"bucket": "demo", "object": "source.csv", "nested": [1, 2, 3]}
    token = encrypt_value(secret)

    assert token != str(secret)
    assert decrypt_value(token) == secret
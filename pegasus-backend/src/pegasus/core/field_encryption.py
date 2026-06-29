# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:05:47Z
# --- END GENERATED FILE METADATA ---

"""Application-level encryption helpers for persisted validation metadata."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import Text, TypeDecorator

from pegasus.core.config import get_settings


def _serialize(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"), ensure_ascii=False)


def _deserialize(text: str) -> Any:
    return json.loads(text)


@lru_cache(maxsize=1)
def get_database_fernet() -> Fernet:
    key = (get_settings().database_encryption_key or "").strip()
    if not key:
        raise RuntimeError(
            "PEGASUS_DATABASE_ENCRYPTION_KEY is required when validation persistence is enabled"
        )
    return Fernet(key.encode("utf-8"))


def encrypt_value(value: Any) -> str:
    payload = _serialize(value).encode("utf-8")
    return get_database_fernet().encrypt(payload).decode("ascii")


def decrypt_value(token: Any) -> Any:
    if token is None:
        return None
    if not isinstance(token, str):
        return token
    try:
        plaintext = get_database_fernet().decrypt(token.encode("utf-8"))
    except InvalidToken:
        return token
    return _deserialize(plaintext.decode("utf-8"))


class EncryptedText(TypeDecorator[str | None]):
    """Store a string-like value encrypted in a TEXT column."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        decrypted = decrypt_value(value)
        return decrypted if isinstance(decrypted, str) else str(decrypted)


class EncryptedJSON(TypeDecorator[Any]):
    """Store a JSON-like value encrypted at rest inside a JSONB column."""

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return value
        if not isinstance(value, str):
            return value
        decrypted = decrypt_value(value)
        if isinstance(decrypted, str):
            try:
                return _deserialize(decrypted)
            except Exception:
                return decrypted
        return decrypted
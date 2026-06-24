# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T06:44:56Z
# --- END GENERATED FILE METADATA ---

"""Fast JSON encode/decode with optional orjson."""

from __future__ import annotations

import json
from typing import Any

try:
    import orjson as _orjson  # type: ignore[import-not-found]

    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False
    _orjson = None  # type: ignore[assignment]


def dumps_bytes(obj: Any, *, indent: bool = False) -> bytes:
    """Serialize *obj* to UTF-8 bytes (compact unless *indent* is True)."""
    if _HAS_ORJSON:
        opts = 0
        if indent:
            opts |= _orjson.OPT_INDENT_2  # type: ignore[attr-defined]
        return _orjson.dumps(obj, default=str, option=opts)  # type: ignore[union-attr]
    if indent:
        return json.dumps(obj, default=str, indent=2).encode("utf-8")
    return json.dumps(obj, default=str, separators=(",", ":")).encode("utf-8")


def loads_bytes(data: bytes) -> Any:
    if _HAS_ORJSON:
        return _orjson.loads(data)  # type: ignore[union-attr]
    return json.loads(data.decode("utf-8"))


def loads_str(text: str) -> Any:
    if _HAS_ORJSON:
        return _orjson.loads(text.encode("utf-8"))  # type: ignore[union-attr]
    return json.loads(text)

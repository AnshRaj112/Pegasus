"""Compare CSV cell strings that encode lists, dicts, or tuples (JSON or Python literals)."""

from __future__ import annotations

import ast
import json
from typing import Any

from pegasus.validation.json_compare import json_values_equal


def looks_like_structured_string(text: str) -> bool:
    """Fast check whether *text* might encode a list, dict, or tuple literal."""
    cleaned = str(text).strip()
    return bool(cleaned) and cleaned[0] in "[{("


def try_parse_structured_string(text: str) -> Any | None:
    """Parse *text* when it looks like JSON or a Python literal for a structured value."""
    cleaned = text.strip()
    if not cleaned:
        return None
    if cleaned[0] not in "[{(":
        return None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None
    else:
        if isinstance(parsed, (dict, list)):
            return parsed
        return parsed

    try:
        value = ast.literal_eval(cleaned)
    except (SyntaxError, ValueError):
        return None
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        return value
    return None


def _deep_equal_strict(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
            if len(left) != len(right):
                return False
            return all(_deep_equal_strict(a, b) for a, b in zip(left, right, strict=False))
        return False
    if isinstance(left, dict):
        if list(left.keys()) != list(right.keys()):
            return False
        return all(_deep_equal_strict(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)):
        if len(left) != len(right):
            return False
        return all(_deep_equal_strict(a, b) for a, b in zip(left, right, strict=False))
    if isinstance(left, set):
        if len(left) != len(right):
            return False
        return all(item in right for item in left)
    return left == right


def _normalize_for_order_insensitive(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize_for_order_insensitive(item) for item in value]
    if isinstance(value, list):
        return [_normalize_for_order_insensitive(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_for_order_insensitive(val) for key, val in value.items()}
    return value


def structured_values_equal(left: Any, right: Any, *, order_sensitive: bool) -> bool:
    """Return True when parsed structured values match under the chosen ordering rules."""
    if order_sensitive:
        return _deep_equal_strict(left, right)
    return json_values_equal(
        _normalize_for_order_insensitive(left),
        _normalize_for_order_insensitive(right),
    )


def structured_strings_equal(
    left: Any,
    right: Any,
    *,
    order_sensitive: bool,
) -> bool:
    """Compare two cell values that may be plain text or structured literals."""
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False

    left_s = str(left).strip()
    right_s = str(right).strip()
    if left_s == right_s:
        return True

    left_parsed = try_parse_structured_string(left_s)
    right_parsed = try_parse_structured_string(right_s)
    if left_parsed is not None and right_parsed is not None:
        return structured_values_equal(left_parsed, right_parsed, order_sensitive=order_sensitive)
    return False

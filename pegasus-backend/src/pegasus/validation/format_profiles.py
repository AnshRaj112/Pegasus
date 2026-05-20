"""Heuristic column format inference and mapping compatibility checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EU_DASH_DATE = re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$")
_US_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_ISO_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_PHONE = re.compile(r"^\+?[\d\s().-]{7,20}$")
_INT = re.compile(r"^-?\d+$")
_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")
_BOOL = re.compile(r"^(true|false|yes|no|0|1)$", re.IGNORECASE)


class FormatKind(StrEnum):
    EMAIL = "email"
    ISO_DATE = "iso_date"
    EU_DASH_DATE = "eu_dash_date"
    US_DATE = "us_date"
    DATETIME = "datetime"
    INTEGER = "integer"
    DECIMAL = "decimal"
    PHONE = "phone"
    UUID = "uuid"
    BOOLEAN = "boolean"
    TEXT = "text"
    EMPTY = "empty"
    UNKNOWN = "unknown"


# Formats that may compare as equivalent with care (still warn on cross-family).
_COMPATIBLE_GROUPS: tuple[frozenset[FormatKind], ...] = (
    frozenset({FormatKind.INTEGER, FormatKind.DECIMAL}),
)


@dataclass(frozen=True, slots=True)
class FormatProfile:
    kind: FormatKind
    confidence: float
    sample_size: int
    example: str | None = None


def _classify_value(raw: str) -> FormatKind:
    s = raw.strip()
    if not s:
        return FormatKind.EMPTY
    if _EMAIL.match(s):
        return FormatKind.EMAIL
    if _UUID.match(s):
        return FormatKind.UUID
    if _ISO_DATETIME.match(s):
        return FormatKind.DATETIME
    if _ISO_DATE.match(s):
        return FormatKind.ISO_DATE
    if _EU_DASH_DATE.match(s):
        return FormatKind.EU_DASH_DATE
    if _US_DATE.match(s):
        return FormatKind.US_DATE
    if _BOOL.match(s):
        return FormatKind.BOOLEAN
    if _INT.match(s):
        return FormatKind.INTEGER
    if _DECIMAL.match(s):
        return FormatKind.DECIMAL
    if _PHONE.match(s) and sum(c.isdigit() for c in s) >= 7:
        return FormatKind.PHONE
    return FormatKind.UNKNOWN


def infer_format(values: Sequence[str], *, min_confidence: float = 0.6) -> FormatProfile:
    """Infer the dominant format from non-empty string samples."""
    non_empty = [v.strip() for v in values if v is not None and str(v).strip()]
    if not non_empty:
        return FormatProfile(FormatKind.EMPTY, 1.0, 0, None)

    counts: dict[FormatKind, int] = {}
    for raw in non_empty:
        kind = _classify_value(str(raw))
        if kind == FormatKind.EMPTY:
            continue
        counts[kind] = counts.get(kind, 0) + 1

    if not counts:
        return FormatProfile(FormatKind.TEXT, 0.5, len(non_empty), non_empty[0][:80])

    total = sum(counts.values())
    kind, count = max(counts.items(), key=lambda kv: kv[1])
    confidence = count / total
    example = next((str(v) for v in non_empty if _classify_value(str(v)) == kind), non_empty[0])

    if confidence < min_confidence:
        return FormatProfile(FormatKind.UNKNOWN, confidence, total, example[:80])

    return FormatProfile(kind, confidence, total, example[:80] if example else None)


def formats_compatible(source: FormatKind, target: FormatKind) -> tuple[bool, str | None]:
    """Return whether two inferred formats are safe to map for validation."""
    if source == target:
        return True, None
    if source == FormatKind.EMPTY or target == FormatKind.EMPTY:
        return True, "One side has no sample values; format could not be verified."
    if source == FormatKind.UNKNOWN or target == FormatKind.UNKNOWN:
        return True, "At least one column has mixed or unrecognized values."
    if source == FormatKind.TEXT or target == FormatKind.TEXT:
        return True, "Free-text column; no strict format enforced."

    for group in _COMPATIBLE_GROUPS:
        if source in group and target in group:
            return True, f"Numeric family match ({source.value} / {target.value})."

    date_kinds = {FormatKind.ISO_DATE, FormatKind.EU_DASH_DATE, FormatKind.US_DATE}
    if source in date_kinds and target in date_kinds:
        # Treat ISO date as distinct (ISO vs US/EU are not considered safely compatible).
        if source == FormatKind.ISO_DATE or target == FormatKind.ISO_DATE:
            return (
                False,
                f"Format mismatch: source {source.value}, target {target.value}.",
            )
        return True, f"Date family match ({source.value} / {target.value}); values compare by calendar date."
    if {source, target} == {FormatKind.ISO_DATE, FormatKind.DATETIME} or {
        source,
        target,
    } == {FormatKind.US_DATE, FormatKind.DATETIME}:
        return (
            False,
            f"Date granularity differs: source {source.value}, target {target.value}.",
        )

    return (
        False,
        f"Format mismatch: source {source.value}, target {target.value}.",
    )


def check_mapping_format(
    *,
    source_column: str,
    target_column: str,
    source_values: Sequence[str],
    target_values: Sequence[str],
) -> dict[str, object]:
    src_profile = infer_format(source_values)
    tgt_profile = infer_format(target_values)
    compatible, message = formats_compatible(src_profile.kind, tgt_profile.kind)
    return {
        "source_column": source_column,
        "target_column": target_column,
        "source_format": src_profile.kind.value,
        "target_format": tgt_profile.kind.value,
        "source_confidence": round(src_profile.confidence, 3),
        "target_confidence": round(tgt_profile.confidence, 3),
        "compatible": compatible,
        "message": message,
        "source_example": src_profile.example,
        "target_example": tgt_profile.example,
    }

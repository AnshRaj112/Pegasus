"""Per-column compare rules from mapping configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from pegasus.validation.fixed_width_dates import normalize_strptime_format, parse_fixed_width_date
from pegasus.validation.value_compare import try_parse_calendar_date, values_equal_for_validation

Side = Literal["source", "target"]

_COMPARE_MODES = frozenset({"auto", "text", "date", "phone", "digits"})


@dataclass(frozen=True, slots=True)
class CompareRule:
    compare_mode: str = "auto"
    source_date_format: str | None = None
    target_date_format: str | None = None
    source_strip_prefix: str | None = None
    target_strip_prefix: str | None = None
    source_regex_pattern: str | None = None
    source_regex_replacement: str = ""
    target_regex_pattern: str | None = None
    target_regex_replacement: str = ""


def rule_from_mapping(mapping: object) -> CompareRule | None:
    """Return a compare rule when the mapping overrides default comparison."""
    mode = (getattr(mapping, "compare_mode", None) or "auto").strip().lower()
    if mode not in _COMPARE_MODES:
        mode = "auto"
    rule = CompareRule(
        compare_mode=mode,
        source_date_format=_empty_as_none(getattr(mapping, "source_date_format", None)),
        target_date_format=_empty_as_none(getattr(mapping, "target_date_format", None)),
        source_strip_prefix=_empty_as_none(getattr(mapping, "source_strip_prefix", None)),
        target_strip_prefix=_empty_as_none(getattr(mapping, "target_strip_prefix", None)),
        source_regex_pattern=_empty_as_none(getattr(mapping, "source_regex_pattern", None)),
        source_regex_replacement=getattr(mapping, "source_regex_replacement", None) or "",
        target_regex_pattern=_empty_as_none(getattr(mapping, "target_regex_pattern", None)),
        target_regex_replacement=getattr(mapping, "target_regex_replacement", None) or "",
    )
    if not mapping_has_custom_compare(rule):
        return None
    return rule


def mapping_has_custom_compare(rule: CompareRule) -> bool:
    if rule.compare_mode != "auto":
        return True
    return any(
        (
            rule.source_date_format,
            rule.target_date_format,
            rule.source_strip_prefix,
            rule.target_strip_prefix,
            rule.source_regex_pattern,
            rule.target_regex_pattern,
        )
    )


def build_rules_by_source_column(mappings: list[object] | None) -> dict[str, CompareRule]:
    """Map source column name → compare rule (after target rename, columns share source names)."""
    out: dict[str, CompareRule] = {}
    for mapping in mappings or []:
        rule = rule_from_mapping(mapping)
        if rule is not None:
            out[getattr(mapping, "source_column")] = rule
    return out


def normalize_cell_value(value: Any, rule: CompareRule | None, *, side: Side) -> Any:
    """Normalize one cell before equality check."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if rule is None:
        return text

    prefix = rule.source_strip_prefix if side == "source" else rule.target_strip_prefix
    if prefix and text.startswith(prefix):
        text = text[len(prefix) :].strip()

    pattern = rule.source_regex_pattern if side == "source" else rule.target_regex_pattern
    replacement = (
        rule.source_regex_replacement if side == "source" else rule.target_regex_replacement
    )
    if pattern:
        text = re.sub(pattern, replacement or "", text).strip()

    mode = rule.compare_mode
    if mode in {"phone", "digits"}:
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits or None

    if mode == "date":
        fmt = rule.source_date_format if side == "source" else rule.target_date_format
        if fmt:
            try:
                return parse_fixed_width_date(text, normalize_strptime_format(fmt))
            except ValueError:
                pass
        parsed = try_parse_calendar_date(text)
        return parsed if parsed is not None else text

    if mode == "text":
        return text

    # auto
    return text


def values_equal_with_rule(left: Any, right: Any, rule: CompareRule | None) -> bool:
    """Compare two cells using optional per-column rules."""
    if rule is None:
        return values_equal_for_validation(left, right)

    if left is None and right is None:
        return True
    if left is None or right is None:
        return False

    left_n = normalize_cell_value(left, rule, side="source")
    right_n = normalize_cell_value(right, rule, side="target")

    if isinstance(left_n, date) and isinstance(right_n, date):
        return left_n == right_n

    if rule.compare_mode == "auto":
        return values_equal_for_validation(left, right)

    return left_n == right_n


def _empty_as_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None

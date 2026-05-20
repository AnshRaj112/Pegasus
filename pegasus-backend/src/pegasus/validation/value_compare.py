"""Semantic value equality for CSV validation (cross-format dates, etc.)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from pegasus.validation.compare_rules import CompareRule

# Common calendar-date layouts seen in reconciliation feeds.
_CALENDAR_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%Y%m%d",
)


def try_parse_calendar_date(value: str | None) -> date | None:
    """Parse *value* as a calendar date when it matches a known pattern."""
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    for fmt in _CALENDAR_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def values_equal_for_validation(
    left: Any,
    right: Any,
    rule: CompareRule | None = None,
) -> bool:
    """Return True when two cell values should be treated as equal for validation."""
    if rule is not None:
        from pegasus.validation.compare_rules import values_equal_with_rule

        return values_equal_with_rule(left, right, rule)

    if left is None and right is None:
        return True
    if left is None or right is None:
        return False

    left_s = str(left).strip()
    right_s = str(right).strip()
    if left_s == right_s:
        return True

    left_date = try_parse_calendar_date(left_s)
    right_date = try_parse_calendar_date(right_s)
    if left_date is not None and right_date is not None:
        return left_date == right_date

    return False


def _polars_date_expr(column: pl.Expr) -> pl.Expr:
    """Best-effort calendar-date parse; null when the string is not a known date layout."""
    base = column.cast(pl.String).str.strip_chars()
    return pl.coalesce(
        [
            base.str.strptime(pl.Date, fmt, strict=False)
            for fmt in _CALENDAR_DATE_FORMATS
        ]
    )


def _polars_apply_strip_prefix(column: pl.Expr, prefix: str | None) -> pl.Expr:
    base = column.cast(pl.String).str.strip_chars()
    if not prefix:
        return base
    return pl.when(base.str.starts_with(prefix)).then(base.str.slice(len(prefix))).otherwise(base)


def _polars_apply_regex(column: pl.Expr, pattern: str | None, replacement: str) -> pl.Expr:
    base = column
    if not pattern:
        return base
    return base.str.replace_all(pattern, replacement or "", literal=False)


def _polars_digits_expr(column: pl.Expr) -> pl.Expr:
    return column.cast(pl.String).str.strip_chars().str.replace_all(r"[^\d]", "", literal=False)


def polars_values_differ_expr(
    source_col: str,
    target_col: str,
    rule: CompareRule | None = None,
) -> pl.Expr:
    """Polars expression that is True when source/target should count as a value mismatch."""
    if rule is None or rule.compare_mode == "auto":
        source = pl.col(source_col)
        target = pl.col(target_col)

        source_s = source.cast(pl.String).str.strip_chars().fill_null("__NULL__")
        target_s = target.cast(pl.String).str.strip_chars().fill_null("__NULL__")
        string_equal = source_s == target_s

        source_date = _polars_date_expr(source)
        target_date = _polars_date_expr(target)
        date_equal = source_date.is_not_null() & target_date.is_not_null() & (source_date == target_date)

        return ~(string_equal | date_equal)

    mode = rule.compare_mode
    src = _polars_apply_regex(
        _polars_apply_strip_prefix(pl.col(source_col), rule.source_strip_prefix),
        rule.source_regex_pattern,
        rule.source_regex_replacement,
    )
    tgt = _polars_apply_regex(
        _polars_apply_strip_prefix(pl.col(target_col), rule.target_strip_prefix),
        rule.target_regex_pattern,
        rule.target_regex_replacement,
    )

    if mode in {"phone", "digits"}:
        return _polars_digits_expr(src).fill_null("__NULL__") != _polars_digits_expr(tgt).fill_null("__NULL__")

    if mode == "text":
        return src.fill_null("__NULL__") != tgt.fill_null("__NULL__")

    if mode == "date":
        src_dates = _polars_date_expr_with_format(src, rule.source_date_format)
        tgt_dates = _polars_date_expr_with_format(tgt, rule.target_date_format)
        both_parsed = src_dates.is_not_null() & tgt_dates.is_not_null()
        parsed_equal = both_parsed & (src_dates == tgt_dates)
        string_equal = src.fill_null("__NULL__") == tgt.fill_null("__NULL__")
        return ~(string_equal | parsed_equal)

    return polars_values_differ_expr(source_col, target_col, rule=None)


def _polars_date_expr_with_format(column: pl.Expr, fmt: str | None) -> pl.Expr:
    from pegasus.validation.fixed_width_dates import normalize_strptime_format

    base = column.cast(pl.String).str.strip_chars()
    if fmt:
        normalized = normalize_strptime_format(fmt)
        parsed = base.str.strptime(pl.Date, normalized, strict=False)
        return pl.coalesce([parsed, _polars_date_expr(column)])
    return _polars_date_expr(column)

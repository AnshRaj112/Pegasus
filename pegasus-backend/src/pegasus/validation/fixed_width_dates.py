# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T07:31:54Z
# --- END GENERATED FILE METADATA ---

"""Date parsing and cross-format equality for fixed-width field slices."""

from __future__ import annotations

from datetime import date, datetime

from pegasus.validation.comparators.core import _DF, _date_candidates, _dates_equal

_FRIENDLY_TOKENS: tuple[tuple[str, str], ...] = (
    ("YYYY", "%Y"),
    ("YY", "%y"),
    ("DD", "%d"),
    ("MM", "%m"),
    ("MON", "%b"),
    ("MONTH", "%B"),
)


def friendly_to_strptime(fmt: str) -> str:
    """Convert UI-friendly tokens (DD/MM/YYYY) to strptime directives."""
    text = fmt.strip()
    if not text:
        return "%Y-%m-%d"
    if "%" in text:
        return text
    out = text
    for token, directive in _FRIENDLY_TOKENS:
        out = out.replace(token, directive)
    return out


def parse_fixed_width_date(value: str, date_format: str) -> date:
    """Parse a fixed-width date slice using an explicit or friendly format."""
    text = value.strip()
    if not text:
        raise ValueError("empty date value")
    strptime_fmt = friendly_to_strptime(date_format)
    try:
        return datetime.strptime(text, strptime_fmt).date()
    except ValueError:
        candidates = _date_candidates(text)
        if len(candidates) == 1:
            return next(iter(candidates))
        raise ValueError(f"value {text!r} does not match format {date_format!r}") from None


def date_candidates_with_format(value: str, date_format: str | None) -> frozenset[date]:
    """Candidate calendar dates for a slice, honoring an optional explicit format."""
    found = set(_date_candidates(value))
    if date_format:
        try:
            found.add(parse_fixed_width_date(value, date_format))
        except ValueError:
            pass
    return frozenset(found)


def dates_equal_fixed_width(
    source_value: str,
    target_value: str,
    *,
    source_date_format: str | None = None,
    target_date_format: str | None = None,
) -> bool:
    """Return whether two date slices denote the same calendar day.

  When per-side formats are supplied (e.g. DD/MM/YYYY vs MM/DD/YYYY), each
  side is parsed with its format and the results are compared. Otherwise the
  shared auto-detect path from :mod:`comparators.core` is used.
    """
    if source_date_format or target_date_format:
        src_dates = date_candidates_with_format(source_value, source_date_format)
        tgt_dates = date_candidates_with_format(target_value, target_date_format)
        if src_dates and tgt_dates:
            return bool(src_dates & tgt_dates)
    return _dates_equal(source_value, target_value)


def supported_auto_formats() -> tuple[str, ...]:
    """Strptime patterns tried during auto date detection."""
    return _DF

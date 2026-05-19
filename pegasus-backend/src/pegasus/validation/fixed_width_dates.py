"""Date parsing helpers for fixed-width validation."""

from __future__ import annotations

from datetime import date, datetime

# User-friendly tokens → strptime directives (longest first).
_FRIENDLY_TOKENS: tuple[tuple[str, str], ...] = (
    ("YYYY", "%Y"),
    ("yyyy", "%Y"),
    ("YY", "%y"),
    ("yy", "%y"),
    ("DD", "%d"),
    ("dd", "%d"),
    ("MM", "%m"),
    ("mm", "%m"),
    ("HH", "%H"),
    ("hh", "%H"),
    ("SS", "%S"),
    ("ss", "%S"),
)


def normalize_strptime_format(fmt: str) -> str:
    """Convert patterns like ``dd-mm-yyyy`` to strptime form ``%d-%m-%Y``.

    Strings that already contain ``%`` directives are returned unchanged.
    """
    if not fmt:
        return fmt
    s = fmt.strip()
    if not s or "%" in s:
        return s
    out = s
    for token, directive in _FRIENDLY_TOKENS:
        out = out.replace(token, directive)
    return out


def parse_fixed_width_date(value: str, fmt: str) -> date:
    """Parse a sliced date value; ``fmt`` may be strptime or friendly notation."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("empty date value")
    normalized = normalize_strptime_format(fmt)
    if not normalized:
        raise ValueError("date format is required")
    return datetime.strptime(cleaned, normalized).date()

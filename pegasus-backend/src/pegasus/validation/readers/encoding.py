"""Helpers for Polars CSV encoding quirks (lazy scan vs eager read)."""

from __future__ import annotations

from typing import Literal

from pegasus.validation.readers.exceptions import CSVValidationError


def try_lazy_csv_encoding(encoding: str) -> Literal["utf8", "utf8-lossy"] | None:
    """Return Polars lazy-scan encoding, or ``None`` if *encoding* needs eager I/O."""
    key = encoding.strip().lower().replace("_", "-")
    if key in ("utf-8", "utf8"):
        return "utf8"
    if key in ("utf-8-lossy", "utf8-lossy"):
        return "utf8-lossy"
    return None


def normalize_lazy_csv_encoding(encoding: str) -> Literal["utf8", "utf8-lossy"]:
    """Map common spellings to values accepted by :func:`polars.scan_csv`.

    Polars' lazy CSV reader only supports ``utf8`` and ``utf8-lossy``.

    Raises
    ------
    CSVValidationError
        If *encoding* cannot be used with lazy scanning / streaming collection.
    """
    resolved = try_lazy_csv_encoding(encoding)
    if resolved is None:
        raise CSVValidationError(
            "Streaming Polars CSV APIs require encoding utf-8 / utf8 or utf8-lossy "
            f"(got {encoding!r}). Use read_file (eager path) for other encodings, "
            "transcode to UTF-8, or use utf8-lossy for invalid UTF-8 bytes."
        )
    return resolved

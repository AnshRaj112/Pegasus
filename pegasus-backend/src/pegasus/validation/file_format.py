# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-05T09:31:09Z
# --- END GENERATED FILE METADATA ---

"""File format normalization and path-based inference."""

from __future__ import annotations

from pathlib import Path

_AUTO_ALIASES = frozenset({"auto", "detect", "unknown"})
_JSON_ALIASES = frozenset({"json", "ndjson"})
_FIXED_WIDTH_ALIASES = frozenset({"fixed-width", "fixedwidth", "fixed", "fw"})
_COLUMNAR_ALIASES = frozenset({"parquet", "orc", "avro", "excel", "xlsx", "xls"})

_SUFFIX_TO_FORMAT: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "csv",
    ".dat": "csv",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".orc": "orc",
    ".avro": "avro",
    ".xlsx": "excel",
    ".xls": "excel",
    ".json": "json",
    ".ndjson": "json",
}


def normalize_file_format(file_format: str | None) -> str:
    """Return canonical format token for routing."""
    token = (file_format or "csv").strip().lower().replace("_", "-")
    if token in _AUTO_ALIASES:
        return "auto"
    if token in _JSON_ALIASES:
        return "json"
    if token in _FIXED_WIDTH_ALIASES:
        return "fixed-width"
    if token in _COLUMNAR_ALIASES:
        return "excel" if token in {"xlsx", "xls"} else token
    return "csv"


def format_hint_from_suffix(suffix: str) -> str | None:
    """Map a file suffix (e.g. ``.csv``) to a canonical format token, if known."""
    return _SUFFIX_TO_FORMAT.get(suffix.lower())


def infer_file_format_from_path(path: Path, requested: str | None = None) -> str:
    """Infer format from extension when *requested* is auto/csv or missing."""
    fmt = normalize_file_format(requested)
    if fmt not in {"auto", "csv"}:
        return fmt
    mapped = _SUFFIX_TO_FORMAT.get(path.suffix.lower())
    return mapped or "csv"


def is_columnar_format(file_format: str | None) -> bool:
    return normalize_file_format(file_format) in _COLUMNAR_ALIASES


def extensions_for_format(file_format: str | None) -> frozenset[str]:
    fmt = normalize_file_format(file_format)
    if fmt == "json":
        return frozenset({".json", ".ndjson"})
    if fmt == "fixed-width":
        return frozenset({".txt", ".dat", ".fw", ".fixed"})
    if fmt == "parquet":
        return frozenset({".parquet", ".pq"})
    if fmt == "orc":
        return frozenset({".orc"})
    if fmt == "avro":
        return frozenset({".avro"})
    if fmt == "excel":
        return frozenset({".xlsx", ".xls"})
    if fmt == "auto":
        return frozenset(_SUFFIX_TO_FORMAT.keys()) | frozenset({".zip"})
    return frozenset({".csv", ".tsv", ".txt", ".dat"})

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-28T11:56:30Z
# --- END GENERATED FILE METADATA ---

"""File format normalization and path-based inference."""

from __future__ import annotations

from pathlib import Path

_AUTO_ALIASES = frozenset({"auto", "any", "detect", "unknown"})
_JSON_ALIASES = frozenset({"json", "ndjson"})
_FIXED_WIDTH_ALIASES = frozenset({"fixed-width", "fixedwidth", "fixed", "fw"})
_COLUMNAR_ALIASES = frozenset({"parquet", "orc", "avro", "excel", "xlsx", "xls"})

_SUFFIX_TO_FORMAT: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "csv",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".orc": "orc",
    ".avro": "avro",
    ".xlsx": "excel",
    ".xls": "excel",
    ".json": "json",
    ".ndjson": "json",
}

# Content sniff required — may be fixed-width, delimited, or plain text.
_AMBIGUOUS_TABULAR_SUFFIXES = frozenset({".txt", ".dat"})


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


def is_ambiguous_tabular_suffix(suffix: str) -> bool:
    """Return whether the suffix needs content sniff (``.txt``, ``.dat``)."""
    return suffix.lower() in _AMBIGUOUS_TABULAR_SUFFIXES


def infer_file_format_from_path(path: Path, requested: str | None = None) -> str:
    """Infer format from extension when *requested* is auto/csv or missing."""
    fmt = normalize_file_format(requested)
    if fmt not in {"auto", "csv"}:
        return fmt
    mapped = _SUFFIX_TO_FORMAT.get(path.suffix.lower())
    return mapped or "csv"


def is_columnar_format(file_format: str | None) -> bool:
    return normalize_file_format(file_format) in _COLUMNAR_ALIASES


_COMPRESSED_SUFFIXES: tuple[str, ...] = (".gz", ".bz2", ".zip", ".zst")


def object_name_matches_format(name: str, allowed: frozenset[str]) -> bool:
    """Return whether a leaf object name matches *allowed* tabular extensions.

    Uses suffix matching so compressed exports like ``data.csv.gz`` match ``.csv``.
    Extensionless names are allowed (common for large warehouse dumps).
    """
    leaf = name.rstrip("/").split("/")[-1]
    lower = leaf.lower()
    if "." not in lower:
        return True
    for ext in allowed:
        if lower.endswith(ext):
            return True
        for comp in _COMPRESSED_SUFFIXES:
            if lower.endswith(ext + comp):
                return True
    return False


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
        return (
            frozenset(_SUFFIX_TO_FORMAT.keys())
            | _AMBIGUOUS_TABULAR_SUFFIXES
            | frozenset({".zip", ".fw", ".fixed"})
        )
    return frozenset({".csv", ".tsv", ".txt", ".dat"})

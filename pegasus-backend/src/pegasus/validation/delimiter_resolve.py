# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:20:06Z
# --- END GENERATED FILE METADATA ---

"""Resolve API delimiter tokens to the literal separator string."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.flat_file import EmptyDelimiterError, normalize_delimiter
from pegasus.validation.readers.delimiter_detection import (
    detect_delimiter,
    polars_supports_csv_delimiter,
    resolve_shared_auto_delimiter,
)

__all__ = (
    "polars_supports_csv_delimiter",
    "resolve_delimiter_for_paths",
    "resolve_delimiter_token",
)


def resolve_delimiter_token(token: str | None) -> str:
    """Map UI/API tokens (``tab``, ``\\t``, ``auto``) to a separator string.

    Raises :class:`ValueError` when *token* is ``auto``/empty (use
    :func:`resolve_delimiter_for_paths` instead) or invalid.
    """
    raw = (token or "").strip()
    lowered = raw.lower()
    if lowered in {"", "auto", "infer", "detect"}:
        raise ValueError("delimiter is auto; resolve against file paths")
    if lowered in {"tab", "\\t", "\\\\t"}:
        return "\t"
    try:
        return normalize_delimiter(raw)
    except EmptyDelimiterError as exc:
        raise ValueError(str(exc)) from exc


def resolve_delimiter_for_paths(
    token: str | None,
    source_path: Path,
    target_path: Path | None = None,
) -> str:
    """Resolve delimiter for one or two local files (shared auto-detection when paired)."""
    raw = (token or "").strip()
    lowered = raw.lower()
    if lowered in {"", "auto", "infer", "detect"}:
        if target_path is not None:
            result = resolve_shared_auto_delimiter(source_path, target_path)
            return result.delimiter
        result = detect_delimiter(source_path)
        return result.delimiter
    return resolve_delimiter_token(raw)


def resolve_delimiter_for_adapters(
    token: str | None,
    source: object,
    target: object,
) -> str:
    """Resolve delimiter for local paths and/or GCS streaming adapters."""
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter

    raw = (token or "").strip()
    lowered = raw.lower()
    if lowered not in {"", "auto", "infer", "detect"}:
        return resolve_delimiter_token(raw)

    src_path = Path(getattr(source, "path", "source"))
    tgt_path = Path(getattr(target, "path", "target"))
    src_is_gcs = isinstance(source, GcsDelimitedAdapter)
    tgt_is_gcs = isinstance(target, GcsDelimitedAdapter)
    src_lines = source.sample_lines() if src_is_gcs else None
    tgt_lines = target.sample_lines() if tgt_is_gcs else None

    if src_is_gcs or tgt_is_gcs:
        result = resolve_shared_auto_delimiter(
            src_path,
            tgt_path,
            source_lines=src_lines,
            target_lines=tgt_lines,
        )
        return result.delimiter

    if isinstance(source, FileDelimitedAdapter) and isinstance(target, FileDelimitedAdapter):
        return resolve_delimiter_for_paths(token, source.path, target.path)

    if hasattr(source, "path") and hasattr(target, "path"):
        src_p = Path(source.path)
        tgt_p = Path(target.path)
        if src_p.is_file() and tgt_p.is_file():
            return resolve_delimiter_for_paths(token, src_p, tgt_p)

    raise ValueError("Could not resolve delimiter for the provided inputs")

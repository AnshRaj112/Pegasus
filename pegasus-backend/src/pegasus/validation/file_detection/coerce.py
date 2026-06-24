# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:21:21Z
# --- END GENERATED FILE METADATA ---

"""Resolve file_format using detection while preserving API backward compatibility."""

from __future__ import annotations

from pathlib import Path

from pegasus.core.config import Settings
from pegasus.validation.file_detection.pipeline import detect_file
from pegasus.validation.file_format import infer_file_format_from_path, normalize_file_format


def resolve_file_format_with_detection(
    path: Path,
    requested: str | None,
    *,
    settings: Settings | None = None,
) -> tuple[str, list[str]]:
    """Return canonical file_format and optional warnings."""
    fmt = normalize_file_format(requested)
    auto_enabled = settings.validation_auto_detect_format if settings else True

    if fmt != "auto" or not auto_enabled:
        resolved = infer_file_format_from_path(path, requested)
        if fmt != "auto" and auto_enabled:
            report = detect_file(path, user_format_hint=requested)
            if (
                report.suggested_file_format
                and report.suggested_file_format != resolved
                and (report.validation_strategy and report.validation_strategy.confidence >= 70)
            ):
                return resolved, list(report.warnings)
        return resolved, []

    report = detect_file(path, user_format_hint=requested)
    if report.suggested_file_format and (report.validation_strategy or None) and (
        report.validation_strategy.confidence >= 55
    ):
        return normalize_file_format(report.suggested_file_format), list(report.warnings)
    return infer_file_format_from_path(path, requested), list(report.warnings)


def suggest_format_override(path: Path, declared: str | None) -> str | None:
    """When declared format disagrees strongly with content, return suggested override."""
    report = detect_file(path, user_format_hint=declared)
    declared_norm = normalize_file_format(declared)
    if not report.suggested_file_format:
        return None
    if report.suggested_file_format == declared_norm:
        return None
    if report.validation_strategy and report.validation_strategy.confidence >= 75:
        return report.suggested_file_format
    return None


def coerce_local_validate_fields_with_detection(
    source_path: Path,
    target_path: Path,
    file_format: str | None,
    *,
    settings: Settings,
) -> tuple[str, list[str]]:
    """Resolve a single file_format for a local pair using detection when enabled."""
    src_fmt, src_warn = resolve_file_format_with_detection(source_path, file_format, settings=settings)
    tgt_fmt, tgt_warn = resolve_file_format_with_detection(target_path, file_format, settings=settings)
    warnings = src_warn + tgt_warn
    if src_fmt != tgt_fmt:
        raise ValueError(
            f"Source and target file formats differ after detection: source={src_fmt!r}, target={tgt_fmt!r}"
        )
    return src_fmt, warnings

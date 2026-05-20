"""Resolve fixed-width validation settings from API payloads and job meta."""

from __future__ import annotations

from typing import Any

from pegasus.validation.delimiter_tokens import FIXED_WIDTH_DELIMITER, is_fixed_width_delimiter

_FIXED_WIDTH_FORMAT_ALIASES = frozenset({"fixed-width", "fixed_width", "fixedwidth"})

_DRAFT_CONFIG_KEYS = (
    "source_date_start",
    "source_date_end",
    "source_date_format",
    "target_date_start",
    "target_date_end",
    "target_date_format",
)


def normalize_file_format(file_format: str | None) -> str:
    """Return ``csv`` or ``fixed-width``."""
    token = (file_format or "csv").strip().lower().replace("_", "-")
    if token in _FIXED_WIDTH_FORMAT_ALIASES or token == "fixed-width":
        return "fixed-width"
    return "csv"


def is_fixed_width_run(*, file_format: str | None = None, delimiter: str | None = None) -> bool:
    """True when the job should use streaming fixed-width validation (not CSV)."""
    if normalize_file_format(file_format) == "fixed-width":
        return True
    return is_fixed_width_delimiter(delimiter)


def _mapping_value(mappings: list[Any], source_column: str) -> str | None:
    for item in mappings:
        if not isinstance(item, dict):
            continue
        if str(item.get("source_column") or "") != source_column:
            continue
        raw = item.get("target_column")
        if raw is None:
            return None
        return str(raw).strip()
    return None


def fixed_width_config_from_column_mappings(mappings: list[Any] | None) -> dict[str, Any] | None:
    """Rebuild ``fixed_width_config`` from mapping-wizard draft rows."""
    if not mappings:
        return None
    values = {key: _mapping_value(mappings, key) for key in _DRAFT_CONFIG_KEYS}
    if not any(values.values()):
        return None
    try:
        return {
            "source_date_start": int(values["source_date_start"] or 0),
            "source_date_end": int(values["source_date_end"] or 0),
            "source_date_format": values["source_date_format"] or "",
            "target_date_start": int(values["target_date_start"] or 0),
            "target_date_end": int(values["target_date_end"] or 0),
            "target_date_format": values["target_date_format"] or "",
        }
    except (TypeError, ValueError):
        return None


def resolve_fixed_width_config(
    *,
    file_format: str | None,
    delimiter: str | None,
    fixed_width_config: dict[str, Any] | None,
    column_mappings: list[Any] | None = None,
) -> dict[str, Any] | None:
    """Return the config dict to pass to :meth:`ValidationService.validate_fixed_width_pair_sync`."""
    if not is_fixed_width_run(file_format=file_format, delimiter=delimiter):
        return None
    if isinstance(fixed_width_config, dict) and fixed_width_config:
        return dict(fixed_width_config)
    return fixed_width_config_from_column_mappings(column_mappings)


def coerce_local_validate_fields(
    *,
    file_format: str,
    delimiter: str,
    fixed_width_config: dict[str, Any] | None,
    column_mappings: list[Any] | None,
) -> tuple[str, str, dict[str, Any] | None]:
    """Normalize local-path validate request fields for fixed-width runs."""
    if not is_fixed_width_run(file_format=file_format, delimiter=delimiter):
        return file_format, delimiter, fixed_width_config
    resolved = resolve_fixed_width_config(
        file_format="fixed-width",
        delimiter=delimiter,
        fixed_width_config=fixed_width_config,
        column_mappings=column_mappings,
    )
    return "fixed-width", FIXED_WIDTH_DELIMITER, resolved

"""Resolve fixed-width validation settings from API payloads and job meta."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pegasus.validation.delimiter_tokens import (
    FIXED_WIDTH_DELIMITER,
    JSON_DELIMITER,
    is_fixed_width_delimiter,
    is_json_delimiter,
)

_FIXED_WIDTH_FORMAT_ALIASES = frozenset({"fixed-width", "fixed_width", "fixedwidth"})
_JSON_FORMAT_ALIASES = frozenset({"json"})
_COLUMNAR_FORMAT_ALIASES = frozenset({"parquet", "orc", "avro", "excel", "xlsx"})
_AUTO_FORMAT_ALIASES = frozenset({"auto", "detect", "infer"})

_DRAFT_CONFIG_KEYS = (
    "source_date_start",
    "source_date_end",
    "source_date_format",
    "target_date_start",
    "target_date_end",
    "target_date_format",
)


def normalize_file_format(file_format: str | None) -> str:
    """Return canonical format token for routing."""
    token = (file_format or "csv").strip().lower().replace("_", "-")
    if token in _AUTO_FORMAT_ALIASES:
        return "auto"
    if token in _JSON_FORMAT_ALIASES:
        return "json"
    if token in _FIXED_WIDTH_FORMAT_ALIASES or token == "fixed-width":
        return "fixed-width"
    if token in _COLUMNAR_FORMAT_ALIASES or token == "xlsx":
        return "excel" if token == "xlsx" else token
    return "csv"


def is_columnar_run(file_format: str | None = None) -> bool:
    """True when validation should use the columnar (Parquet/ORC/Avro/Excel) path."""
    return normalize_file_format(file_format) in _COLUMNAR_FORMAT_ALIASES


def is_json_run(*, file_format: str | None = None, delimiter: str | None = None) -> bool:
    """True when the job should compare two JSON documents (not CSV / fixed-width)."""
    if normalize_file_format(file_format) == "json":
        return True
    return is_json_delimiter(delimiter)


def is_fixed_width_run(*, file_format: str | None = None, delimiter: str | None = None) -> bool:
    """True when the job should use streaming fixed-width validation (not CSV)."""
    if is_json_run(file_format=file_format, delimiter=delimiter):
        return False
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


def materialize_fixed_width_fields(config: dict[str, Any]) -> dict[str, Any]:
    """Ensure ``fields`` and ``uid_column`` exist (legacy date-only payloads)."""
    cfg = dict(config)
    if cfg.get("fields"):
        return cfg

    uid = str(cfg.get("uid_column") or "name").strip()
    fields: list[dict[str, Any]] = []
    src_ds = cfg.get("source_date_start")
    src_de = cfg.get("source_date_end")
    tgt_ds = cfg.get("target_date_start")
    tgt_de = cfg.get("target_date_end")
    if src_ds is not None and src_de is not None and tgt_ds is not None and tgt_de is not None:
        fields.append({
            "field_name": "dob",
            "source_start": int(src_ds),
            "source_end": int(src_de),
            "target_start": int(tgt_ds),
            "target_end": int(tgt_de),
            "field_type": "date",
            "source_date_format": cfg.get("source_date_format"),
            "target_date_format": cfg.get("target_date_format"),
        })
    join_field = next((f for f in fields if f["field_name"] == uid), None)
    if join_field is None and uid == "name":
        fields = [
            {
                "field_name": "id",
                "source_start": 0,
                "source_end": 5,
                "target_start": 0,
                "target_end": 5,
                "field_type": "text",
            },
            {
                "field_name": "name",
                "source_start": 8,
                "source_end": 28,
                "target_start": 8,
                "target_end": 28,
                "field_type": "text",
            },
            {
                "field_name": "email",
                "source_start": 28,
                "source_end": 58,
                "target_start": 28,
                "target_end": 58,
                "field_type": "text",
            },
            *fields,
        ]
    cfg["fields"] = fields
    cfg["uid_column"] = uid
    if cfg.get("uid_source_start") is None:
        join = next((f for f in fields if f["field_name"] == uid), None)
        if join is not None:
            cfg["uid_source_start"] = join["source_start"]
            cfg["uid_source_end"] = join["source_end"]
            cfg["uid_target_start"] = join["target_start"]
            cfg["uid_target_end"] = join["target_end"]
    return cfg


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
        return materialize_fixed_width_fields(dict(fixed_width_config))
    built = fixed_width_config_from_column_mappings(column_mappings)
    return materialize_fixed_width_fields(built) if built else None


def coerce_local_validate_fields(
    *,
    file_format: str,
    delimiter: str,
    fixed_width_config: dict[str, Any] | None,
    column_mappings: list[Any] | None,
    source_path: Path | None = None,
    target_path: Path | None = None,
    auto_detect: bool = False,
    auto_extract: bool = False,
) -> tuple[str, str, dict[str, Any] | None]:
    """Normalize local-path validate request fields for fixed-width / JSON runs."""
    if (auto_detect or auto_extract) and source_path is not None and target_path is not None:
        from pegasus.validation.file_detection.routing import coerce_local_validate_fields_with_detection

        fmt, delim, cfg, _src, _tgt, _cleanup, _warnings = coerce_local_validate_fields_with_detection(
            file_format=file_format,
            delimiter=delimiter,
            fixed_width_config=fixed_width_config,
            column_mappings=column_mappings,
            source_path=Path(source_path),
            target_path=Path(target_path),
            auto_detect=auto_detect,
            auto_extract=auto_extract,
        )
        return fmt, delim, cfg
    if is_json_run(file_format=file_format, delimiter=delimiter):
        return "json", JSON_DELIMITER, None
    if is_columnar_run(file_format=file_format):
        return normalize_file_format(file_format), ",", None
    if not is_fixed_width_run(file_format=file_format, delimiter=delimiter):
        return normalize_file_format(file_format) if normalize_file_format(file_format) != "auto" else file_format, delimiter, fixed_width_config
    resolved = resolve_fixed_width_config(
        file_format="fixed-width",
        delimiter=delimiter,
        fixed_width_config=fixed_width_config,
        column_mappings=column_mappings,
    )
    return "fixed-width", FIXED_WIDTH_DELIMITER, resolved

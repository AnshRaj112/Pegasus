"""Auto-routing: detection + materialization + format coercion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pegasus.validation.delimiter_tokens import JSON_DELIMITER
from pegasus.validation.file_detection.archive_extract import (
    ArchiveExtractError,
    MaterializedFile,
    materialize_validation_path,
)
from pegasus.validation.file_detection.context import detect_file_cached
from pegasus.validation.file_detection.models import DatasetModel
from pegasus.validation.delimiter_tokens import FIXED_WIDTH_DELIMITER
from pegasus.validation.fixed_width_meta import (
    is_fixed_width_run,
    is_json_run,
    normalize_file_format,
    resolve_fixed_width_config,
)

_AUTO_FORMAT_TOKENS = frozenset({"auto", "detect", "infer", ""})
_COLUMNAR_FORMATS = frozenset({"parquet", "orc", "avro", "excel"})


def is_auto_format(file_format: str | None) -> bool:
    token = (file_format or "").strip().lower().replace("_", "-")
    return token in _AUTO_FORMAT_TOKENS


def is_columnar_format(file_format: str | None) -> bool:
    return normalize_file_format(file_format) in _COLUMNAR_FORMATS


def materialize_pair_for_validation(
    source_path: Path,
    target_path: Path,
    *,
    auto_extract: bool = True,
    work_dir: Path | None = None,
) -> tuple[MaterializedFile, MaterializedFile]:
    """Optionally decompress/extract both paths before validation."""
    if not auto_extract:
        return (
            MaterializedFile(path=source_path.resolve()),
            MaterializedFile(path=target_path.resolve()),
        )
    try:
        src = materialize_validation_path(source_path, work_dir=work_dir)
        tgt = materialize_validation_path(target_path, work_dir=work_dir)
    except ArchiveExtractError as exc:
        raise ValueError(str(exc)) from exc
    return src, tgt


def _resolve_format_from_detection(
    report_source,
    report_target,
    *,
    declared: str,
    min_confidence: int,
) -> str:
    if is_auto_format(declared):
        for report in (report_source, report_target):
            if report.suggested_file_format and report.validation_strategy.confidence >= min_confidence:
                return report.suggested_file_format
        s_fmt = report_source.structured_format.detected_type if report_source.structured_format else "unknown"
        t_fmt = report_target.structured_format.detected_type if report_target.structured_format else "unknown"
        if s_fmt == t_fmt and s_fmt in {"json", "jsonl"}:
            return "json"
        if s_fmt in {"csv", "tsv", "psv"} or t_fmt in {"csv", "tsv", "psv"}:
            return "csv"
        if report_source.dataset_model == DatasetModel.HIERARCHICAL:
            return "json"
        if report_source.magic_bytes and report_source.magic_bytes.detected_type in {"parquet", "orc", "avro"}:
            return report_source.magic_bytes.detected_type
        return "csv"
    return normalize_file_format(declared)


def _resolve_delimiter_from_detection(
    report_source,
    report_target,
    *,
    declared: str,
    min_confidence: int,
) -> str:
    token = (declared or "").strip().lower()
    if token not in {"", "auto", "infer", "detect"}:
        return declared
    for report in (report_source, report_target):
        if report.suggested_delimiter and report.structured_format and report.structured_format.confidence >= min_confidence:
            return report.suggested_delimiter
    return "auto"


def coerce_local_validate_fields_with_detection(
    *,
    file_format: str,
    delimiter: str,
    fixed_width_config: dict[str, Any] | None,
    column_mappings: list[Any] | None,
    source_path: Path | None = None,
    target_path: Path | None = None,
    auto_detect: bool = True,
    auto_extract: bool = True,
    min_confidence: int = 55,
    work_dir: Path | None = None,
    max_extract_bytes: int | None = None,
) -> tuple[str, str, dict[str, Any] | None, Path, Path, list[Path], list[str]]:
    """Like :func:`coerce_local_validate_fields` but with optional path-based detection.

    Returns ``(file_format, delimiter, fixed_width_config, source_path, target_path, cleanup_paths, warnings)``.
    """
    warnings: list[str] = []
    cleanup: list[Path] = []
    declared = (file_format or "csv").strip()
    if source_path is None or target_path is None:
        raise ValueError("source_path and target_path are required for detection routing")

    src_mat: MaterializedFile | None = None
    tgt_mat: MaterializedFile | None = None
    extract_kwargs: dict[str, object] = {}
    if max_extract_bytes is not None:
        extract_kwargs["max_extract_bytes"] = max_extract_bytes

    if auto_extract:
        from pegasus.validation.file_detection.archive_extract import materialize_validation_path

        try:
            src_mat = materialize_validation_path(source_path, work_dir=work_dir, **extract_kwargs)
            tgt_mat = materialize_validation_path(target_path, work_dir=work_dir, **extract_kwargs)
        except ArchiveExtractError as exc:
            raise ValueError(str(exc)) from exc
        cleanup.extend(src_mat.cleanup_paths)
        cleanup.extend(tgt_mat.cleanup_paths)
        warnings.extend(src_mat.warnings)
        warnings.extend(tgt_mat.warnings)
        source_path = src_mat.path
        target_path = tgt_mat.path

    resolved_format = declared
    resolved_delim = delimiter

    if auto_detect and source_path is not None and target_path is not None:
        rs = detect_file_cached(source_path, user_format_hint=None if is_auto_format(declared) else declared)
        rt = detect_file_cached(target_path, user_format_hint=None if is_auto_format(declared) else declared)
        warnings.extend(rs.warnings)
        warnings.extend(rt.warnings)
        resolved_format = _resolve_format_from_detection(
            rs,
            rt,
            declared=declared,
            min_confidence=min_confidence,
        )
        resolved_delim = _resolve_delimiter_from_detection(
            rs,
            rt,
            declared=delimiter,
            min_confidence=min_confidence,
        )
        if resolved_format != normalize_file_format(declared) and not is_auto_format(declared):
            warnings.append(
                f"detection adjusted file_format from {declared!r} to {resolved_format!r}"
            )

    if is_json_run(file_format=resolved_format, delimiter=resolved_delim):
        return "json", JSON_DELIMITER, None, source_path, target_path, cleanup, warnings
    if is_columnar_format(resolved_format):
        return resolved_format, ",", None, source_path, target_path, cleanup, warnings
    if not is_fixed_width_run(file_format=resolved_format, delimiter=resolved_delim):
        return resolved_format, resolved_delim, fixed_width_config, source_path, target_path, cleanup, warnings
    resolved_cfg = resolve_fixed_width_config(
        file_format="fixed-width",
        delimiter=resolved_delim,
        fixed_width_config=fixed_width_config,
        column_mappings=column_mappings,
    )
    return "fixed-width", FIXED_WIDTH_DELIMITER, resolved_cfg, source_path, target_path, cleanup, warnings

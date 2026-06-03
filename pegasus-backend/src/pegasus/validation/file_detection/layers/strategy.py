"""Layer 9: validation strategy selection from detection evidence."""

from __future__ import annotations

from pegasus.validation.file_detection.models import (
    DatasetModel,
    DetectionStageResult,
    ValidationStrategyHint,
)
from pegasus.validation.file_detection.layers.compression import is_compressed_type
from pegasus.validation.file_detection.plugins.registry import plugin_for_magic_type
from pegasus.validation.file_detection.sampling import FileSample

_COLUMNAR_TYPES = frozenset({"parquet", "orc", "avro", "excel", "ole_compound"})


def select_validation_strategy(
    sample: FileSample,
    *,
    compression: DetectionStageResult | None,
    container: DetectionStageResult | None,
    encoding: DetectionStageResult | None,
    structured: DetectionStageResult | None,
    text_binary: DetectionStageResult | None,
    schema: DetectionStageResult | None,
    user_format_hint: str | None = None,
) -> tuple[DetectionStageResult, DatasetModel, str | None, str | None]:
    """Return strategy stage, dataset model, suggested file_format, suggested delimiter."""

    warnings: list[str] = []

    if compression and is_compressed_type(compression.detected_type):
        return (
            DetectionStageResult(
                ValidationStrategyHint.DECOMPRESS_FIRST.value,
                90,
                [f"compressed: {compression.detected_type}"],
            ),
            DatasetModel.CONTAINER,
            None,
            None,
        )

    if container and container.detected_type not in {"none", "unknown"}:
        return (
            DetectionStageResult(
                ValidationStrategyHint.CONTAINER_INSPECT.value,
                85,
                [f"archive container: {container.detected_type}"],
                {"entry_count": container.metadata.get("entry_count")},
            ),
            DatasetModel.CONTAINER,
            None,
            None,
        )

    if encoding and encoding.detected_type in {"utf-16-le", "utf-16-be", "utf-16", "utf-32-le", "utf-32-be"}:
        return (
            DetectionStageResult(
                ValidationStrategyHint.TRANSCODE_FIRST.value,
                88,
                [f"encoding {encoding.detected_type} not supported for direct CSV validation"],
            ),
            DatasetModel.BINARY_ASSET,
            None,
            None,
        )

    if encoding and encoding.detected_type in {"hex", "base64", "url_encoded"}:
        warnings.append("encoded payload; decode before validation")

    fmt = structured.detected_type if structured else "unknown"
    conf = structured.confidence if structured else 0

    if user_format_hint:
        hinted = user_format_hint.strip().lower().replace("_", "-")
        strategy, model, out_fmt, delim = _map_user_hint(hinted)
        return (
            DetectionStageResult(
                strategy.value,
                95,
                [f"user hint file_format={hinted!r}"],
            ),
            model,
            out_fmt,
            delim,
        )

    if fmt == "json" and conf >= 50:
        return (
            DetectionStageResult(ValidationStrategyHint.JSON_DOCUMENT.value, conf, ["structured JSON"]),
            DatasetModel.HIERARCHICAL,
            "json",
            "json",
        )

    if fmt == "jsonl" and conf >= 50:
        warnings.append("jsonl not natively validated; treating as json hint")
        return (
            DetectionStageResult(ValidationStrategyHint.JSON_DOCUMENT.value, conf - 10, ["JSONL sample"]),
            DatasetModel.HIERARCHICAL,
            "json",
            "json",
        )

    if fmt == "fixed_width" and conf >= 50:
        return (
            DetectionStageResult(ValidationStrategyHint.FIXED_WIDTH.value, conf, ["fixed-width heuristic"]),
            DatasetModel.TABULAR,
            "fixed-width",
            "fixed",
        )

    if fmt in {"csv", "tsv", "psv"} and conf >= 40:
        delim = structured.metadata.get("delimiter", "\t" if fmt == "tsv" else "|" if fmt == "psv" else ",")
        return (
            DetectionStageResult(ValidationStrategyHint.CSV_TABULAR.value, conf, [f"delimited {fmt}"]),
            DatasetModel.TABULAR,
            "csv",
            str(delim),
        )

    if fmt in _COLUMNAR_TYPES or (magic_result and magic_result.detected_type in _COLUMNAR_TYPES):
        col_fmt = fmt if fmt in _COLUMNAR_TYPES else (magic_result.detected_type if magic_result else "parquet")
        if col_fmt == "ole_compound":
            col_fmt = "excel"
        plugin = plugin_for_magic_type(col_fmt)
        token = plugin.suggested_file_format() if plugin else col_fmt
        return (
            DetectionStageResult(
                ValidationStrategyHint.CSV_TABULAR.value,
                85,
                [f"columnar format {col_fmt}"],
                {"columnar_format": token},
            ),
            DatasetModel.TABULAR,
            token,
            ",",
        )

    if text_binary and text_binary.detected_type == "binary":
        return (
            DetectionStageResult(ValidationStrategyHint.UNSUPPORTED.value, 60, ["binary asset"]),
            DatasetModel.BINARY_ASSET,
            None,
            None,
        )

    if conf < 40:
        return (
            DetectionStageResult(ValidationStrategyHint.UNKNOWN.value, conf, ["insufficient confidence"]),
            DatasetModel.UNKNOWN,
            None,
            None,
        )

    return (
        DetectionStageResult(ValidationStrategyHint.CSV_TABULAR.value, 35, ["default csv fallback"]),
        DatasetModel.TABULAR,
        "csv",
        "auto",
    )


def _map_user_hint(
    hinted: str,
) -> tuple[ValidationStrategyHint, DatasetModel, str, str | None]:
    if hinted == "json":
        return ValidationStrategyHint.JSON_DOCUMENT, DatasetModel.HIERARCHICAL, "json", "json"
    if hinted in {"fixed-width", "fixedwidth", "fixed_width"}:
        return ValidationStrategyHint.FIXED_WIDTH, DatasetModel.TABULAR, "fixed-width", "fixed"
    if hinted in _COLUMNAR_TYPES:
        token = "excel" if hinted == "ole_compound" else hinted
        return ValidationStrategyHint.CSV_TABULAR, DatasetModel.TABULAR, token, ","
    return ValidationStrategyHint.CSV_TABULAR, DatasetModel.TABULAR, "csv", "auto"

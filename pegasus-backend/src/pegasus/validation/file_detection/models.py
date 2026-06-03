"""Canonical types for multi-layer file detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DatasetModel(str, Enum):
    """Validation operates on dataset models, not raw extensions."""

    TABULAR = "tabular"
    HIERARCHICAL = "hierarchical"
    CONTAINER = "container"
    BINARY_ASSET = "binary_asset"
    DATABASE = "database"
    UNKNOWN = "unknown"


class TextBinaryClass(str, Enum):
    TEXT = "text"
    BINARY = "binary"
    UNKNOWN = "unknown"


class ValidationStrategyHint(str, Enum):
    """Suggested downstream validation path (backward-compatible tokens)."""

    CSV_TABULAR = "csv"
    FIXED_WIDTH = "fixed-width"
    JSON_DOCUMENT = "json"
    CONTAINER_INSPECT = "container"
    DECOMPRESS_FIRST = "decompress_first"
    TRANSCODE_FIRST = "transcode_first"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class DetectionStageResult:
    """Outcome of a single pipeline layer."""

    detected_type: str
    confidence: int
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.confidence = max(0, min(100, int(self.confidence)))


@dataclass(slots=True)
class FileDetectionReport:
    """Full detection report for one file path."""

    path: str
    file_size_bytes: int
    bytes_read: int
    extension: DetectionStageResult | None = None
    magic_bytes: DetectionStageResult | None = None
    container: DetectionStageResult | None = None
    compression: DetectionStageResult | None = None
    encoding: DetectionStageResult | None = None
    text_binary: DetectionStageResult | None = None
    structured_format: DetectionStageResult | None = None
    schema: DetectionStageResult | None = None
    validation_strategy: DetectionStageResult | None = None
    dataset_model: DatasetModel = DatasetModel.UNKNOWN
    mime_type: str | None = None
    suggested_file_format: str | None = None
    suggested_delimiter: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def _stage(s: DetectionStageResult | None) -> dict[str, Any] | None:
            if s is None:
                return None
            return {
                "detected_type": s.detected_type,
                "confidence": s.confidence,
                "evidence": list(s.evidence),
                "metadata": dict(s.metadata),
            }

        return {
            "path": self.path,
            "file_size_bytes": self.file_size_bytes,
            "bytes_read": self.bytes_read,
            "dataset_model": self.dataset_model.value,
            "mime_type": self.mime_type,
            "suggested_file_format": self.suggested_file_format,
            "suggested_delimiter": self.suggested_delimiter,
            "warnings": list(self.warnings),
            "extension": _stage(self.extension),
            "magic_bytes": _stage(self.magic_bytes),
            "container": _stage(self.container),
            "compression": _stage(self.compression),
            "encoding": _stage(self.encoding),
            "text_binary": _stage(self.text_binary),
            "structured_format": _stage(self.structured_format),
            "schema": _stage(self.schema),
            "validation_strategy": _stage(self.validation_strategy),
        }

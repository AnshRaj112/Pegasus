# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-04T06:59:09Z
# --- END GENERATED FILE METADATA ---

"""Types for the multi-layer file detection pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pegasus.schemas.validation import FileDetectionResponse, FileDetectionStageResponse


@dataclass(slots=True)
class DetectionStage:
    """One layer result with confidence 0–100."""

    detected_type: str
    confidence: int
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_api(self) -> FileDetectionStageResponse:
        return FileDetectionStageResponse(
            detected_type=self.detected_type,
            confidence=self.confidence,
            evidence=list(self.evidence),
            metadata=dict(self.metadata),
        )


@dataclass(slots=True)
class FileDetectionReport:
    """Full detection report for a local file path."""

    path: str
    file_size_bytes: int
    bytes_read: int
    dataset_model: str
    mime_type: str | None = None
    suggested_file_format: str | None = None
    suggested_delimiter: str | None = None
    warnings: list[str] = field(default_factory=list)
    extension: DetectionStage | None = None
    magic_bytes: DetectionStage | None = None
    container: DetectionStage | None = None
    compression: DetectionStage | None = None
    encoding: DetectionStage | None = None
    text_binary: DetectionStage | None = None
    structured_format: DetectionStage | None = None
    schema_hint: DetectionStage | None = None
    validation_strategy: DetectionStage | None = None

    def to_api(self) -> FileDetectionResponse:
        return FileDetectionResponse(
            path=self.path,
            file_size_bytes=self.file_size_bytes,
            bytes_read=self.bytes_read,
            dataset_model=self.dataset_model,
            mime_type=self.mime_type,
            suggested_file_format=self.suggested_file_format,
            suggested_delimiter=self.suggested_delimiter,
            warnings=list(self.warnings),
            extension=self.extension.to_api() if self.extension else None,
            magic_bytes=self.magic_bytes.to_api() if self.magic_bytes else None,
            container=self.container.to_api() if self.container else None,
            compression=self.compression.to_api() if self.compression else None,
            encoding=self.encoding.to_api() if self.encoding else None,
            text_binary=self.text_binary.to_api() if self.text_binary else None,
            structured_format=self.structured_format.to_api() if self.structured_format else None,
            schema_hint=self.schema_hint.to_api() if self.schema_hint else None,
            validation_strategy=self.validation_strategy.to_api() if self.validation_strategy else None,
        )

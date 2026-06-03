"""Multi-layer file type detection for the validation platform."""

from pegasus.validation.file_detection.models import (
    DatasetModel,
    DetectionStageResult,
    FileDetectionReport,
    TextBinaryClass,
    ValidationStrategyHint,
)
from pegasus.validation.file_detection.pipeline import detect_file, suggest_format_override
from pegasus.validation.file_detection.sampling import (
    DEFAULT_MAX_SAMPLE_BYTES,
    SAMPLE_4K,
    SAMPLE_64K,
    SAMPLE_8K,
    FileSample,
    read_file_sample,
)

__all__ = [
    "DatasetModel",
    "DetectionStageResult",
    "DEFAULT_MAX_SAMPLE_BYTES",
    "FileDetectionReport",
    "FileSample",
    "SAMPLE_4K",
    "SAMPLE_64K",
    "SAMPLE_8K",
    "TextBinaryClass",
    "ValidationStrategyHint",
    "detect_file",
    "read_file_sample",
    "suggest_format_override",
]

"""Multi-layer file type detection for the validation platform."""

from pegasus.validation.file_detection.models import (
    DatasetModel,
    DetectionStageResult,
    FileDetectionReport,
    TextBinaryClass,
    ValidationStrategyHint,
)
from pegasus.validation.file_detection.pipeline import detect_file, suggest_format_override
from pegasus.validation.file_detection.plugins.registry import (
    register_format_plugin,
    RegisteredFormatPlugin,
)
from pegasus.validation.file_detection.routing import (
    coerce_local_validate_fields_with_detection,
    is_auto_format,
    materialize_pair_for_validation,
)
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
    "register_format_plugin",
    "RegisteredFormatPlugin",
    "coerce_local_validate_fields_with_detection",
    "is_auto_format",
    "materialize_pair_for_validation",
]

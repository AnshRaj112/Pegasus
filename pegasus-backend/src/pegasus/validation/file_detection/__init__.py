# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:52:37Z
# --- END GENERATED FILE METADATA ---

"""Multi-layer bounded file type detection for Pegasus validation."""

from pegasus.validation.file_detection.coerce import (
    coerce_local_validate_fields_with_detection,
    resolve_file_format_with_detection,
    suggest_format_override,
)
from pegasus.validation.file_detection.pipeline import detect_file
from pegasus.validation.file_detection.sample import read_file_sample
from pegasus.validation.file_detection.types import DetectionStage, FileDetectionReport

__all__ = [
    "DetectionStage",
    "FileDetectionReport",
    "coerce_local_validate_fields_with_detection",
    "detect_file",
    "read_file_sample",
    "resolve_file_format_with_detection",
    "suggest_format_override",
]

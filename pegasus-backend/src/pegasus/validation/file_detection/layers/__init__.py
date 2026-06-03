"""Individual detection layers."""

from pegasus.validation.file_detection.layers.compression import detect_compression
from pegasus.validation.file_detection.layers.container import detect_container
from pegasus.validation.file_detection.layers.encoding import detect_encoding
from pegasus.validation.file_detection.layers.extension import detect_extension_hint
from pegasus.validation.file_detection.layers.magic_bytes import detect_magic_bytes
from pegasus.validation.file_detection.layers.schema_discovery import discover_schema_hint
from pegasus.validation.file_detection.layers.structured import detect_structured_format
from pegasus.validation.file_detection.layers.strategy import select_validation_strategy
from pegasus.validation.file_detection.layers.text_binary import classify_text_binary

__all__ = [
    "detect_compression",
    "detect_container",
    "detect_encoding",
    "detect_extension_hint",
    "detect_magic_bytes",
    "discover_schema_hint",
    "detect_structured_format",
    "select_validation_strategy",
    "classify_text_binary",
]

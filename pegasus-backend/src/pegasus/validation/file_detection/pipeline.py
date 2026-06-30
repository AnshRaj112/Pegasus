# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:41:59Z
# --- END GENERATED FILE METADATA ---

"""Orchestrates the multi-layer file detection pipeline."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.file_detection.layers import compression as compression_layer
from pegasus.validation.file_detection.layers import container as container_layer
from pegasus.validation.file_detection.layers import encoding as encoding_layer
from pegasus.validation.file_detection.layers import extension as extension_layer
from pegasus.validation.file_detection.layers import magic_bytes as magic_layer
from pegasus.validation.file_detection.layers import schema_discovery as schema_layer
from pegasus.validation.file_detection.layers import strategy as strategy_layer
from pegasus.validation.file_detection.layers import structured as structured_layer
from pegasus.validation.file_detection.layers import text_binary as text_binary_layer
from pegasus.validation.file_detection.sample import read_file_sample
from pegasus.validation.file_detection.types import FileDetectionReport


def detect_file(
    path: str | Path,
    *,
    user_format_hint: str | None = None,
    max_sample_bytes: int | None = None,
) -> FileDetectionReport:
    """Run the full detection pipeline on a local file (bounded read)."""
    sample = read_file_sample(
        Path(path),
        max_bytes=max_sample_bytes if max_sample_bytes is not None else 64 * 1024,
    )

    extension = extension_layer.detect_extension(sample)
    magic = magic_layer.detect_magic_bytes(sample)
    container = container_layer.detect_container(sample, magic)
    compression = compression_layer.detect_compression(sample, magic)
    encoding = encoding_layer.detect_encoding(sample)
    text_binary = text_binary_layer.detect_text_binary(sample, encoding)
    structured = structured_layer.detect_structured(sample, text_binary, magic)
    schema_hint = schema_layer.detect_schema_hint(sample, structured)

    strategy, dataset_model, suggested_format, suggested_delim, warnings = strategy_layer.select_validation_strategy(
        extension=extension,
        magic=magic,
        container=container,
        compression=compression,
        encoding=encoding,
        structured=structured,
        user_format_hint=user_format_hint,
    )

    mime = magic.metadata.get("mime") if magic else None

    return FileDetectionReport(
        path=str(sample.path),
        file_size_bytes=sample.file_size_bytes,
        bytes_read=sample.bytes_read,
        dataset_model=dataset_model,
        mime_type=mime,
        suggested_file_format=suggested_format,
        suggested_delimiter=suggested_delim,
        warnings=warnings,
        extension=extension,
        magic_bytes=magic,
        container=container,
        compression=compression,
        encoding=encoding,
        text_binary=text_binary,
        structured_format=structured,
        schema_hint=schema_hint,
        validation_strategy=strategy,
    )

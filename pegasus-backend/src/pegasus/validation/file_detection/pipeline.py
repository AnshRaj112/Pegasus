"""Orchestrates the multi-layer file detection pipeline."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.file_detection.layers import (
    classify_text_binary,
    detect_compression,
    detect_container,
    detect_encoding,
    detect_extension_hint,
    detect_magic_bytes,
    detect_structured_format,
    discover_schema_hint,
    select_validation_strategy,
)
from pegasus.validation.file_detection.models import FileDetectionReport
from pegasus.validation.file_detection.sampling import read_file_sample


def detect_file(
    path: Path | str,
    *,
    user_format_hint: str | None = None,
    max_sample_bytes: int | None = None,
) -> FileDetectionReport:
    """Run the full detection pipeline on a local file (bounded read only)."""
    kwargs = {}
    if max_sample_bytes is not None:
        kwargs["max_bytes"] = max_sample_bytes
    sample = read_file_sample(path, **kwargs)

    extension = detect_extension_hint(sample)
    magic = detect_magic_bytes(sample)
    container = detect_container(sample, magic_result=magic)
    compression = detect_compression(sample, magic_result=magic)
    encoding = detect_encoding(sample, magic_result=magic)

    # If wire encoding wraps payload, decode a small sample and re-run magic/structured.
    if encoding.detected_type in {"hex", "base64"} and encoding.confidence >= 70:
        decoded = _decode_encoding_sample(sample.prefix_8k, encoding.detected_type)
        if decoded:
            from pegasus.validation.file_detection.sampling import FileSample

            inner = FileSample(
                path=sample.path,
                file_size_bytes=sample.file_size_bytes,
                prefix=decoded[: len(sample.prefix)],
                prefix_4k=decoded[:4096],
                prefix_8k=decoded[:8192],
            )
            magic = detect_magic_bytes(inner)
            encoding = detect_encoding(inner, magic_result=magic)

    text_binary = classify_text_binary(
        sample,
        compression_result=compression,
        magic_result=magic,
    )
    structured = detect_structured_format(
        sample,
        text_binary=text_binary,
        extension_hint=extension,
    )
    schema = discover_schema_hint(sample, structured=structured)

    strategy, dataset_model, suggested_fmt, suggested_delim = select_validation_strategy(
        sample,
        compression=compression,
        container=container,
        encoding=encoding,
        structured=structured,
        text_binary=text_binary,
        schema=schema,
        user_format_hint=user_format_hint,
    )

    mime = None
    if magic.metadata.get("mime"):
        mime = str(magic.metadata["mime"])

    warnings: list[str] = []
    if extension.confidence > 0 and structured.confidence >= 50:
        if extension.detected_type not in {structured.detected_type, "text", "unknown"}:
            if extension.detected_type != structured.detected_type:
                warnings.append(
                    f"extension suggests {extension.detected_type} but content suggests {structured.detected_type}"
                )

    return FileDetectionReport(
        path=str(sample.path),
        file_size_bytes=sample.file_size_bytes,
        bytes_read=sample.bytes_read,
        extension=extension,
        magic_bytes=magic,
        container=container,
        compression=compression,
        encoding=encoding,
        text_binary=text_binary,
        structured_format=structured,
        schema=schema,
        validation_strategy=strategy,
        dataset_model=dataset_model,
        mime_type=mime,
        suggested_file_format=suggested_fmt,
        suggested_delimiter=suggested_delim,
        warnings=warnings,
    )


def _decode_encoding_sample(prefix: bytes, encoding_type: str) -> bytes | None:
    import base64

    try:
        if encoding_type == "hex":
            text = prefix[:512].strip().decode("ascii")
            return bytes.fromhex(text)
        if encoding_type == "base64":
            return base64.b64decode(prefix[:1024].strip(), validate=True)
    except Exception:
        return None
    return None


def suggest_format_override(
    path: Path | str,
    declared_format: str | None,
    *,
    min_confidence: int = 55,
) -> tuple[str, str, list[str]]:
    """Optionally refine declared format using detection (backward compatible).

    Returns ``(file_format, delimiter, warnings)``. When confidence is low,
    returns the declared values unchanged.
    """
    declared = (declared_format or "csv").strip().lower()
    report = detect_file(path, user_format_hint=declared_format)
    warnings = list(report.warnings)

    if report.validation_strategy.confidence < min_confidence:
        return declared, "auto", warnings

    if report.suggested_file_format and report.suggested_file_format != declared:
        if report.structured_format and report.structured_format.confidence >= min_confidence:
            warnings.append(
                f"detection suggests file_format={report.suggested_file_format!r} "
                f"(declared {declared!r})"
            )
            fmt = report.suggested_file_format
            delim = report.suggested_delimiter or "auto"
            return fmt, delim, warnings

    delim = report.suggested_delimiter or "auto"
    return declared, delim, warnings

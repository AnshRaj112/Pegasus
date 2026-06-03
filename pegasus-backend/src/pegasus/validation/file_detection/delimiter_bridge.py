"""Merge delimiter sniffing with file-detection sample windows."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.file_detection.context import detect_file_cached
from pegasus.validation.file_detection.sampling import read_file_sample
from pegasus.validation.readers.delimiter_detection import (
    DelimiterDetectionResult,
    detect_delimiter,
    detect_delimiter_from_lines,
    resolve_shared_auto_delimiter,
)

_MIN_STRUCTURED_CONFIDENCE = 40


def sample_lines_for_delimiter(path: Path, *, max_bytes: int = 512 * 1024, max_lines: int = 500) -> list[str]:
    """Reuse detection prefix when possible, else bounded line sample."""
    sample = read_file_sample(path, max_bytes=max_bytes)
    text = sample.prefix.decode("utf-8", errors="replace")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
        if len(lines) >= max_lines:
            break
    if lines:
        return lines
    from pegasus.validation.readers.delimiter_detection import _sample_non_empty_lines

    return _sample_non_empty_lines(path, max_bytes=max_bytes, max_lines=max_lines)


def resolve_auto_delimiter(source_path: Path, target_path: Path) -> str:
    """Resolve delimiter using detection hints then shared sniff (single prefix read per file)."""
    src_report = detect_file_cached(source_path)
    tgt_report = detect_file_cached(target_path)

    hinted: list[str] = []
    for report in (src_report, tgt_report):
        structured = report.structured_format
        if structured is None or structured.confidence < _MIN_STRUCTURED_CONFIDENCE:
            continue
        delim = structured.metadata.get("delimiter")
        if isinstance(delim, str) and delim and delim not in hinted:
            hinted.append(delim)

    if len(hinted) == 1 and len(hinted[0]) > 1:
        return hinted[0]

    src_lines = sample_lines_for_delimiter(source_path)
    tgt_lines = sample_lines_for_delimiter(target_path)
    try:
        left = detect_delimiter_from_lines(src_lines, path=source_path)
        right = detect_delimiter_from_lines(tgt_lines, path=target_path)
    except ValueError:
        shared = resolve_shared_auto_delimiter(source_path, target_path)
        return shared.delimiter

    if left.delimiter == right.delimiter:
        return left.delimiter

    shared = resolve_shared_auto_delimiter(
        source_path,
        target_path,
        source_lines=src_lines,
        target_lines=tgt_lines,
    )
    return shared.delimiter

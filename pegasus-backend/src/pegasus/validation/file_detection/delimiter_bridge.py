# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:27:08Z
# --- END GENERATED FILE METADATA ---

"""Reuse detection sample for delimiter resolution (avoid duplicate large reads)."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.file_detection.pipeline import detect_file
from pegasus.validation.file_detection.sample import read_file_sample
from pegasus.validation.readers.delimiter_detection import (
    DelimiterDetectionResult,
    detect_delimiter,
    resolve_shared_auto_delimiter,
)


def resolve_auto_delimiter(
    source_path: Path,
    target_path: Path,
    *,
    file_format_hint: str | None = "csv",
) -> DelimiterDetectionResult:
    """Pick delimiter using detection structured hints when confident, else bounded sniff."""
    src_report = detect_file(source_path, user_format_hint=file_format_hint)
    if src_report.suggested_delimiter and (src_report.structured_format or None) and (
        src_report.structured_format.confidence >= 70
    ):
        return DelimiterDetectionResult(
            delimiter=src_report.suggested_delimiter,
            strategy="file_detection_structured",
        )

    src_sample = read_file_sample(source_path)
    tgt_sample = read_file_sample(target_path)
    src_lines = src_sample.raw.decode("utf-8", errors="replace").splitlines()[:30]
    tgt_lines = tgt_sample.raw.decode("utf-8", errors="replace").splitlines()[:30]
    if src_lines and tgt_lines:
        try:
            return resolve_shared_auto_delimiter(
                source_path,
                target_path,
                source_lines=src_lines,
                target_lines=tgt_lines,
            )
        except ValueError:
            pass
    return detect_delimiter(source_path)

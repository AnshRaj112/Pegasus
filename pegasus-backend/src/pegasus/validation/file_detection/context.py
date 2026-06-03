"""Shared detection context to avoid duplicate prefix reads."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pegasus.validation.file_detection.models import FileDetectionReport
from pegasus.validation.file_detection.pipeline import detect_file


@dataclass(slots=True)
class PairDetectionContext:
    source: FileDetectionReport
    target: FileDetectionReport


def detect_pair(source_path: Path, target_path: Path, *, user_format_hint: str | None = None) -> PairDetectionContext:
    return PairDetectionContext(
        source=detect_file(source_path, user_format_hint=user_format_hint),
        target=detect_file(target_path, user_format_hint=user_format_hint),
    )


@lru_cache(maxsize=256)
def _cached_detect_file(path_str: str, mtime_ns: int, size: int, hint: str | None) -> FileDetectionReport:
    del mtime_ns, size
    return detect_file(path_str, user_format_hint=hint)


def detect_file_cached(path: Path, *, user_format_hint: str | None = None) -> FileDetectionReport:
    st = path.stat()
    return _cached_detect_file(str(path.resolve()), st.st_mtime_ns, st.st_size, user_format_hint)

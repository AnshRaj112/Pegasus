# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:42:20Z
# --- END GENERATED FILE METADATA ---

"""Bounded prefix reads for file detection (never load entire files)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_SAMPLE_BYTES = 64 * 1024
PREFIX_8K = 8 * 1024
PREFIX_4K = 4 * 1024


@dataclass(slots=True)
class FileSample:
    """Prefix windows read once per detection call."""

    path: Path
    file_size_bytes: int
    raw: bytes
    bytes_read: int

    @property
    def prefix_4k(self) -> bytes:
        return self.raw[:PREFIX_4K]

    @property
    def prefix_8k(self) -> bytes:
        return self.raw[:PREFIX_8K]

    @property
    def suffix_4(self) -> bytes:
        if self.file_size_bytes < 4:
            return b""
        with self.path.open("rb") as fh:
            fh.seek(max(0, self.file_size_bytes - 4))
            return fh.read(4)


def read_file_sample(path: Path, *, max_bytes: int = MAX_SAMPLE_BYTES) -> FileSample:
    """Read at most *max_bytes* from the start of *path*."""
    path = path.resolve()
    file_size = path.stat().st_size
    cap = min(max_bytes, file_size)
    with path.open("rb") as fh:
        raw = fh.read(cap)
    return FileSample(path=path, file_size_bytes=file_size, raw=raw, bytes_read=len(raw))

"""Bounded, streaming-safe file sampling for detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Detection never reads more than 64 KiB for classification.
SAMPLE_4K = 4 * 1024
SAMPLE_8K = 8 * 1024
SAMPLE_64K = 64 * 1024
DEFAULT_MAX_SAMPLE_BYTES = SAMPLE_64K


@dataclass(slots=True)
class FileSample:
    """Prefix bytes loaded once and reused across detection layers."""

    path: Path
    file_size_bytes: int
    prefix: bytes
    prefix_4k: bytes
    prefix_8k: bytes

    @property
    def bytes_read(self) -> int:
        return len(self.prefix)

    @property
    def suffix(self) -> str:
        return self.path.suffix.lower()

    @property
    def name(self) -> str:
        return self.path.name


def read_file_sample(
    path: Path | str,
    *,
    max_bytes: int = DEFAULT_MAX_SAMPLE_BYTES,
) -> FileSample:
    """Read at most *max_bytes* from the start of *path* (never the full file)."""
    p = Path(path)
    size = p.stat().st_size
    cap = min(max(size, 0), max_bytes)
    with p.open("rb") as fh:
        prefix = fh.read(cap) if cap else b""
    return FileSample(
        path=p,
        file_size_bytes=size,
        prefix=prefix,
        prefix_4k=prefix[:SAMPLE_4K],
        prefix_8k=prefix[:SAMPLE_8K],
    )

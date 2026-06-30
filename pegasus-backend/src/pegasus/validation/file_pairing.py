# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T05:26:24Z
# --- END GENERATED FILE METADATA ---

"""Auto-match and list files for folder-based validation."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from pegasus.validation.file_format import extensions_for_format, object_name_matches_format


def _file_matches_format(path: Path, allowed: frozenset[str]) -> bool:
    return object_name_matches_format(path.name, allowed)


def list_files_in_directory(
    directory: Path,
    *,
    file_format: str | None = None,
    recursive: bool = False,
    max_files: int = 10_000,
) -> list[Path]:
    """Return sorted file paths under *directory*; optionally recursive."""
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")
    allowed = extensions_for_format(file_format)
    out: list[Path] = []

    if not recursive:
        for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_file():
                continue
            if _file_matches_format(child, allowed):
                out.append(child)
        return out

    for root, _dirs, files in os.walk(directory):
        root_path = Path(root)
        for name in sorted(files, key=str.lower):
            child = root_path / name
            if not child.is_file():
                continue
            if _file_matches_format(child, allowed):
                out.append(child.resolve())
            if len(out) >= max_files:
                return out
    return out


@dataclass(frozen=True)
class MatchedPair:
    unit_id: str
    source_path: Path
    target_path: Path
    auto_matched: bool


@dataclass(frozen=True)
class PairingResult:
    pairs: list[MatchedPair]
    unmatched_sources: list[Path]
    unmatched_targets: list[Path]


def auto_match_files_by_name(
    source_files: list[Path],
    target_files: list[Path],
) -> PairingResult:
    """Pair files when basenames match exactly; remainder are unmatched."""
    by_name: dict[str, list[Path]] = {}
    for p in target_files:
        by_name.setdefault(p.name, []).append(p)

    pairs: list[MatchedPair] = []
    unmatched_sources: list[Path] = []
    used_targets: set[Path] = set()

    for src in sorted(source_files, key=lambda p: p.name.lower()):
        candidates = [t for t in by_name.get(src.name, []) if t not in used_targets]
        if len(candidates) == 1:
            tgt = candidates[0]
            used_targets.add(tgt)
            pairs.append(
                MatchedPair(
                    unit_id=str(uuid.uuid4()),
                    source_path=src,
                    target_path=tgt,
                    auto_matched=True,
                )
            )
        else:
            unmatched_sources.append(src)

    unmatched_targets = sorted(
        (t for t in target_files if t not in used_targets),
        key=lambda p: p.name.lower(),
    )
    return PairingResult(pairs=pairs, unmatched_sources=unmatched_sources, unmatched_targets=unmatched_targets)

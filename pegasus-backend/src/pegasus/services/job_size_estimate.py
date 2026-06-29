# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:05:47Z
# --- END GENERATED FILE METADATA ---

"""Estimate combined validation input bytes for queue admission."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pegasus.core.json_util import loads_str


def _path_size(path: str | Path | None) -> int:
    if not path:
        return 0
    p = Path(path)
    try:
        if p.is_file():
            return p.stat().st_size
    except OSError:
        pass
    return 0


def combined_bytes_from_meta(meta: dict[str, Any]) -> int:
    """Return source+target bytes from meta fields and referenced paths."""
    src = int(meta.get("source_bytes") or meta.get("source_size_bytes") or 0)
    tgt = int(meta.get("target_bytes") or meta.get("target_size_bytes") or 0)
    if src > 0 or tgt > 0:
        return src + tgt
    src = _path_size(meta.get("source_path"))
    tgt = _path_size(meta.get("target_path"))
    if src > 0 or tgt > 0:
        return src + tgt
    total = 0
    for unit in meta.get("batch_units") or []:
        if not isinstance(unit, dict):
            continue
        sp = unit.get("source_path") or (unit.get("source_paths") or [None])[0]
        tp = unit.get("target_path") or (unit.get("target_paths") or [None])[0]
        total += _path_size(sp) + _path_size(tp)
    return total


def enrich_meta_file_sizes(
    meta: dict[str, Any],
    *,
    source_bytes: int | None = None,
    target_bytes: int | None = None,
) -> dict[str, Any]:
    """Stamp source_bytes/target_bytes on meta when inferrable."""
    src = source_bytes if source_bytes is not None else _path_size(meta.get("source_path"))
    tgt = target_bytes if target_bytes is not None else _path_size(meta.get("target_path"))
    if src > 0:
        meta["source_bytes"] = src
    if tgt > 0:
        meta["target_bytes"] = tgt
    return meta


def estimate_job_combined_bytes(job_dir: Path) -> int:
    """Read combined source+target bytes from job meta or copied inputs."""
    meta_path = job_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = loads_str(meta_path.read_text(encoding="utf-8"))
            combined = combined_bytes_from_meta(meta)
            if combined > 0:
                return combined
        except (OSError, ValueError, TypeError):
            pass
    total = 0
    for name in ("source.csv", "target.csv", "source", "target"):
        path = job_dir / name
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total

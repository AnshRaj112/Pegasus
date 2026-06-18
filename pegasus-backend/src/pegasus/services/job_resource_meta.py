# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Read and write per-job file-size metadata used by the resource governor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pegasus.core.json_util import loads_str


def adapter_size_bytes(adapter: object) -> int:
    """Return byte size from a delimited adapter when available."""
    getter = getattr(adapter, "get_size_bytes", None)
    if callable(getter):
        try:
            size = int(getter())
            if size > 0:
                return size
        except (OSError, TypeError, ValueError):
            pass
    path = getattr(adapter, "path", None)
    if isinstance(path, Path) and path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            pass
    return 0


def local_path_size_bytes(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def stamp_resource_sizes(
    meta: dict[str, Any],
    *,
    source_bytes: int,
    target_bytes: int,
    column_count: int | None = None,
) -> dict[str, Any]:
    """Attach normalized size fields to job meta before enqueue."""
    src = max(0, int(source_bytes))
    tgt = max(0, int(target_bytes))
    meta["source_bytes"] = src
    meta["target_bytes"] = tgt
    meta["combined_bytes"] = src + tgt
    if column_count is not None:
        meta["column_count"] = max(0, int(column_count))
    return meta


def read_job_meta(job_dir: Path) -> dict[str, Any]:
    meta_path = job_dir / "meta.json"
    if not meta_path.is_file():
        return {}
    try:
        data = loads_str(meta_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def job_column_count(meta: dict[str, Any]) -> int:
    explicit = meta.get("column_count")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    mappings = meta.get("column_mappings")
    if isinstance(mappings, list) and mappings:
        return len(mappings)
    return 8


def estimate_job_csv_bytes(job_dir: Path) -> int:
    """Combined source + target bytes for admission (meta.json first)."""
    meta = read_job_meta(job_dir)
    combined = meta.get("combined_bytes")
    if isinstance(combined, int) and combined > 0:
        return combined
    src = meta.get("source_bytes")
    tgt = meta.get("target_bytes")
    if isinstance(src, int) and isinstance(tgt, int) and (src > 0 or tgt > 0):
        return max(0, src) + max(0, tgt)

    total = 0
    for name in ("source.csv", "target.csv"):
        p = job_dir / name
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
            continue
        ext_key = "source_path" if name == "source.csv" else "target_path"
        ext_path = meta.get(ext_key)
        if ext_path:
            try:
                total += Path(str(ext_path)).stat().st_size
            except OSError:
                pass
    return total

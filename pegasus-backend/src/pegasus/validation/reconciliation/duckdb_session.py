"""Shared DuckDB connection tuning for reconciliation and CSV ingest."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import duckdb

from pegasus.core.resource_tuning import physical_ram_bytes

from .config import ReconciliationRuntimeConfig

logger = logging.getLogger(__name__)


def _network_fs_types() -> set[str]:
    return {"nfs", "nfs4", "cifs", "smb3", "fuse.sshfs", "ceph", "glusterfs", "lustre"}


def _path_on_network_fs(path: Path) -> bool:
    try:
        mounts = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    target = path.resolve()
    best_mount = ""
    best_type = ""
    for line in mounts:
        parts = line.split()
        if len(parts) < 3:
            continue
        mount_point = parts[1].replace("\\040", " ")
        fs_type = parts[2]
        try:
            mp = Path(mount_point).resolve()
        except OSError:
            continue
        try:
            target.relative_to(mp)
        except ValueError:
            continue
        if len(str(mp)) > len(best_mount):
            best_mount = str(mp)
            best_type = fs_type
    return best_type in _network_fs_types()


def duckdb_effective_thread_count(
    cfg: ReconciliationRuntimeConfig,
    *,
    source_path: Path,
    target_path: Path,
) -> int:
    """Threads DuckDB will use for this job (network cap vs local cap), never above ``os.cpu_count()``."""
    cpu = max(1, int(os.cpu_count() or 1))
    if _path_on_network_fs(source_path) or _path_on_network_fs(target_path):
        return max(1, min(int(cfg.duckdb_network_threads), cpu))
    if cfg.duckdb_local_threads > 0:
        return max(1, min(int(cfg.duckdb_local_threads), cpu))
    return cpu


def configure_duckdb_connection(
    con: duckdb.DuckDBPyConnection,
    workspace: Path,
    cfg: ReconciliationRuntimeConfig,
    *,
    source_path: Path,
    target_path: Path,
) -> None:
    con.execute("SET temp_directory = ?", [str(workspace)])
    total_ram = physical_ram_bytes()
    if total_ram is not None:
        reserve = max(0, int(cfg.duckdb_memory_os_reserve_bytes))
        usable = max(256 * 1024 * 1024, total_ram - reserve)
        mem_bytes = max(256 * 1024 * 1024, int(usable * cfg.duckdb_memory_limit_ratio))
        con.execute("SET memory_limit = ?", [f"{mem_bytes}B"])
        logger.info(
            "DuckDB memory_limit=%sB (phys_ram=%s reserve=%s ratio=%s)",
            mem_bytes,
            total_ram,
            reserve,
            cfg.duckdb_memory_limit_ratio,
        )

    network_io = _path_on_network_fs(source_path) or _path_on_network_fs(target_path)
    threads = duckdb_effective_thread_count(cfg, source_path=source_path, target_path=target_path)
    con.execute("SET threads = ?", [threads])
    if network_io:
        logger.info("DuckDB using network-I/O mode threads=%d", threads)
    else:
        logger.info("DuckDB local disk threads=%d", threads)
        if cfg.duckdb_enable_object_cache:
            con.execute("SET enable_object_cache = true")

    con.execute("SET preserve_insertion_order = false")

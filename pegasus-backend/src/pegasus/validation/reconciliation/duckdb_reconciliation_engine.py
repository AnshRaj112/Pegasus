"""DuckDB-backed external memory reconciliation for two CSV files on a UID key."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import duckdb

from pegasus.validation.comparators.exceptions import UIDComparisonError
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame

from .config import ReconciliationRuntimeConfig, ReconciliationStrategy
from .disk_guard import ensure_disk_headroom
from .exceptions import ReconciliationError
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics

logger = logging.getLogger(__name__)


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _total_ram_bytes() -> int | None:
    """Best-effort physical RAM discovery without extra dependencies."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if isinstance(pages, int) and isinstance(page_size, int) and pages > 0 and page_size > 0:
            return pages * page_size
    except (ValueError, OSError, AttributeError):
        pass
    return None


def _network_fs_types() -> set[str]:
    return {"nfs", "nfs4", "cifs", "smb3", "fuse.sshfs", "ceph", "glusterfs", "lustre"}


def _path_on_network_fs(path: Path) -> bool:
    """Detect network-backed mounts via /proc/mounts (Linux); fallback False."""
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


def _fetch_explain_text(con: duckdb.DuckDBPyConnection, sql: str, params: list[object]) -> str:
    """Return combined EXPLAIN ANALYZE text regardless of duckdb-python tuple shape."""
    rows = con.execute(f"EXPLAIN ANALYZE {sql}", params).fetchall()
    if not rows:
        return "(empty EXPLAIN ANALYZE output)"
    pieces: list[str] = []
    for row in rows:
        if not row:
            continue
        pieces.append(str(row[-1]))
    return "\n".join(pieces) if pieces else str(rows)


class DuckDBReconciliationEngine:
    """Full-file reconciliation using DuckDB temp directory and streaming mismatch export."""

    __slots__ = ("_metrics",)

    def __init__(self, *, metrics: ReconciliationMetrics | None = None) -> None:
        self._metrics = metrics or NoOpReconciliationMetrics()

    def run_csv_pair(
        self,
        *,
        workspace: Path,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
    ) -> tuple[MismatchReport, int, int, ReconciliationStrategy]:
        if len(delimiter) != 1:
            raise ReconciliationError("DuckDB reconciliation requires a single-character delimiter")
        combined = source_path.stat().st_size + target_path.stat().st_size
        ensure_disk_headroom(
            workspace,
            int(combined * cfg.disk_headroom_multiplier),
            label="duckdb reconciliation",
        )

        artifact = workspace / "mismatches.ndjson"
        if artifact.exists():
            artifact.unlink()

        uid_q = _quote_ident(uid_column)

        con = duckdb.connect(database=":memory:")
        try:
            con.execute("SET temp_directory = ?", [str(workspace)])
            total_ram = _total_ram_bytes()
            if total_ram is not None:
                mem_bytes = max(256 * 1024 * 1024, int(total_ram * cfg.duckdb_memory_limit_ratio))
                con.execute("SET memory_limit = ?", [f"{mem_bytes}B"])

            network_io = _path_on_network_fs(source_path) or _path_on_network_fs(target_path)
            if network_io:
                threads = max(1, min(cfg.duckdb_network_threads, int(os.cpu_count() or 1)))
                con.execute("SET threads = ?", [threads])
                logger.info("DuckDB using network-I/O mode threads=%d", threads)
            else:
                threads = cfg.duckdb_local_threads if cfg.duckdb_local_threads > 0 else max(1, int(os.cpu_count() or 1))
                con.execute("SET threads = ?", [threads])
                if cfg.duckdb_enable_object_cache:
                    con.execute("SET enable_object_cache = true")

            con.execute("SET preserve_insertion_order = false")

            src_tbl = "pegasus_src"
            tgt_tbl = "pegasus_tgt"
            q_src = f"""
                CREATE TABLE {src_tbl} AS
                SELECT * FROM read_csv_auto(
                    ?, delim=?, header=true, ignore_errors=false, sample_size=-1
                )
            """
            q_tgt = f"""
                CREATE TABLE {tgt_tbl} AS
                SELECT * FROM read_csv_auto(
                    ?, delim=?, header=true, ignore_errors=false, sample_size=-1
                )
            """
            src_params: list[object] = [str(source_path), delimiter]
            tgt_params: list[object] = [str(target_path), delimiter]
            if cfg.duckdb_explain_analyze:
                logger.info("DuckDB EXPLAIN ANALYZE [load_source]\n%s", _fetch_explain_text(con, q_src, src_params))
                logger.info("DuckDB EXPLAIN ANALYZE [load_target]\n%s", _fetch_explain_text(con, q_tgt, tgt_params))
            else:
                con.execute(q_src, src_params)
                con.execute(q_tgt, tgt_params)

            src_n = int(con.execute(f"SELECT count(*) FROM {src_tbl}").fetchone()[0])
            tgt_n = int(con.execute(f"SELECT count(*) FROM {tgt_tbl}").fetchone()[0])

            dup_s = con.execute(
                f"SELECT {uid_q} AS u FROM {src_tbl} GROUP BY 1 HAVING count(*) > 1 LIMIT 1"
            ).fetchone()
            if dup_s is not None:
                raise UIDComparisonError(
                    f"Duplicate uid values in source for column {uid_column!r} (DuckDB probe)"
                )
            dup_t = con.execute(
                f"SELECT {uid_q} AS u FROM {tgt_tbl} GROUP BY 1 HAVING count(*) > 1 LIMIT 1"
            ).fetchone()
            if dup_t is not None:
                raise UIDComparisonError(
                    f"Duplicate uid values in target for column {uid_column!r} (DuckDB probe)"
                )

            summary = {
                MismatchType.MISSING_IN_TARGET.value: 0,
                MismatchType.EXTRA_IN_TARGET.value: 0,
                MismatchType.VALUE_MISMATCH.value: 0,
            }

            def fmt_cell(v: object) -> str | None:
                if v is None:
                    return "<null>" if cfg.stringify_null_in_report else None
                return str(v)

            self._metrics.on_phase_start("duckdb_export_mismatches", rows=src_n + tgt_n)
            with artifact.open("w", encoding="utf-8") as out:
                q_miss = f"""
                    SELECT s.{uid_q} AS uid
                    FROM {src_tbl} s
                    ANTI JOIN {tgt_tbl} t ON s.{uid_q} = t.{uid_q}
                """
                rel = con.execute(q_miss)
                while True:
                    batch = rel.fetchmany(10_000)
                    if not batch:
                        break
                    for (uid_val,) in batch:
                        row = {
                            "uid": str(uid_val),
                            "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                            "column_name": None,
                            "source_value": None,
                            "target_value": None,
                            "row_detail": "{}",
                        }
                        out.write(json.dumps(row, ensure_ascii=False))
                        out.write("\n")
                        summary[MismatchType.MISSING_IN_TARGET.value] += 1

                q_extra = f"""
                    SELECT t.{uid_q} AS uid
                    FROM {tgt_tbl} t
                    ANTI JOIN {src_tbl} s ON t.{uid_q} = s.{uid_q}
                """
                rel = con.execute(q_extra)
                while True:
                    batch = rel.fetchmany(10_000)
                    if not batch:
                        break
                    for (uid_val,) in batch:
                        row = {
                            "uid": str(uid_val),
                            "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                            "column_name": None,
                            "source_value": None,
                            "target_value": None,
                            "row_detail": "{}",
                        }
                        out.write(json.dumps(row, ensure_ascii=False))
                        out.write("\n")
                        summary[MismatchType.EXTRA_IN_TARGET.value] += 1

                if compare_columns:
                    vm_joined = "pegasus_vm_joined"
                    select_cols: list[str] = []
                    for i, col in enumerate(compare_columns):
                        cq = _quote_ident(col)
                        select_cols.append(f"s.{cq} AS s_{i}")
                        select_cols.append(f"t.{cq} AS t_{i}")
                    col_block = ",\n                        ".join(select_cols)
                    q_vm_joined = f"""
                        CREATE TEMP TABLE {vm_joined} AS
                        SELECT
                            s.{uid_q} AS uid,
                            {col_block}
                        FROM {src_tbl} s
                        INNER JOIN {tgt_tbl} t ON s.{uid_q} = t.{uid_q}
                    """
                    if cfg.duckdb_explain_analyze:
                        logger.info(
                            "DuckDB EXPLAIN ANALYZE [value_mismatch_joined]\n%s",
                            _fetch_explain_text(con, q_vm_joined, []),
                        )
                    else:
                        con.execute(q_vm_joined)

                    vm_parts: list[str] = []
                    for i, col in enumerate(compare_columns):
                        col_lit = _quote_sql_literal(col)
                        vm_parts.append(
                            f"""
                            SELECT uid, {col_lit} AS column_name, s_{i} AS sv, t_{i} AS tv
                            FROM {vm_joined}
                            WHERE s_{i} IS DISTINCT FROM t_{i}
                            """
                        )
                    q_vm = "\nUNION ALL\n".join(vm_parts)
                    if cfg.duckdb_explain_analyze:
                        logger.info(
                            "DuckDB EXPLAIN ANALYZE [value_mismatch_extract]\n%s",
                            _fetch_explain_text(con, q_vm, []),
                        )
                    rel = con.execute(q_vm)
                    while True:
                        batch = rel.fetchmany(10_000)
                        if not batch:
                            break
                        for uid_v, col_name, sv, tv in batch:
                            row = {
                                "uid": str(uid_v),
                                "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                                "column_name": str(col_name),
                                "source_value": fmt_cell(sv),
                                "target_value": fmt_cell(tv),
                                "row_detail": "{}",
                            }
                            out.write(json.dumps(row, ensure_ascii=False))
                            out.write("\n")
                            summary[MismatchType.VALUE_MISMATCH.value] += 1

            self._metrics.on_phase_end("duckdb_export_mismatches")

            total_m = sum(summary.values())
            logger.info(
                "DuckDB reconciliation complete source_rows=%d target_rows=%d mismatch_lines=%d",
                src_n,
                tgt_n,
                total_m,
            )
            report = MismatchReport(
                mismatches=empty_mismatch_frame(),
                summary=summary,
                mismatch_artifact_path=artifact,
            )
            return report, src_n, tgt_n, ReconciliationStrategy.HASH_PARTITION
        finally:
            con.close()

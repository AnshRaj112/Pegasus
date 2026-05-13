"""DuckDB-backed external memory reconciliation for two CSV files on a UID key."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import duckdb

from pegasus.validation.comparators.exceptions import UIDComparisonError
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame

from .config import ReconciliationRuntimeConfig, ReconciliationStrategy
from .csv_ingestion_pipeline import CSVIngestionPipeline
from .disk_guard import ensure_disk_headroom
from .duckdb_session import configure_duckdb_connection
from .exceptions import ReconciliationError
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics
from .parquet_converter import merge_ndjson_chunk_files, path_sql_literal, _delim_sql_literal
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _quote_sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _fetch_explain_text(con: duckdb.DuckDBPyConnection, sql: str, params: list[object]) -> str:
    rows = con.execute(f"EXPLAIN ANALYZE {sql}", params).fetchall()
    if not rows:
        return "(empty EXPLAIN ANALYZE output)"
    pieces: list[str] = []
    for row in rows:
        if not row:
            continue
        pieces.append(str(row[-1]))
    return "\n".join(pieces) if pieces else str(rows)


def _partition_dup_probe(
    con: duckdb.DuckDBPyConnection,
    *,
    parquet_path: Path,
    uid_column: str,
    partition_id: int,
) -> None:
    uid_q = _quote_ident(uid_column)
    plit = path_sql_literal(parquet_path)
    pid = int(partition_id)
    sql = f"""
        SELECT {uid_q} AS u
        FROM read_parquet({plit}) WHERE pegasus_part = {pid}
        GROUP BY 1 HAVING count(*) > 1 LIMIT 1
    """
    row = con.execute(sql).fetchone()
    if row is not None:
        raise UIDComparisonError(
            f"Duplicate uid values for column {uid_column!r} (DuckDB partition {partition_id} probe)"
        )


def _export_partition_mismatches(
    con: duckdb.DuckDBPyConnection,
    *,
    src_pq: Path,
    tgt_pq: Path,
    uid_column: str,
    compare_columns: list[str],
    partition_id: int,
    stringify_null: bool,
    out_chunk: Path,
    cfg: ReconciliationRuntimeConfig,
) -> None:
    uid_q = _quote_ident(uid_column)
    src_lit = path_sql_literal(src_pq)
    tgt_lit = path_sql_literal(tgt_pq)
    out_lit = path_sql_literal(out_chunk)
    pid = int(partition_id)
    sv_cast = (
        "CASE WHEN sv IS NULL THEN NULL ELSE cast(sv as varchar) END"
        if not stringify_null
        else "CASE WHEN sv IS NULL THEN '<null>' ELSE cast(sv as varchar) END"
    )
    tv_cast = (
        "CASE WHEN tv IS NULL THEN NULL ELSE cast(tv as varchar) END"
        if not stringify_null
        else "CASE WHEN tv IS NULL THEN '<null>' ELSE cast(tv as varchar) END"
    )

    q_missing = f"""
        WITH s AS (SELECT * FROM read_parquet({src_lit}) WHERE pegasus_part = {pid}),
             t AS (SELECT * FROM read_parquet({tgt_lit}) WHERE pegasus_part = {pid})
        SELECT
            cast(s.{uid_q} as varchar) AS uid,
            '{MismatchType.MISSING_IN_TARGET.value}' AS mismatch_type,
            NULL::varchar AS column_name,
            NULL::varchar AS source_value,
            NULL::varchar AS target_value,
            '{{}}' AS row_detail
        FROM s
        ANTI JOIN t ON s.{uid_q} = t.{uid_q}
    """
    q_extra = f"""
        WITH t AS (SELECT * FROM read_parquet({tgt_lit}) WHERE pegasus_part = {pid}),
             s AS (SELECT * FROM read_parquet({src_lit}) WHERE pegasus_part = {pid})
        SELECT
            cast(t.{uid_q} as varchar) AS uid,
            '{MismatchType.EXTRA_IN_TARGET.value}' AS mismatch_type,
            NULL::varchar AS column_name,
            NULL::varchar AS source_value,
            NULL::varchar AS target_value,
            '{{}}' AS row_detail
        FROM t
        ANTI JOIN s ON t.{uid_q} = s.{uid_q}
    """

    parts_sql: list[str] = [f"({q_missing})", f"({q_extra})"]

    if compare_columns:
        select_cols: list[str] = []
        for i, col in enumerate(compare_columns):
            cq = _quote_ident(col)
            select_cols.append(f"s.{cq} AS s_{i}")
            select_cols.append(f"t.{cq} AS t_{i}")
        col_block = ",\n                        ".join(select_cols)
        vm_union = "\nUNION ALL\n".join(
            f"""
            SELECT uid, {_quote_sql_literal(col)} AS column_name, s_{i} AS sv, t_{i} AS tv
            FROM vm
            WHERE s_{i} IS DISTINCT FROM t_{i}
            """.strip()
            for i, col in enumerate(compare_columns)
        )
        q_value = f"""
            WITH s AS (SELECT * FROM read_parquet({src_lit}) WHERE pegasus_part = {pid}),
                 t AS (SELECT * FROM read_parquet({tgt_lit}) WHERE pegasus_part = {pid}),
                 vm AS (
                     SELECT s.{uid_q} AS uid, {col_block}
                     FROM s
                     INNER JOIN t ON s.{uid_q} = t.{uid_q}
                 )
            SELECT
                cast(uid as varchar) AS uid,
                '{MismatchType.VALUE_MISMATCH.value}' AS mismatch_type,
                cast(column_name as varchar) AS column_name,
                {sv_cast} AS source_value,
                {tv_cast} AS target_value,
                '{{}}' AS row_detail
            FROM (
            {vm_union}
            ) z
        """
        parts_sql.append(f"({q_value})")

    union_sql = "\nUNION ALL\n".join(parts_sql)
    copy_sql = f"COPY ({union_sql}) TO {out_lit} (FORMAT JSON)"
    if cfg.duckdb_explain_analyze and partition_id == 0:
        logger.info(
            "DuckDB EXPLAIN ANALYZE [partition_export p=%d]\n%s",
            partition_id,
            _fetch_explain_text(con, copy_sql, []),
        )
    con.execute(copy_sql)


def _summary_from_ndjson(con: duckdb.DuckDBPyConnection, artifact: Path) -> dict[str, int]:
    summary = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 0,
    }
    lit = path_sql_literal(artifact)
    rows = con.execute(
        f"SELECT mismatch_type, count(*) FROM read_json_auto({lit}) GROUP BY mismatch_type"
    ).fetchall()
    for mt, cnt in rows:
        if mt is not None:
            summary[str(mt)] = int(cnt)
    return summary


def _run_legacy_full_table_csv(
    con: duckdb.DuckDBPyConnection,
    *,
    workspace: Path,
    source_path: Path,
    target_path: Path,
    uid_column: str,
    delimiter: str,
    compare_columns: list[str],
    cfg: ReconciliationRuntimeConfig,
    progress_callback: Callable[[dict[str, Any]], None] | None,
    artifact: Path,
) -> tuple[MismatchReport, int, int]:
    """Diagnostic path: full-table CSV materialization (not recommended for 10M+ rows)."""
    uid_q = _quote_ident(uid_column)

    def emit(phase: str, message: str, percent: float | None = None, **progress: Any) -> None:
        if progress_callback is None:
            return
        payload: dict[str, Any] = {"phase": phase, "message": message}
        if percent is not None:
            payload["percent"] = round(float(percent), 2)
        if progress:
            payload["progress"] = progress
        progress_callback(payload)

    src_tbl = "pegasus_src"
    tgt_tbl = "pegasus_tgt"
    emit("duckdb_load_source", "Loading source CSV (legacy full table)", 6.0)
    delim_sql = _delim_sql_literal(delimiter)
    q_src = f"""
        CREATE TABLE {src_tbl} AS
        SELECT * FROM read_csv_auto(?, delim={delim_sql}, header=true, ignore_errors=false)
    """
    q_tgt = f"""
        CREATE TABLE {tgt_tbl} AS
        SELECT * FROM read_csv_auto(?, delim={delim_sql}, header=true, ignore_errors=false)
    """
    con.execute(q_src, [str(source_path)])
    emit("duckdb_load_target", "Loading target CSV (legacy full table)", 16.0)
    con.execute(q_tgt, [str(target_path)])
    src_n = int(con.execute(f"SELECT count(*) FROM {src_tbl}").fetchone()[0])
    tgt_n = int(con.execute(f"SELECT count(*) FROM {tgt_tbl}").fetchone()[0])
    emit("duckdb_loaded", "CSV load complete", 26.0, source_rows=src_n, target_rows=tgt_n)

    dup_s = con.execute(
        f"SELECT {uid_q} AS u FROM {src_tbl} GROUP BY 1 HAVING count(*) > 1 LIMIT 1"
    ).fetchone()
    if dup_s is not None:
        raise UIDComparisonError(f"Duplicate uid values in source for column {uid_column!r} (DuckDB probe)")
    dup_t = con.execute(
        f"SELECT {uid_q} AS u FROM {tgt_tbl} GROUP BY 1 HAVING count(*) > 1 LIMIT 1"
    ).fetchone()
    if dup_t is not None:
        raise UIDComparisonError(f"Duplicate uid values in target for column {uid_column!r} (DuckDB probe)")

    q_missing_rows = f"""
        SELECT
            cast(s.{uid_q} as varchar) AS uid,
            '{MismatchType.MISSING_IN_TARGET.value}' AS mismatch_type,
            NULL::varchar AS column_name,
            NULL::varchar AS source_value,
            NULL::varchar AS target_value,
            '{{}}' AS row_detail
        FROM {src_tbl} s
        ANTI JOIN {tgt_tbl} t ON s.{uid_q}=t.{uid_q}
    """
    q_extra_rows = f"""
        SELECT
            cast(t.{uid_q} as varchar) AS uid,
            '{MismatchType.EXTRA_IN_TARGET.value}' AS mismatch_type,
            NULL::varchar AS column_name,
            NULL::varchar AS source_value,
            NULL::varchar AS target_value,
            '{{}}' AS row_detail
        FROM {tgt_tbl} t
        ANTI JOIN {src_tbl} s ON t.{uid_q}=s.{uid_q}
    """
    q_value_rows = (
        "SELECT NULL::varchar uid, NULL::varchar mismatch_type, NULL::varchar column_name, "
        "NULL::varchar source_value, NULL::varchar target_value, NULL::varchar row_detail WHERE false"
    )
    if compare_columns:
        vm_joined = "pegasus_vm_joined"
        select_cols: list[str] = []
        for i, col in enumerate(compare_columns):
            cq = _quote_ident(col)
            select_cols.append(f"s.{cq} AS s_{i}")
            select_cols.append(f"t.{cq} AS t_{i}")
        col_block = ",\n                    ".join(select_cols)
        q_vm_joined = f"""
            CREATE TEMP TABLE {vm_joined} AS
            SELECT s.{uid_q} AS uid, {col_block}
            FROM {src_tbl} s
            INNER JOIN {tgt_tbl} t ON s.{uid_q} = t.{uid_q}
        """
        con.execute(q_vm_joined)
        vm_parts: list[str] = []
        for i, col in enumerate(compare_columns):
            col_lit = _quote_sql_literal(col)
            vm_parts.append(
                f"SELECT uid, {col_lit} AS column_name, s_{i} AS sv, t_{i} AS tv FROM {vm_joined} WHERE s_{i} IS DISTINCT FROM t_{i}"
            )
        q_vm = "\nUNION ALL\n".join(vm_parts)
        sv_cast = (
            "CASE WHEN sv IS NULL THEN NULL ELSE cast(sv as varchar) END"
            if not cfg.stringify_null_in_report
            else "CASE WHEN sv IS NULL THEN '<null>' ELSE cast(sv as varchar) END"
        )
        tv_cast = (
            "CASE WHEN tv IS NULL THEN NULL ELSE cast(tv as varchar) END"
            if not cfg.stringify_null_in_report
            else "CASE WHEN tv IS NULL THEN '<null>' ELSE cast(tv as varchar) END"
        )
        q_value_rows = f"""
            SELECT cast(uid as varchar) AS uid, '{MismatchType.VALUE_MISMATCH.value}' AS mismatch_type,
                cast(column_name as varchar) AS column_name, {sv_cast} AS source_value, {tv_cast} AS target_value, '{{}}' AS row_detail
            FROM ({q_vm}) vm
        """
    q_all_rows = f"""
        SELECT * FROM ({q_missing_rows})
        UNION ALL SELECT * FROM ({q_extra_rows})
        UNION ALL SELECT * FROM ({q_value_rows})
    """
    q_export_tbl = "pegasus_mismatch_export"
    con.execute(f"CREATE TEMP TABLE {q_export_tbl} AS {q_all_rows}")
    art_lit = path_sql_literal(artifact)
    con.execute(
        f"COPY (SELECT uid, mismatch_type, column_name, source_value, target_value, row_detail FROM {q_export_tbl}) TO {art_lit} (FORMAT JSON)",
    )
    summary_raw = con.execute(
        f"SELECT mismatch_type, count(*) FROM {q_export_tbl} GROUP BY mismatch_type"
    ).fetchall()
    summary: dict[str, int] = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 0,
    }
    for mt, cnt in summary_raw:
        summary[str(mt)] = int(cnt)
    return (
        MismatchReport(mismatches=empty_mismatch_frame(), summary=summary, mismatch_artifact_path=artifact),
        src_n,
        tgt_n,
    )


class DuckDBReconciliationEngine:
    """Partitioned reconciliation over Parquet working files with incremental mismatch export."""

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
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
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

        def emit(phase: str, message: str, percent: float | None = None, **progress: Any) -> None:
            if progress_callback is None:
                return
            payload: dict[str, Any] = {"phase": phase, "message": message}
            if percent is not None:
                payload["percent"] = round(float(percent), 2)
            if progress:
                payload["progress"] = progress
            progress_callback(payload)

        perf = PerformanceMonitor(_label="duckdb_reconciliation")
        con = duckdb.connect(database=":memory:")
        try:
            emit("duckdb_init", "Initializing DuckDB runtime", 2.0)
            configure_duckdb_connection(con, workspace, cfg, source_path=source_path, target_path=target_path)

            if not cfg.duckdb_ingest_csv_to_parquet:
                logger.warning(
                    "duckdb_ingest_csv_to_parquet=False uses a single global join (diagnostic only; avoid on huge files)"
                )
                report, src_n, tgt_n = _run_legacy_full_table_csv(
                    con,
                    workspace=workspace,
                    source_path=source_path,
                    target_path=target_path,
                    uid_column=uid_column,
                    delimiter=delimiter,
                    compare_columns=compare_columns,
                    cfg=cfg,
                    progress_callback=progress_callback,
                    artifact=artifact,
                )
                perf.checkpoint("duckdb_legacy_done", source_rows=src_n, target_rows=tgt_n)
                emit("duckdb_done", "DuckDB reconciliation completed", 100.0, total_mismatch_records=sum(report.summary.values()))
                return report, src_n, tgt_n, ReconciliationStrategy.HASH_PARTITION

            n_parts = cfg.duckdb_reconciliation_partitions or cfg.partition_buckets
            if n_parts < 1:
                n_parts = 1

            self._metrics.on_phase_start("duckdb_csv_to_parquet", rows=0)
            src_pq, tgt_pq, src_n, tgt_n = CSVIngestionPipeline.ingest_pair(
                con,
                workspace=workspace,
                source_path=source_path,
                target_path=target_path,
                uid_column=uid_column,
                delimiter=delimiter,
                compare_columns=compare_columns,
                cfg=cfg,
                partition_buckets=n_parts,
                progress_callback=progress_callback,
            )
            self._metrics.on_phase_end("duckdb_csv_to_parquet")
            perf.checkpoint("duckdb_ingest_parquet", partitions=n_parts)

            emit("duckdb_checks", "UID uniqueness (per partition)", 28.0)
            for pid in range(n_parts):
                _partition_dup_probe(con, parquet_path=src_pq, uid_column=uid_column, partition_id=pid)
                _partition_dup_probe(con, parquet_path=tgt_pq, uid_column=uid_column, partition_id=pid)
                if progress_callback and n_parts > 1 and pid % max(1, n_parts // 10) == 0:
                    emit(
                        "duckdb_checks",
                        "UID uniqueness scan",
                        28.0 + (pid + 1) / max(n_parts, 1) * 2.0,
                        partition=pid,
                        partitions=n_parts,
                    )
            emit("duckdb_checks", "UID validation complete", 30.0)

            self._metrics.on_phase_start("duckdb_partition_export", rows=src_n + tgt_n)
            chunk_paths: list[Path] = []
            for pid in range(n_parts):
                chunk = workspace / f"mismatches_p_{pid:05d}.ndjson"
                if chunk.exists():
                    chunk.unlink()
                _export_partition_mismatches(
                    con,
                    src_pq=src_pq,
                    tgt_pq=tgt_pq,
                    uid_column=uid_column,
                    compare_columns=compare_columns,
                    partition_id=pid,
                    stringify_null=cfg.stringify_null_in_report,
                    out_chunk=chunk,
                    cfg=cfg,
                )
                chunk_paths.append(chunk)
                if progress_callback and n_parts > 1:
                    emit(
                        "duckdb_partition",
                        f"Partition {pid + 1}/{n_parts} exported",
                        30.0 + (pid + 1) / max(n_parts, 1) * 65.0,
                        partition=pid,
                        partitions=n_parts,
                    )
            self._metrics.on_phase_end("duckdb_partition_export")

            emit("duckdb_merge", "Merging mismatch chunks", 96.0)
            merge_ndjson_chunk_files(artifact, chunk_paths)
            perf.checkpoint("duckdb_merge_chunks")

            summary = _summary_from_ndjson(con, artifact)
            total_m = sum(summary.values())
            logger.info(
                "DuckDB reconciliation complete source_rows=%d target_rows=%d mismatch_lines=%d partitions=%d",
                src_n,
                tgt_n,
                total_m,
                n_parts,
            )
            emit("duckdb_finalize", "Finalizing mismatch report", 99.0, total_mismatch_records=total_m)
            report = MismatchReport(
                mismatches=empty_mismatch_frame(),
                summary=summary,
                mismatch_artifact_path=artifact,
            )
            perf.checkpoint("duckdb_done", total_mismatch_records=total_m)
            emit("duckdb_done", "DuckDB reconciliation completed", 100.0, total_mismatch_records=total_m)
            return report, src_n, tgt_n, ReconciliationStrategy.HASH_PARTITION
        finally:
            con.close()

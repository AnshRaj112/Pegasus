"""CSV ingestion for DuckDB reconciliation: materialize working Parquet files."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

import duckdb

from pegasus.validation.reconciliation.config import ReconciliationRuntimeConfig
from pegasus.validation.reconciliation.duckdb_session import configure_duckdb_connection
from pegasus.validation.reconciliation.parquet_converter import csv_to_partitioned_parquet, parquet_row_count

logger = logging.getLogger(__name__)


def _dedupe_preserve_order(columns: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for c in columns:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def working_columns(uid_column: str, compare_columns: list[str]) -> list[str]:
    """UID plus compare columns (deduped) for pruned Parquet working sets."""
    return _dedupe_preserve_order([uid_column, *compare_columns])


def _ingest_one_side_thread(
    workspace: Path,
    side: str,
    csv_path: Path,
    out_parquet: Path,
    *,
    uid_column: str,
    cols: list[str],
    delimiter: str,
    partition_buckets: int,
    row_group_size: int,
    cfg: ReconciliationRuntimeConfig,
    probe_path: Path,
) -> None:
    """Dedicated DuckDB connection + temp dir (used for parallel source/target ingest)."""
    tmp = workspace / f"duckdb_tmp_ingest_{side}"
    tmp.mkdir(parents=True, exist_ok=True)
    sub_cfg = cfg.model_copy(
        update={"duckdb_memory_limit_ratio": max(0.1, cfg.duckdb_memory_limit_ratio * 0.5)},
    )
    con = duckdb.connect(database=":memory:")
    try:
        configure_duckdb_connection(con, tmp, sub_cfg, source_path=probe_path, target_path=probe_path)
        csv_to_partitioned_parquet(
            con,
            csv_path=csv_path,
            out_parquet=out_parquet,
            delimiter=delimiter,
            uid_column=uid_column,
            columns_to_keep=cols,
            partition_buckets=partition_buckets,
            row_group_size=row_group_size,
        )
    finally:
        con.close()


class CSVIngestionPipeline:
    """Stream both CSV sides into partitioned Parquet via :func:`csv_to_partitioned_parquet`."""

    @staticmethod
    def ingest_pair(
        con: duckdb.DuckDBPyConnection,
        *,
        workspace: Path,
        source_path: Path,
        target_path: Path,
        uid_column: str,
        delimiter: str,
        compare_columns: list[str],
        cfg: ReconciliationRuntimeConfig,
        partition_buckets: int,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path, Path, int, int]:
        cols = working_columns(uid_column, compare_columns)
        src_pq = workspace / "pegasus_source.parquet"
        tgt_pq = workspace / "pegasus_target.parquet"

        def emit(phase: str, message: str, percent: float | None = None, **kw: Any) -> None:
            if progress_callback is None:
                return
            payload: dict[str, Any] = {"phase": phase, "message": message}
            if percent is not None:
                payload["percent"] = round(float(percent), 2)
            if kw:
                payload["progress"] = kw
            progress_callback(payload)

        rg = cfg.duckdb_parquet_row_group_size

        if cfg.duckdb_parallel_csv_ingest:
            emit(
                "duckdb_csv_ingest",
                "Streaming source and target CSV to Parquet (parallel)",
                8.0,
            )
            with ThreadPoolExecutor(max_workers=2) as pool:
                f_src = pool.submit(
                    _ingest_one_side_thread,
                    workspace,
                    "source",
                    source_path,
                    src_pq,
                    uid_column=uid_column,
                    cols=cols,
                    delimiter=delimiter,
                    partition_buckets=partition_buckets,
                    row_group_size=rg,
                    cfg=cfg,
                    probe_path=source_path,
                )
                f_tgt = pool.submit(
                    _ingest_one_side_thread,
                    workspace,
                    "target",
                    target_path,
                    tgt_pq,
                    uid_column=uid_column,
                    cols=cols,
                    delimiter=delimiter,
                    partition_buckets=partition_buckets,
                    row_group_size=rg,
                    cfg=cfg,
                    probe_path=target_path,
                )
                for fut in as_completed((f_src, f_tgt)):
                    fut.result()
        else:
            emit("duckdb_csv_ingest", "Streaming source CSV to Parquet", 6.0)
            csv_to_partitioned_parquet(
                con,
                csv_path=source_path,
                out_parquet=src_pq,
                delimiter=delimiter,
                uid_column=uid_column,
                columns_to_keep=cols,
                partition_buckets=partition_buckets,
                row_group_size=rg,
            )
            emit("duckdb_csv_ingest", "Streaming target CSV to Parquet", 14.0)
            csv_to_partitioned_parquet(
                con,
                csv_path=target_path,
                out_parquet=tgt_pq,
                delimiter=delimiter,
                uid_column=uid_column,
                columns_to_keep=cols,
                partition_buckets=partition_buckets,
                row_group_size=rg,
            )

        src_n = parquet_row_count(con, src_pq)
        tgt_n = parquet_row_count(con, tgt_pq)
        logger.info(
            "CSV ingestion pipeline complete source_rows=%d target_rows=%d cols=%s buckets=%d parallel=%s",
            src_n,
            tgt_n,
            cols,
            partition_buckets,
            cfg.duckdb_parallel_csv_ingest,
        )
        emit("duckdb_loaded", "Parquet ingest complete", 26.0, source_rows=src_n, target_rows=tgt_n)
        return src_pq, tgt_pq, src_n, tgt_n

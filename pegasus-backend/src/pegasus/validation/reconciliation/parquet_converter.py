"""Stream CSV into ZSTD Parquet working files with a precomputed hash partition column."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# Match :data:`pegasus.validation.reconciliation.uid_partition._DEFAULT_NULL_PLACEHOLDER` for routing.
_UID_NULL_SQL = "__NULL__"


def posix_path(p: Path) -> str:
    return p.resolve().as_posix()


def _path_sql_literal(path: Path) -> str:
    return "'" + posix_path(path).replace("'", "''") + "'"


def path_sql_literal(path: Path) -> str:
    """Escape a filesystem path for safe embedding in DuckDB SQL string literals."""
    return _path_sql_literal(path)


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _delim_sql_literal(delimiter: str) -> str:
    """Single-character delimiter as a DuckDB string literal for ``read_csv_auto``."""
    if len(delimiter) != 1:
        raise ValueError("delimiter must be a single character")
    if delimiter == "'":
        return "''''"
    if delimiter == "\\":
        return "'\\\\'"
    return "'" + delimiter + "'"


def csv_to_partitioned_parquet(
    con: duckdb.DuckDBPyConnection,
    *,
    csv_path: Path,
    out_parquet: Path,
    delimiter: str,
    uid_column: str,
    columns_to_keep: list[str],
    partition_buckets: int,
    row_group_size: int,
) -> None:
    """COPY CSV → Parquet with ``pegasus_part = hash(uid_token) % partition_buckets`` (DuckDB ``hash``)."""
    if partition_buckets < 1:
        raise ValueError("partition_buckets must be >= 1")
    uid_q = _quote_ident(uid_column)
    col_exprs = ", ".join(_quote_ident(c) for c in columns_to_keep)
    null_lit = _UID_NULL_SQL.replace("'", "''")
    delim_sql = _delim_sql_literal(delimiter)
    csv_lit = _path_sql_literal(csv_path)
    out_lit = _path_sql_literal(out_parquet)
    sql = f"""
        COPY (
            SELECT
                {col_exprs},
                mod(
                    abs(hash(coalesce(cast({uid_q} as varchar), '{null_lit}'))),
                    {int(partition_buckets)}
                )::INTEGER AS pegasus_part
            FROM read_csv_auto({csv_lit}, delim={delim_sql}, header=true, ignore_errors=false)
        ) TO {out_lit} (FORMAT PARQUET, ROW_GROUP_SIZE {int(row_group_size)}, COMPRESSION ZSTD)
    """
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    con.execute(sql)
    logger.info(
        "DuckDB CSV→Parquet ingest complete rows_unknown path=%s parquet=%s buckets=%d",
        csv_path,
        out_parquet,
        partition_buckets,
    )


def _parquet_row_count_from_metadata(con: duckdb.DuckDBPyConnection, parquet_path: Path) -> int | None:
    """Row count from Parquet footers only (avoids a full table scan)."""
    lit = _path_sql_literal(parquet_path)
    sql = f"""
        SELECT COALESCE(sum(rg_rows), 0)::BIGINT
        FROM (
            SELECT row_group_id, max(row_group_num_rows) AS rg_rows
            FROM parquet_metadata({lit})
            GROUP BY row_group_id
        ) s
    """
    try:
        row = con.execute(sql).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception as exc:
        logger.warning("parquet_metadata row count failed for %s, falling back to scan: %s", parquet_path, exc)
    return None


def parquet_row_count(con: duckdb.DuckDBPyConnection, parquet_path: Path) -> int:
    fast = _parquet_row_count_from_metadata(con, parquet_path)
    if fast is not None:
        return fast
    lit = _path_sql_literal(parquet_path)
    return int(con.execute(f"SELECT count(*) FROM read_parquet({lit})").fetchone()[0])


def merge_ndjson_chunk_files(dest: Path, chunks: list[Path]) -> None:
    """Concatenate NDJSON chunk files into *dest* (streaming, then delete chunks)."""
    import shutil

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        for chunk in chunks:
            if not chunk.is_file() or chunk.stat().st_size == 0:
                continue
            with chunk.open("rb") as inn:
                shutil.copyfileobj(inn, out, length=16 * 1024 * 1024)
    for chunk in chunks:
        if chunk.is_file():
            try:
                chunk.unlink()
            except OSError as exc:
                logger.warning("Failed to remove mismatch chunk %s: %s", chunk, exc)

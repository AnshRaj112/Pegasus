"""DuckDB-backed external memory reconciliation for two CSV files on a UID key."""

from __future__ import annotations

import json
import logging
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

            src_tbl = "pegasus_src"
            tgt_tbl = "pegasus_tgt"
            con.execute(
                f"""
                CREATE TABLE {src_tbl} AS
                SELECT * FROM read_csv_auto(?, delim=?, header=true, ignore_errors=false)
                """,
                [str(source_path), delimiter],
            )
            con.execute(
                f"""
                CREATE TABLE {tgt_tbl} AS
                SELECT * FROM read_csv_auto(?, delim=?, header=true, ignore_errors=false)
                """,
                [str(target_path), delimiter],
            )

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

                for col in compare_columns:
                    cq = _quote_ident(col)
                    q_vm = f"""
                        SELECT s.{uid_q} AS uid, s.{cq} AS sv, t.{cq} AS tv
                        FROM {src_tbl} s
                        INNER JOIN {tgt_tbl} t ON s.{uid_q} = t.{uid_q}
                        WHERE s.{cq} IS DISTINCT FROM t.{cq}
                    """
                    rel = con.execute(q_vm)
                    while True:
                        batch = rel.fetchmany(10_000)
                        if not batch:
                            break
                        for uid_v, sv, tv in batch:
                            row = {
                                "uid": str(uid_v),
                                "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                                "column_name": col,
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

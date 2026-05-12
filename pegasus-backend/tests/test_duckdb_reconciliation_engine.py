"""Integration tests for :class:`~pegasus.validation.reconciliation.duckdb_reconciliation_engine.DuckDBReconciliationEngine`."""

from __future__ import annotations

import textwrap
from pathlib import Path

from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader
from pegasus.validation.reconciliation.config import (
    ReconciliationBackend,
    ReconciliationRuntimeConfig,
    ReconciliationStrategy,
)
from pegasus.validation.reconciliation.coordinator import ReconciliationCoordinator


def _write_csv(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def test_duckdb_backend_finds_mismatches(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        """
        uid,x,y
        a,1,p
        b,2,q
        c,3,r
        """,
    )
    _write_csv(
        tgt,
        """
        uid,x,y
        a,1,p
        b,9,q
        d,4,s
        """,
    )

    reader = PolarsCSVReader(default_batch_size=10_000)
    cfg = ReconciliationRuntimeConfig(
        strategy=ReconciliationStrategy.HASH_PARTITION,
        chunk_rows=1024,
        partition_buckets=8,
        external_memory_threshold_bytes=0,
        duckdb_ingest_csv_to_parquet=True,
        duckdb_parquet_row_group_size=1024,
    ).with_overrides(backend=ReconciliationBackend.DUCKDB)
    coord = ReconciliationCoordinator(reader=reader)
    report, src_rows, tgt_rows, strat = coord.run_csv_pair(
        source_path=src,
        target_path=tgt,
        uid_column="uid",
        delimiter=",",
        compare_columns=["x", "y"],
        cfg=cfg,
    )
    assert strat == ReconciliationStrategy.HASH_PARTITION
    assert src_rows == 3 and tgt_rows == 3
    assert report.summary.get(MismatchType.MISSING_IN_TARGET.value, 0) >= 1
    assert report.summary.get(MismatchType.EXTRA_IN_TARGET.value, 0) >= 1
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) >= 1

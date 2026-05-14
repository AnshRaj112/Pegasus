"""Tests for external-memory reconciliation coordinator."""

from __future__ import annotations

import textwrap
from pathlib import Path

import polars as pl

from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader
from pegasus.validation.reconciliation.config import ReconciliationRuntimeConfig, ReconciliationStrategy
from pegasus.validation.reconciliation.coordinator import ReconciliationCoordinator


def _write_csv(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def test_hash_partition_finds_missing_extra_and_value(tmp_path: Path) -> None:
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
        partition_buckets=4,
        external_memory_threshold_bytes=0,
    ).with_overrides(stream_mismatches=False)
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
    assert src_rows == 3
    assert tgt_rows == 3

    types = set(report.mismatches["mismatch_type"].to_list())
    assert MismatchType.MISSING_IN_TARGET.value in types
    assert MismatchType.EXTRA_IN_TARGET.value in types
    assert MismatchType.VALUE_MISMATCH.value in types


def test_ordered_stream_sorted_csv(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        """
        uid,v
        m,1
        n,2
        """,
    )
    _write_csv(
        tgt,
        """
        uid,v
        m,1
        n,3
        """,
    )

    reader = PolarsCSVReader(default_batch_size=10_000)
    cfg = ReconciliationRuntimeConfig(
        strategy=ReconciliationStrategy.ORDERED_STREAM,
        assume_sorted=True,
        chunk_rows=10_000,
        external_memory_threshold_bytes=0,
    ).with_overrides(stream_mismatches=False)
    coord = ReconciliationCoordinator(reader=reader)
    report, src_rows, tgt_rows, strat = coord.run_csv_pair(
        source_path=src,
        target_path=tgt,
        uid_column="uid",
        delimiter=",",
        compare_columns=["v"],
        cfg=cfg,
    )
    assert strat == ReconciliationStrategy.ORDERED_STREAM
    assert src_rows == 2
    assert tgt_rows == 2
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 1


def test_external_sort_merge(tmp_path: Path) -> None:
    """Unsorted inputs should still reconcile correctly after external sort + merge."""
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        """
        uid,v
        z,1
        a,2
        m,3
        """,
    )
    _write_csv(
        tgt,
        """
        uid,v
        a,2
        m,9
        z,1
        """,
    )

    reader = PolarsCSVReader(default_batch_size=1024)
    cfg = ReconciliationRuntimeConfig(
        strategy=ReconciliationStrategy.EXTERNAL_SORT,
        chunk_rows=1024,
        partition_buckets=8,
        external_memory_threshold_bytes=0,
    ).with_overrides(stream_mismatches=False)
    coord = ReconciliationCoordinator(reader=reader)
    report, src_rows, tgt_rows, strat = coord.run_csv_pair(
        source_path=src,
        target_path=tgt,
        uid_column="uid",
        delimiter=",",
        compare_columns=["v"],
        cfg=cfg,
    )
    assert strat == ReconciliationStrategy.EXTERNAL_SORT
    assert src_rows == 3
    assert tgt_rows == 3
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 1


def test_multichar_hash_partition_streaming(tmp_path: Path) -> None:
    src = tmp_path / "s.csv"
    tgt = tmp_path / "t.csv"
    src.write_text("uid||v\na||1\nb||2\n", encoding="utf-8")
    tgt.write_text("uid||v\na||1\nb||3\n", encoding="utf-8")

    reader = PolarsCSVReader(default_batch_size=1024)
    cfg = ReconciliationRuntimeConfig(
        strategy=ReconciliationStrategy.HASH_PARTITION,
        chunk_rows=1024,
        partition_buckets=4,
        external_memory_threshold_bytes=0,
    ).with_overrides(stream_mismatches=False)
    coord = ReconciliationCoordinator(reader=reader)
    report, sr, tr, strat = coord.run_multichar_hash_partition_csv_pair(
        source_path=src,
        target_path=tgt,
        uid_column="uid",
        delimiter="||",
        compare_columns=["v"],
        cfg=cfg,
    )
    assert strat == ReconciliationStrategy.HASH_PARTITION
    assert sr == 2 and tr == 2
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) >= 1


def test_hash_partition_sub_buckets_and_ndjson_mirror(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        """
        uid,x
        a,1
        b,2
        """,
    )
    _write_csv(
        tgt,
        """
        uid,x
        a,9
        c,3
        """,
    )
    reader = PolarsCSVReader(default_batch_size=1024)
    cfg = ReconciliationRuntimeConfig(
        strategy=ReconciliationStrategy.HASH_PARTITION,
        chunk_rows=1024,
        partition_buckets=4,
        sub_partition_buckets=2,
        parallel_spill_sides=False,
        mismatch_ndjson_mirror=True,
        disk_headroom_multiplier=1.0,
        external_memory_threshold_bytes=0,
    ).with_overrides(stream_mismatches=False)
    coord = ReconciliationCoordinator(reader=reader)
    report, src_rows, tgt_rows, strat = coord.run_csv_pair(
        source_path=src,
        target_path=tgt,
        uid_column="uid",
        delimiter=",",
        compare_columns=["x"],
        cfg=cfg,
    )
    assert strat == ReconciliationStrategy.HASH_PARTITION
    assert src_rows == 2 and tgt_rows == 2
    assert report.mismatches.height >= 2
    types = set(report.mismatches["mismatch_type"].to_list())
    assert MismatchType.MISSING_IN_TARGET.value in types
    assert MismatchType.EXTRA_IN_TARGET.value in types
    assert MismatchType.VALUE_MISMATCH.value in types

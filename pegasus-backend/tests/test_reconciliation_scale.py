# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T11:11:28Z
# --- END GENERATED FILE METADATA ---

"""Scale throughput gates (1M+ rows). Run with PEGASUS_RUN_SCALE_TESTS=1."""

from __future__ import annotations

import csv
import os
import tempfile
import time
from pathlib import Path

import pytest

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline

_COMPARE = ["sku", "amount", "region", "attr4", "attr5", "attr6", "attr7", "attr8", "attr9", "attr10", "attr11"]
_PERF_FACTOR = float(os.environ.get("PEGASUS_PERF_FACTOR", "1.0"))
_RUN_SCALE = os.environ.get("PEGASUS_RUN_SCALE_TESTS", "").strip() in ("1", "true", "yes")


def _generate_pair(work: Path, rows: int) -> tuple[Path, Path]:
    src = work / "source.csv"
    tgt = work / "target.csv"
    for path in (src, tgt):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="|", lineterminator="\n")
            w.writerow(["id", *_COMPARE])
            for i in range(rows):
                w.writerow([str(i), f"SKU{i}", str(i * 1.5), "US", "a", "b", "c", "d", "e", "f", "g", "h"])
    return src, tgt


def _run(src: Path, tgt: Path, *, force_spill: bool) -> float:
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=0 if force_spill else 512 * 1024 * 1024,
        force_disk_spill=force_spill,
        enable_column_drilldown=False,
        chunk_rows=50_000,
        streaming_spill_min_bytes=32 * 1024 * 1024 if force_spill else 10**12,
    )
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        TabularReconciliationPipeline(
            FileDelimitedAdapter(src, delimiter="|"),
            FileDelimitedAdapter(tgt, delimiter="|"),
            identity_columns=["id"],
            compare_columns=_COMPARE,
            config=cfg,
        ).run(workspace=Path(td))
    return time.perf_counter() - t0


@pytest.mark.performance
@pytest.mark.skipif(not _RUN_SCALE, reason="set PEGASUS_RUN_SCALE_TESTS=1 to run scale gates")
def test_1m_rows_spill_under_five_seconds() -> None:
    with tempfile.TemporaryDirectory() as td:
        src, tgt = _generate_pair(Path(td), 1_000_000)
        elapsed = _run(src, tgt, force_spill=True)
    assert elapsed < 35.0 * _PERF_FACTOR, f"1M spill took {elapsed:.2f}s"


@pytest.mark.performance
@pytest.mark.skipif(not _RUN_SCALE, reason="set PEGASUS_RUN_SCALE_TESTS=1 to run scale gates")
def test_1m_rows_auto_under_five_seconds() -> None:
    with tempfile.TemporaryDirectory() as td:
        src, tgt = _generate_pair(Path(td), 1_000_000)
        elapsed = _run(src, tgt, force_spill=False)
    assert elapsed < 35.0 * _PERF_FACTOR, f"1M auto took {elapsed:.2f}s"


@pytest.mark.performance
@pytest.mark.skipif(not _RUN_SCALE, reason="set PEGASUS_RUN_SCALE_TESTS=1 to run scale gates")
def test_1m_rows_uses_vectorized_spill_not_per_row() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        src, tgt = _generate_pair(work, 1_000_000)
        cfg = TabularPipelineConfig(
            enable_in_memory_reconcile=False,
            force_disk_spill=True,
            enable_column_drilldown=False,
            chunk_rows=50_000,
            streaming_spill_min_bytes=32 * 1024 * 1024,
        )
        with tempfile.TemporaryDirectory() as ws:
            result = TabularReconciliationPipeline(
                FileDelimitedAdapter(src, delimiter="|"),
                FileDelimitedAdapter(tgt, delimiter="|"),
                identity_columns=["id"],
                compare_columns=_COMPARE,
                config=cfg,
            ).run(workspace=Path(ws))
    path = (result.extra_stats or {}).get("path")
    assert path in {"precheck_chunk_merkle", "spill_arrow_ipc", "precheck_spill_partitions"}, (
        f"unexpected slow path: {path}"
    )

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:05:47Z
# --- END GENERATED FILE METADATA ---

"""Throughput assertions for reconciliation pipeline."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline

COMPARE_COLS = [
    "sku",
    "amount",
    "region",
    "attr4",
    "attr5",
    "attr6",
    "attr7",
    "attr8",
    "attr9",
    "attr10",
    "attr11",
]

# Conservative thresholds for 4-core CI; scale with PEGASUS_PERF_FACTOR env (default 1.0).
_PERF_FACTOR = float(os.environ.get("PEGASUS_PERF_FACTOR", "1.0"))


def _mb_per_second(bytes_total: int, elapsed: float) -> float:
    return bytes_total / max(elapsed, 1e-9) / (1024 * 1024)


def _run_pair(src: Path, tgt: Path, *, force_disk: bool, drilldown: bool) -> tuple[float, str, int]:
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=0 if force_disk else 64 * 1024 * 1024,
        force_disk_spill=force_disk,
        enable_column_drilldown=drilldown,
        fingerprint_algorithm="xxhash64",
    )
    src_ad = FileDelimitedAdapter(src, delimiter="||")
    tgt_ad = FileDelimitedAdapter(tgt, delimiter="||")
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        result = TabularReconciliationPipeline(
            src_ad,
            tgt_ad,
            identity_columns=["id"],
            compare_columns=COMPARE_COLS,
            config=cfg,
        ).run(workspace=Path(td))
    return time.perf_counter() - t0, str(result.extra_stats.get("path", "")), result.source_row_count


@pytest.mark.performance
def test_10k_local_throughput() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        pytest.skip("generated 10k dataset missing")

    elapsed, path, rows = _run_pair(src, tgt, force_disk=False, drilldown=False)
    total_bytes = src.stat().st_size + tgt.stat().st_size
    mbps = _mb_per_second(total_bytes, elapsed)
    assert rows == 10_000
    assert path in ("in_memory_polars", "polars_direct", "spill_binary", "spill_arrow_ipc")
    assert mbps >= 8.0 / _PERF_FACTOR, f"10k throughput {mbps:.2f} MB/s below floor (path={path})"


@pytest.mark.performance
def test_100k_local_auto_path_under_ten_seconds() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        pytest.skip("generated 100k dataset missing")

    elapsed, path, rows = _run_pair(src, tgt, force_disk=False, drilldown=False)
    assert rows == 100_000
    assert elapsed < 3.0 * _PERF_FACTOR, f"100k auto path took {elapsed:.2f}s (path={path})"


@pytest.mark.performance
def test_100k_8col_spill_drilldown_under_eight_seconds() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-8cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-8cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        pytest.skip("generated 100k 8-col dataset missing")

    cols = ["sku", "amount", "region", "attr4", "attr5", "attr6", "attr7"]
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=0,
        force_disk_spill=True,
        enable_column_drilldown=True,
        fingerprint_algorithm="xxhash64",
    )
    src_ad = FileDelimitedAdapter(src, delimiter="||")
    tgt_ad = FileDelimitedAdapter(tgt, delimiter="||")
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        result = TabularReconciliationPipeline(
            src_ad,
            tgt_ad,
            identity_columns=["id"],
            compare_columns=cols,
            config=cfg,
        ).run(workspace=Path(td))
    elapsed = time.perf_counter() - t0
    assert result.source_row_count == 100_000
    assert result.extra_stats.get("path") in (
        "spill_binary",
        "spill_columnar",
        "spill_binary_lazy_drilldown",
        "spill_arrow_ipc",
    )
    assert elapsed < 3.5 * _PERF_FACTOR, f"100k spill+drill took {elapsed:.2f}s"


@pytest.mark.performance
def test_100k_disk_spill_under_fifteen_seconds() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-100k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        pytest.skip("generated 100k dataset missing")

    elapsed, path, rows = _run_pair(src, tgt, force_disk=True, drilldown=False)
    assert rows == 100_000
    assert path in (
        "spill_binary",
        "spill_columnar",
        "spill_binary_lazy_drilldown",
        "spill_arrow_ipc",
    )
    assert elapsed < 8.0 * _PERF_FACTOR, f"100k disk spill took {elapsed:.2f}s"

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:01:15Z
# --- END GENERATED FILE METADATA ---

from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import pytest

from pegasus.core.workload_budget import plan_workload_budget
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.drilldown_cache import load_drilldown_lookup
from pegasus.validation.pipeline.fingerprint import (
    canonical,
    identity_key_from_parts,
    partition_id,
    row_fingerprint_from_parts,
)
from pegasus.validation.pipeline.native_spill import native_drilldown_path
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline
from pegasus.validation.pipeline.spill import PartitionWriter
from pegasus.validation.pipeline.timing import PipelineTimings
from pegasus.validation.readers.native_multichar import native_extension_available
from pegasus.validation.pipeline.native_spill import (
    can_use_native_multichar_spill,
    partition_side_native_multichar,
)

_REPO = Path("/home/ansh.raj/Pegasus")
_FIXTURE = _REPO / "test-data/generated-10k-8cols/source.csv"


def test_native_multichar_allowed_with_lazy_drilldown() -> None:
    if not native_extension_available():
        pytest.skip("pegasus_native not built")
    assert can_use_native_multichar_spill(
        store_payload=False,
        use_arrow_ipc_spill=True,
    )


@pytest.mark.skipif(not native_extension_available(), reason="pegasus_native not built")
def test_native_spill_writes_drilldown_ddrill() -> None:
    if not _FIXTURE.is_file():
        pytest.skip("fixture missing")
    headers = _FIXTURE.read_text(encoding="utf-8").splitlines()[0].split("||")
    compare_cols = [c for c in headers if c != "id"]
    adapter = FileDelimitedAdapter(_FIXTURE, delimiter="||")
    timings = PipelineTimings()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        writer = PartitionWriter(root, "source", store_payload=False, compare_columns=compare_cols)
        rows = partition_side_native_multichar(
            adapter,
            writer,
            identity_columns=["id"],
            compare_columns=compare_cols,
            num_partitions=64,
            timings=timings,
            chunk_rows=2500,
            is_source=True,
            lazy_drilldown=True,
        )
        dd_path = native_drilldown_path(root, "source")
        assert rows == 10_000
        assert dd_path.is_file()
        assert dd_path.suffix == ".ddrill"
        lookup = load_drilldown_lookup(root, "source", compare_cols)
        assert len(lookup) == 10_000
        sample_uid = next(iter(lookup))
        assert len(lookup[sample_uid]) == len(compare_cols)
        subset = load_drilldown_lookup(root, "source", compare_cols, keys={sample_uid})
        assert sample_uid in subset


@pytest.mark.skipif(not native_extension_available(), reason="pegasus_native not built")
def test_pipeline_uses_native_drilldown_path() -> None:
    src = _REPO / "test-data/generated-10k-8cols/source.csv"
    tgt = _REPO / "test-data/generated-10k-8cols/target.csv"
    if not src.is_file() or not tgt.is_file():
        pytest.skip("fixture missing")
    cols = [c for c in src.read_text(encoding="utf-8").splitlines()[0].split("||") if c != "id"]
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=0,
        force_disk_spill=True,
        enable_column_drilldown=True,
        force_native_multichar_spill=True,
        fingerprint_only_spill=True,
    )
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        result = TabularReconciliationPipeline(
            FileDelimitedAdapter(src, delimiter="||"),
            FileDelimitedAdapter(tgt, delimiter="||"),
            identity_columns=["id"],
            compare_columns=cols,
            config=cfg,
        ).run(workspace=work)
        assert result.extra_stats.get("path") == "spill_native_multichar_drilldown"
        assert native_drilldown_path(work, "source").is_file()
        assert native_drilldown_path(work, "target").is_file()


@pytest.mark.skipif(not native_extension_available(), reason="pegasus_native not built")
def test_native_mmap_spill_matches_python_fingerprint() -> None:
    if not _FIXTURE.is_file():
        pytest.skip("fixture missing")
    from pegasus.validation.readers import native_multichar

    headers = _FIXTURE.read_text(encoding="utf-8").splitlines()[0].split("||")
    id_idx = headers.index("id")
    compare_cols = [c for c in headers if c != "id"]

    first_data = _FIXTURE.read_text(encoding="utf-8").splitlines()[1].split("||")
    id_parts = [canonical(first_data[id_idx])]
    cmp_parts = [canonical(first_data[headers.index(c)]) for c in compare_cols]
    expected_identity = identity_key_from_parts(id_parts)
    expected_fp = int.from_bytes(
        row_fingerprint_from_parts(cmp_parts, algorithm="xxhash64"),
        "big",
    )
    expected_pid = partition_id(expected_identity, 64)

    def _rows_from_cbl2(block: bytes) -> list[tuple[str, int]]:
        if not block.startswith(b"CBL2") or len(block) < 8:
            return []
        row_count = struct.unpack_from(">I", block, 4)[0]
        offset = 8
        keys: list[str] = []
        for _ in range(row_count):
            key_len = struct.unpack_from(">H", block, offset)[0]
            offset += 2
            keys.append(block[offset : offset + key_len].decode("utf-8"))
            offset += key_len
        rows: list[tuple[str, int]] = []
        for identity in keys:
            fp = int.from_bytes(block[offset : offset + 8], "big")
            offset += 8
            rows.append((identity, fp))
        return rows

    total = 0
    found_fp: int | None = None
    for chunk in native_multichar.iter_mmap_spill_chunks(
        _FIXTURE,
        delimiter="||",
        has_header=True,
        skip_rows=0,
        chunk_rows=2500,
        identity_columns=["id"],
        compare_columns=compare_cols,
        num_partitions=64,
    ):
        total += int(chunk["rows"])
        block = chunk["partitions"].get(expected_pid)
        if block is not None:
            for ident, fp in _rows_from_cbl2(bytes(block)):
                if ident == expected_identity:
                    found_fp = fp
                    break
    assert total == 10_000
    assert found_fp == expected_fp


def test_inline_native_budget_allows_larger_chunks() -> None:
    polars_budget = plan_workload_budget(
        source_bytes=900 * 1024**2,
        target_bytes=900 * 1024**2,
        compare_column_count=7,
        cpu_cores=8,
        memory_budget_bytes=10 * 1024**3,
        target_duration_seconds=60,
        requested_chunk_rows=500_000,
        requested_partition_buckets=256,
        requested_max_workers=4,
        requested_sub_partition_buckets=1,
        source_row_estimate=10_000_000,
        target_row_estimate=10_000_000,
        identity_column_count=1,
        inline_native_spill=False,
    )
    native_budget = plan_workload_budget(
        source_bytes=900 * 1024**2,
        target_bytes=900 * 1024**2,
        compare_column_count=7,
        cpu_cores=8,
        memory_budget_bytes=10 * 1024**3,
        target_duration_seconds=60,
        requested_chunk_rows=500_000,
        requested_partition_buckets=256,
        requested_max_workers=4,
        requested_sub_partition_buckets=1,
        source_row_estimate=10_000_000,
        target_row_estimate=10_000_000,
        identity_column_count=1,
        inline_native_spill=True,
    )
    assert native_budget.chunk_rows >= polars_budget.chunk_rows

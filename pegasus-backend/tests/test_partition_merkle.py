# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T00:00:00+00:00
# --- END GENERATED FILE METADATA ---

"""Streaming partition Merkle digests skip reconcile for identical spilled rows."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import polars as pl

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline
from pegasus.validation.pipeline.partition_merkle import PartitionMerkleAccumulator


def test_partition_merkle_identical_multisets() -> None:
    left = PartitionMerkleAccumulator()
    right = PartitionMerkleAccumulator()
    frame = pl.DataFrame(
        {
            "_identity": ["a", "b"],
            "_fp_hash": [1, 2],
            "_pid": [0, 1],
        }
    )
    for group in frame.partition_by("_pid", maintain_order=True):
        pid = int(group["_pid"][0])
        left.add_group(pid, group["_identity"], group["_fp_hash"])
        right.add_group(pid, group["_identity"], group["_fp_hash"])
    assert left.identical_to(right, {0, 1})


def test_chunk_merkle_short_circuits_identical_local_pair() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        src = work / "source.csv"
        tgt = work / "target.csv"
        for path in (src, tgt):
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, delimiter="|", lineterminator="\n")
                writer.writerow(["id", "sku", "amount"])
                for i in range(20_000):
                    writer.writerow([str(i), f"S{i}", str(i)])

        cfg = TabularPipelineConfig(
            enable_in_memory_reconcile=False,
            force_disk_spill=True,
            enable_column_drilldown=False,
            chunk_rows=5_000,
            partition_count=64,
            streaming_spill_min_bytes=1024,
        )
        result = TabularReconciliationPipeline(
            FileDelimitedAdapter(src, delimiter="|"),
            FileDelimitedAdapter(tgt, delimiter="|"),
            identity_columns=["id"],
            compare_columns=["sku", "amount"],
            config=cfg,
        ).run(workspace=work / "ws")
        assert result.extra_stats.get("path") == "precheck_chunk_merkle"
        assert result.matching_count == 20_000
        assert result.changed_count == 0

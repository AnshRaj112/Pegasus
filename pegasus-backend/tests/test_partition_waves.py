# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-02T05:38:31Z
# --- END GENERATED FILE METADATA ---

"""Tests for partition wave helpers and spill cleanup."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.validation.pipeline.spill import (
    delete_partition_files,
    partition_waves,
    workspace_spill_bytes,
)


def test_partition_waves_splits_evenly() -> None:
    pids = list(range(10))
    waves = partition_waves(pids, 4)
    assert waves == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]


def test_partition_waves_zero_returns_single_wave() -> None:
    pids = [1, 2, 3]
    assert partition_waves(pids, 0) == [pids]


def test_delete_partition_files_frees_bytes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for side in ("source", "target"):
            (work / side).mkdir(parents=True)
        for pid in (1, 2):
            for side in ("source", "target"):
                path = work / side / f"part_{pid:05d}.bin"
                path.write_bytes(b"x" * 100)
        before = workspace_spill_bytes(work)
        assert before == 400
        freed = delete_partition_files(work, [1])
        assert freed == 200
        assert workspace_spill_bytes(work) == 200
        assert not (work / "source" / "part_00001.bin").exists()

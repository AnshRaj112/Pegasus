# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T05:59:19Z
# --- END GENERATED FILE METADATA ---

"""Tests for job size estimation and wave checkpoint helpers."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pegasus.services.job_size_estimate import (
    combined_bytes_from_meta,
    enrich_meta_file_sizes,
    estimate_job_combined_bytes,
)
from pegasus.validation.pipeline.spill import read_wave_checkpoint


def test_combined_bytes_from_meta_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "a.csv"
        tgt = root / "b.csv"
        src.write_bytes(b"x" * 100)
        tgt.write_bytes(b"y" * 200)
        meta = {"source_path": str(src), "target_path": str(tgt)}
        assert combined_bytes_from_meta(meta) == 300


def test_estimate_job_combined_bytes_reads_meta_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job_dir = root / "job"
        job_dir.mkdir()
        src = root / "a.csv"
        tgt = root / "b.csv"
        src.write_bytes(b"x" * 50)
        tgt.write_bytes(b"y" * 70)
        meta = enrich_meta_file_sizes(
            {"source_path": str(src), "target_path": str(tgt)},
        )
        (job_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        assert estimate_job_combined_bytes(job_dir) == 120


def test_read_wave_checkpoint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        assert read_wave_checkpoint(work) == -1
        (work / "wave_checkpoint.json").write_text(
            json.dumps({"completed_wave": 2}),
            encoding="utf-8",
        )
        assert read_wave_checkpoint(work) == 2

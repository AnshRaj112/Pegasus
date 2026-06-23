# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T05:34:17Z
# --- END GENERATED FILE METADATA ---

"""Tests for batch validation API and runner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pegasus.schemas.validation import BatchFailureMode
from pegasus.validation.batch_runner import run_batch_job


def test_batch_runner_completes_two_units() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job_dir = root / "job"
        job_dir.mkdir()
        src1 = root / "s1.csv"
        tgt1 = root / "t1.csv"
        src2 = root / "s2.csv"
        tgt2 = root / "t2.csv"
        src1.write_text("id,v\n1,a\n", encoding="utf-8")
        tgt1.write_text("id,v\n1,a\n", encoding="utf-8")
        src2.write_text("id,v\n1,b\n", encoding="utf-8")
        tgt2.write_text("id,v\n1,c\n", encoding="utf-8")
        meta = {
            "batch": True,
            "on_unit_failure": BatchFailureMode.CONTINUE.value,
            "delimiter": ",",
            "has_header": True,
            "file_format": "csv",
            "batch_units": [
                {
                    "unit_id": "a",
                    "source_path": str(src1),
                    "target_path": str(tgt1),
                    "uid_column": "id",
                },
                {
                    "unit_id": "b",
                    "source_path": str(src2),
                    "target_path": str(tgt2),
                    "uid_column": "id",
                },
            ],
        }
        (job_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        status_path = job_dir / "status.json"

        from pegasus.core.config import Settings

        settings = Settings()
        rc = run_batch_job(
            job_dir=job_dir,
            meta=meta,
            settings=settings,
            status_path=status_path,
            write_status=lambda p, o: p.write_text(json.dumps(o), encoding="utf-8"),
        )
        assert rc == 0
        batch_result = json.loads((job_dir / "batch_result.json").read_text(encoding="utf-8"))
        assert batch_result["summary"]["completed_units"] == 2

"""Validation performance and completion tests."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from pegasus.core.config import get_settings
from pegasus.core.json_util import dumps_bytes
from pegasus.services.validation_service import ValidationService
from pegasus.validation.job_worker import run_job_directory


def test_small_csv_validation_completes_quickly() -> None:
    get_settings.cache_clear()
    service = ValidationService(get_settings())
    src = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    t0 = time.perf_counter()
    result = service._validate_csv_pair_sync(src, tgt, "employee_id", "auto")
    elapsed = time.perf_counter() - t0
    assert result.source_row_count == 3
    assert elapsed < 5.0

    with tempfile.TemporaryDirectory() as td:
        job_dir = Path(td)
        meta = {
            "uid_column": "employee_id",
            "delimiter": "auto",
            "column_mappings": [],
            "has_header": True,
            "header_leading_rows": 0,
            "source_path": str(src),
            "target_path": str(tgt),
            "file_format": "csv",
            "test_mode": "full",
        }
        (job_dir / "meta.json").write_bytes(dumps_bytes(meta))
        t0 = time.perf_counter()
        assert run_job_directory(job_dir) == 0
        assert time.perf_counter() - t0 < 5.0
        assert (job_dir / "result.json").is_file()

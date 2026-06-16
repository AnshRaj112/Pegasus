# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T08:53:50Z
# --- END GENERATED FILE METADATA ---

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
    assert result.pipeline_metadata.get("mismatched_partitions") == 0


def test_10k_12col_local_validation_under_five_seconds() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/generated-10k-12cols/target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    get_settings.cache_clear()
    service = ValidationService(get_settings())
    cols = [
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

    t0 = time.perf_counter()
    result = service._validate_csv_pair_sync(src, tgt, "id", "||", column_mappings=[])
    elapsed = time.perf_counter() - t0

    assert result.source_row_count == 10_000
    assert elapsed < 5.0

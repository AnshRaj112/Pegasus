# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T11:10:12Z
# --- END GENERATED FILE METADATA ---

"""In-memory reconcile is opt-in; default uses streaming spill."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline


def test_force_disk_spill_when_in_memory_disabled() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    spill_cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=1024,
        force_disk_spill=True,
    )
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        pipeline = TabularReconciliationPipeline(
            FileDelimitedAdapter(src, delimiter=","),
            FileDelimitedAdapter(tgt, delimiter=","),
            identity_columns=["employee_id"],
            compare_columns=["name", "department", "salary"],
            config=spill_cfg,
        )
        result = pipeline.run(workspace=work / "spill")
        assert result.source_row_count == 3
        assert result.partitions_processed > 0


def test_in_memory_only_when_explicitly_enabled() -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_source.csv")
    tgt = Path("/home/ansh.raj/Pegasus/test-data/entity-inference/known-entity/employee_28052026_171500_target.csv")
    if not src.is_file() or not tgt.is_file():
        return

    cfg = TabularPipelineConfig(enable_in_memory_reconcile=True, enable_column_drilldown=True)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        pipeline = TabularReconciliationPipeline(
            FileDelimitedAdapter(src, delimiter=","),
            FileDelimitedAdapter(tgt, delimiter=","),
            identity_columns=["employee_id"],
            compare_columns=["name", "department", "salary"],
            config=cfg,
        )
        result = pipeline.run(workspace=work / "mem")
        assert result.source_row_count == 3
        assert result.partitions_processed == 0

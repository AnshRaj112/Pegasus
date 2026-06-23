# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T11:10:12Z
# --- END GENERATED FILE METADATA ---

"""Headerless CSV column names match between schema and in-memory reconcile."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline


def test_headerless_in_memory_uses_column_1_not_column_0() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "source.csv"
        tgt = root / "target.csv"
        src.write_text("1,alpha\n2,beta\n", encoding="utf-8")
        tgt.write_text("1,alpha\n2,gamma\n", encoding="utf-8")

        source = FileDelimitedAdapter(src, delimiter=",", has_header=False)
        target = FileDelimitedAdapter(tgt, delimiter=",", has_header=False)
        assert source.get_schema().column_names == ["column_1", "column_2"]

        cfg = TabularPipelineConfig(enable_in_memory_reconcile=False, auto_in_memory_max_bytes=1024 * 1024)
        result = TabularReconciliationPipeline(
            source,
            target,
            identity_columns=["column_1"],
            compare_columns=["column_2"],
            config=cfg,
        ).run()

        assert result.partitions_processed == 0
        assert result.source_row_count == 2
        assert result.changed_count == 1

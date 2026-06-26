# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:29:35Z
# --- END GENERATED FILE METADATA ---

"""Mismatch NDJSON enrichment for snippet row_detail payloads."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.pipeline.mismatch_export import (
    enrich_mismatch_ndjson_from_lookups,
    ndjson_row_detail_lacks_columns,
)


def test_enrich_missing_row_fills_source_columns() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mismatches.ndjson"
        path.write_text(
            json.dumps(
                {
                    "uid": "100061",
                    "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": json.dumps({"source_record": {"uid": "100061"}, "target_record": None}),
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        assert ndjson_row_detail_lacks_columns(path, ["sku", "amount"])
        updated = enrich_mismatch_ndjson_from_lookups(
            path,
            compare_columns=["sku", "amount"],
            source_lookup={"100061": {"sku": "A1", "amount": "42"}},
            target_lookup={},
        )
        assert updated == 1
        row = json.loads(path.read_text(encoding="utf-8").strip())
        detail = json.loads(row["row_detail"])
        assert detail["source_record"]["sku"] == "A1"
        assert detail["source_record"]["amount"] == "42"
        assert not ndjson_row_detail_lacks_columns(path, ["sku", "amount"])


def test_enrich_value_mismatch_fills_both_sides() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mismatches.ndjson"
        path.write_text(
            json.dumps(
                {
                    "uid": "both",
                    "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                    "column_name": "sku",
                    "source_value": None,
                    "target_value": None,
                    "row_detail": json.dumps(
                        {"source_record": {"uid": "both"}, "target_record": {"uid": "both"}},
                    ),
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        enrich_mismatch_ndjson_from_lookups(
            path,
            compare_columns=["sku"],
            source_lookup={"both": {"sku": "A"}},
            target_lookup={"both": {"sku": "B"}},
        )
        row = json.loads(path.read_text(encoding="utf-8").strip())
        detail = json.loads(row["row_detail"])
        assert detail["source_record"]["sku"] == "A"
        assert detail["target_record"]["sku"] == "B"
        assert row["source_value"] == "A"
        assert row["target_value"] == "B"


def test_export_fp_diff_without_drilldown_uses_lookups(tmp_path, monkeypatch) -> None:
    from io import StringIO

    from pegasus.validation.pipeline import mismatch_export as me

    workspace = tmp_path / "ws"
    (workspace / "source").mkdir(parents=True)
    (workspace / "target").mkdir(parents=True)

    def _fake_load(path, *, compare_columns):
        if "source" in path.parts and path.name == "part_00001.bin":
            return {"2": {"_fp": 111}}
        if "target" in path.parts and path.name == "part_00001.bin":
            return {"2": {"_fp": 222}}
        return {}

    monkeypatch.setattr(me, "_load_partition_entries", _fake_load)
    monkeypatch.setattr(me, "list_partition_ids", lambda _ws, _side: {1})

    buf = StringIO()
    stats = me._export_partitions_to_fp(
        buf,
        workspace,
        [1],
        compare_columns=["name"],
        sensitive_columns=None,
        src_drilldown={},
        tgt_drilldown={},
        source_lookup={"2": {"name": "Alice"}},
        target_lookup={"2": {"name": "Bob"}},
    )
    assert stats.value_mismatch == 1
    row = json.loads(buf.getvalue().strip())
    assert row["uid"] == "2"
    assert row["column_name"] == "name"
    assert row["source_value"] == "Alice"
    assert row["target_value"] == "Bob"

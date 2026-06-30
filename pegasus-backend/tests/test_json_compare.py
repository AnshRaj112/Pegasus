# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T08:29:07Z
# --- END GENERATED FILE METADATA ---

"""Tests for hierarchical JSON document comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.json_compare import compare_json_documents, validate_json_pair

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "test-data" / "json-compare"
GENERATED_FIXTURES = REPO / "test-data" / "generated-test-json"


class TestJsonOrderSensitivity:
    def test_reordered_document_matches_when_order_ignored(self) -> None:
        src = {"items": ["a", "b"], "meta": {"x": 1, "y": 2}}
        tgt = {"meta": {"y": 2, "x": 1}, "items": ["b", "a"]}
        rows = compare_json_documents(src, tgt, uid="document", order_sensitive=False)
        assert rows == []

    def test_reordered_list_mismatches_when_order_required(self) -> None:
        src = {"items": ["a", "b", "c"]}
        tgt = {"items": ["c", "b", "a"]}
        rows = compare_json_documents(src, tgt, uid="document", order_sensitive=True)
        assert len(rows) >= 2
        assert all(r["mismatch_type"] == MismatchType.VALUE_MISMATCH.value for r in rows)

    def test_leaf_value_mismatch_reports_path(self) -> None:
        src = {"success": False}
        tgt = {"success": True}
        rows = compare_json_documents(src, tgt, uid="document", order_sensitive=False)
        assert len(rows) == 1
        assert rows[0]["column_name"] == "success"


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures missing")
class TestJsonFixtures:
    def test_order_insensitive_fixture_is_clean(self) -> None:
        report = validate_json_pair(
            FIXTURES / "order-insensitive-match" / "source.json",
            FIXTURES / "order-insensitive-match" / "target.json",
            order_sensitive=False,
        )
        assert report.summary.get(MismatchType.MISSING_IN_TARGET.value, 0) == 0
        assert report.summary.get(MismatchType.EXTRA_IN_TARGET.value, 0) == 0
        assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0

    def test_order_sensitive_fixture_finds_mismatches(self) -> None:
        report = validate_json_pair(
            FIXTURES / "order-sensitive-mismatch" / "source.json",
            FIXTURES / "order-sensitive-mismatch" / "target.json",
            order_sensitive=True,
        )
        assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) > 0

    def test_order_insensitive_fixture_allows_reordered_lists(self) -> None:
        report = validate_json_pair(
            FIXTURES / "order-sensitive-mismatch" / "source.json",
            FIXTURES / "order-sensitive-mismatch" / "target.json",
            order_sensitive=False,
        )
        assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0

    def test_value_mismatch_fixture(self) -> None:
        report = validate_json_pair(
            FIXTURES / "value-mismatch" / "source.json",
            FIXTURES / "value-mismatch" / "target.json",
            order_sensitive=False,
        )
        total = (
            report.summary.get(MismatchType.MISSING_IN_TARGET.value, 0)
            + report.summary.get(MismatchType.EXTRA_IN_TARGET.value, 0)
            + report.summary.get(MismatchType.VALUE_MISMATCH.value, 0)
        )
        assert total >= 3
        rows = report.mismatches.to_dicts()
        paths = {r["column_name"] for r in rows}
        assert "success" in paths


@pytest.mark.skipif(not GENERATED_FIXTURES.is_dir(), reason="fixtures missing")
class TestGeneratedTestJson:
    """Scalable JSON pair from scripts/generate_json_file.py (500 records, 51 injected mismatches)."""

    def test_order_sensitive_reports_position_and_value_mismatches(self) -> None:
        report = validate_json_pair(
            GENERATED_FIXTURES / "source.json",
            GENERATED_FIXTURES / "target.json",
            order_sensitive=True,
        )
        rows = report.mismatches.to_dicts()
        assert report.summary.get(MismatchType.MISSING_IN_TARGET.value, 0) == 0
        assert report.summary.get(MismatchType.EXTRA_IN_TARGET.value, 0) == 0
        # Reversed errors array + mutated fields surface as per-index value mismatches.
        assert len(rows) == 1001
        assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 1
        assert all(r["mismatch_type"] == MismatchType.VALUE_MISMATCH.value for r in rows)
        paths = {r["column_name"] for r in rows}
        assert "success" in paths

    @pytest.mark.performance
    def test_order_insensitive_allows_list_reorder_but_finds_mutations(self) -> None:
        report = validate_json_pair(
            GENERATED_FIXTURES / "source.json",
            GENERATED_FIXTURES / "target.json",
            order_sensitive=False,
        )
        rows = report.mismatches.to_dicts()
        assert report.summary.get(MismatchType.MISSING_IN_TARGET.value, 0) == 25
        assert report.summary.get(MismatchType.EXTRA_IN_TARGET.value, 0) == 25
        assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 1
        assert len(rows) == 51
        paths = {r["column_name"] for r in rows}
        assert "success" in paths

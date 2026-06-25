# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:27:19Z
# --- END GENERATED FILE METADATA ---

"""Tests for pegasus.validation.comparators.core."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pegasus.validation.comparators.core import col_pairs, eq, scan_complex, validate

REPO = Path(__file__).resolve().parents[2]
STRUCTURED = REPO / "test-data" / "structured-compare" / "csv"


class TestEq:
    @pytest.mark.parametrize(
        "a,b",
        [
            ("19 May 2026", "05/19/2026"),
            ("19 May 2026", "19/05/2026"),
            ("19 May 2026", "05-19-2026"),
            ("01-Jan-2025", "2025-01-01"),
            ("15/08/2024", "08-15-2024"),
            ("12 Dec 2023", "12/12/2023"),
            ("14 Feb 2026", "02/14/2026"),
            ("10.04.2026", "04/10/2026"),
        ],
    )
    def test_flexible_dates(self, a: str, b: str) -> None:
        assert eq(a, b)

    def test_complex_order_insensitive(self) -> None:
        assert eq("[1,2,3]", "[3,2,1]", complex_mode=True, order=False)

    def test_complex_order_sensitive(self) -> None:
        assert not eq("[1,2,3]", "[3,2,1]", complex_mode=True, order=True)


class TestColPairs:
    def test_headerless_index(self) -> None:
        assert col_pairs(None, None, 3) == [(0, 0), (1, 1), (2, 2)]

    def test_source_header_only(self) -> None:
        assert col_pairs(["a", "b"], None, 2) == [("a", 0), ("b", 1)]


class TestValidate:
    def test_headerless_mismatch(self) -> None:
        r = validate([[1, "x"], [2, "y"]], [[1, "x"], [2, "z"]])
        assert len(r["mismatches"]) == 1
        assert r["mismatches"][0]["column"] == 1

    def test_missing_and_extra(self) -> None:
        src = [{"id": "1"}, {"id": "2"}]
        tgt = [{"id": "1"}, {"id": "3"}]
        r = validate(src, tgt, source_header=["id"], target_header=["id"], key="id")
        assert len(r["missing_data"]) == 1 and r["missing_data"][0]["key"] == "2"
        assert len(r["extra_data"]) == 1 and r["extra_data"][0]["key"] == "3"

    def test_complex_scan_flags_order(self) -> None:
        src = [{"id": "1", "tags": '["a"]'}]
        tgt = [{"id": "1", "tags": '["a"]'}]
        r = validate(
            src,
            tgt,
            source_header=["id", "tags"],
            target_header=["id", "tags"],
            key="id",
        )
        assert r["needs_order_preference"] is True
        assert "tags" in r["complex_columns"]

    def test_reordered_list_matches_when_order_ignored(self) -> None:
        src = [{"id": "1", "tags": '["a","b"]'}]
        tgt = [{"id": "1", "tags": '["b","a"]'}]
        r = validate(
            src,
            tgt,
            source_header=["id", "tags"],
            target_header=["id", "tags"],
            key="id",
            complex_order_sensitive=False,
        )
        assert r["mismatches"] == []


def _load_csv_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, [row for row in reader]


@pytest.mark.skipif(not STRUCTURED.joinpath("source.csv").is_file(), reason="fixtures missing")
def test_structured_fixture_end_to_end() -> None:
    sh, src = _load_csv_rows(STRUCTURED / "source.csv")
    th, tgt = _load_csv_rows(STRUCTURED / "target.csv")
    r = validate(
        src,
        tgt,
        source_header=sh,
        target_header=th,
        key="id",
        complex_order_sensitive=False,
    )
    assert len(r["missing_data"]) == 1
    assert len(r["extra_data"]) == 1
    assert len(r["mismatches"]) >= 2


def test_fingerprint_uses_policy_context() -> None:
    from pegasus.validation.comparators.policy import ComparePolicy, ColumnRule, compare_policy_context
    from pegasus.validation.pipeline.fingerprint import canonical

    policy = ComparePolicy(
        rules={"tags": ColumnRule(mode="structured", complex=True, order_sensitive=False)},
    )
    with compare_policy_context(policy):
        assert canonical('["b","a"]', column="tags") == canonical('["a","b"]', column="tags")

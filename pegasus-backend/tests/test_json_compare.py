"""JSON canonical comparison."""

import json
from pathlib import Path

from pegasus.validation.json_compare import collect_json_mismatches, describe_json_mismatch, json_values_equal


def test_json_order_insensitive_objects_and_arrays() -> None:
    a = {
        "errors": [
            {"error": "invalid", "field": "email"},
            {"error": "required", "field": "name"},
        ],
        "success": False,
    }
    b = {
        "success": False,
        "errors": [
            {"error": "required", "field": "name"},
            {"error": "invalid", "field": "email"},
        ],
    }
    assert json_values_equal(a, b)


def test_json_sorted_nested_lists() -> None:
    assert json_values_equal({"foo": [3, 1, 2]}, {"foo": [2, 1, 3]})


def test_json_integral_float_normalized() -> None:
    assert json_values_equal({"n": 1}, {"n": 1.0})
    assert json_values_equal(
        {"errors": [{"error": "invalid", "field": "x", "code": 1}]},
        {"errors": [{"error": "invalid", "field": "x", "code": 1.0}]},
    )


def test_collect_json_mismatches_counts_granular_rows() -> None:
    big = [{"error": "invalid", "field": f"field_{i}"} for i in range(200)]
    left = {"errors": big, "success": False}
    right = {"errors": big, "success": False, "version": 1}
    summary, rows = collect_json_mismatches(left, right)
    assert summary["extra_in_target"] == 1
    assert summary["value_mismatch"] == 0
    assert len(rows) == 1


def test_field_mismatch_suffix_pairs_as_value_mismatch() -> None:
    source = {"errors": [{"error": "required", "field": "field_481"}]}
    target = {"errors": [{"error": "required_mismatch", "field": "field_481_mismatch"}]}
    summary, rows = collect_json_mismatches(source, target)
    assert summary == {"missing_in_target": 0, "extra_in_target": 0, "value_mismatch": 2}
    assert {r["column_name"] for r in rows} == {"error", "field"}
    assert all(r["uid"] == "field_481" for r in rows)


def test_generated_test_json_fifty_attribute_mismatches() -> None:
    root = Path(__file__).resolve().parents[2] / "test-data" / "generated-test-json"
    if not (root / "source.json").is_file():
        return
    src = json.loads((root / "source.json").read_text(encoding="utf-8"))
    tgt = json.loads((root / "target.json").read_text(encoding="utf-8"))
    summary, rows = collect_json_mismatches(src, tgt)
    assert summary["missing_in_target"] == 0
    assert summary["extra_in_target"] == 0
    assert summary["value_mismatch"] == 50
    assert len(rows) == 50


def test_json_mismatch_reports_path_not_only_prefix() -> None:
    big = [{"error": "invalid", "field": f"field_{i}"} for i in range(200)]
    left = {"errors": big, "success": False}
    right = {"errors": big, "success": False, "version": 1}
    assert not json_values_equal(left, right)
    diff = describe_json_mismatch(left, right)
    assert diff["path"] == "$.version"
    assert "version" in diff["detail"] or "keys differ" in diff["detail"]

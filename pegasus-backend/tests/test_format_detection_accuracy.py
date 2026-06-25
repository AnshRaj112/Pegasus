# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:26:33Z
# --- END GENERATED FILE METADATA ---

"""Broad accuracy sweep (~80 cases) for file-type detection and display labels."""

from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path

import pytest

from format_detection_cases import ACCURACY_CASES, AccuracyCase, build_case
from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.display_label import build_format_display_label


@pytest.fixture(scope="module")
def accuracy_results() -> list[dict]:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="pegasus-fmt-acc-") as tmp:
        root = Path(tmp)
        for index, case in enumerate(ACCURACY_CASES):
            work = root / f"case_{index}"
            work.mkdir()
            path = build_case(work, case)
            report = detect_file(path)
            label = build_format_display_label(report, path=path, object_name=path.name)
            rows.append(
                {
                    "name": case.name,
                    "category": case.category,
                    "path": path.name,
                    "expected_label": case.expected_label,
                    "actual_label": label,
                    "expected_format": case.expected_format,
                    "actual_format": report.suggested_file_format,
                    "dataset_model": report.dataset_model,
                    "label_ok": label == case.expected_label,
                    "format_ok": (
                        case.expected_format is None
                        or report.suggested_file_format == case.expected_format
                    ),
                }
            )
    return rows


@pytest.mark.parametrize("case", ACCURACY_CASES, ids=[c.name for c in ACCURACY_CASES])
def test_format_detection_accuracy_case(tmp_path: Path, case: AccuracyCase) -> None:
    path = build_case(tmp_path, case)
    report = detect_file(path)
    label = build_format_display_label(report, path=path, object_name=path.name)
    assert label == case.expected_label, (
        f"label mismatch for {case.name}: got {label!r}, want {case.expected_label!r}"
    )
    if case.expected_format is not None:
        assert report.suggested_file_format == case.expected_format, (
            f"format mismatch for {case.name}: "
            f"got {report.suggested_file_format!r}, want {case.expected_format!r}"
        )


def test_format_detection_accuracy_summary(accuracy_results: list[dict]) -> None:
    label_hits = sum(1 for row in accuracy_results if row["label_ok"])
    format_cases = [row for row in accuracy_results if row["expected_format"] is not None]
    format_hits = sum(1 for row in format_cases if row["format_ok"])
    label_acc = label_hits / len(accuracy_results)
    format_acc = format_hits / len(format_cases) if format_cases else 1.0

    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in accuracy_results:
        by_category[row["category"]].append(row)

    print("\n=== Format detection accuracy (expanded suite) ===")
    print(f"Total cases: {len(accuracy_results)}")
    print(f"Display label accuracy: {label_hits}/{len(accuracy_results)} ({label_acc:.1%})")
    print(f"Suggested format accuracy: {format_hits}/{len(format_cases)} ({format_acc:.1%})")
    print("\nBy category:")
    for category in sorted(by_category):
        rows = by_category[category]
        hits = sum(1 for row in rows if row["label_ok"])
        print(f"  {category:<12} {hits}/{len(rows)} ({hits / len(rows):.0%})")

    print(f"\n{'CASE':<32} {'CATEGORY':<12} {'EXPECTED':<22} {'ACTUAL':<22} {'OK':>3}")
    for row in accuracy_results:
        print(
            f"{row['name']:<32} {row['category']:<12} {row['expected_label']:<22} "
            f"{row['actual_label']:<22} {'OK' if row['label_ok'] else 'MISS':>3}"
        )

    assert label_acc >= 0.95, f"label accuracy {label_acc:.1%} below 95% threshold"
    assert format_acc >= 0.95, f"format accuracy {format_acc:.1%} below 95% threshold"

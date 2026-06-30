# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T08:29:07Z
# --- END GENERATED FILE METADATA ---

"""JSON parent preview and mapping helpers."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.json_parent_preview import (
    align_roots_with_parent_mappings,
    build_json_parent_preview,
    parent_mappings_from_column_mappings,
    suggest_parent_mappings,
)


def test_suggest_parent_mappings_by_name() -> None:
    rows = suggest_parent_mappings(["meta", "items"], ["items", "meta", "extra"])
    paired = {(row["source_parent"], row["target_parent"]) for row in rows if row["source_parent"]}
    assert ("meta", "meta") in paired
    assert ("items", "items") in paired


def test_align_roots_with_parent_mappings() -> None:
    source = {"a": 1, "b": 2}
    target = {"a": 1, "b": 3, "c": 9}
    aligned_source, aligned_target = align_roots_with_parent_mappings(
        source,
        target,
        [("b", "b")],
    )
    assert aligned_source == {"b": 2}
    assert aligned_target == {"b": 3}


def test_build_json_parent_preview_document(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    target = tmp_path / "target.json"
    source.write_text('{"meta": {"x": 1}, "items": [1, 2]}', encoding="utf-8")
    target.write_text('{"meta": {"x": 2}, "items": [1, 2]}', encoding="utf-8")
    preview = build_json_parent_preview(source, target)
    assert preview["document_mode"] == "document"
    assert {field["key"] for field in preview["source_parents"]} == {"meta", "items"}
    assert any(
        row["source_parent"] == "meta" and row["target_parent"] == "meta"
        for row in preview["suggested_mappings"]
    )


def test_parent_mappings_from_column_mappings() -> None:
    pairs = parent_mappings_from_column_mappings([
        {"source_column": "meta", "target_column": "metadata"},
        {"source_column": "items", "target_column": "items"},
    ])
    assert pairs == [("meta", "metadata"), ("items", "items")]

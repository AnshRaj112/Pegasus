"""Recursive directory file listing."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.file_pairing import list_files_in_directory


def test_list_files_recursive(tmp_path: Path) -> None:
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)
    (root / "a.csv").write_text("1\n", encoding="utf-8")
    (sub / "b.csv").write_text("2\n", encoding="utf-8")

    flat = list_files_in_directory(root, file_format="csv", recursive=False)
    deep = list_files_in_directory(root, file_format="csv", recursive=True)

    assert len(flat) == 1
    assert flat[0].name == "a.csv"
    assert len(deep) == 2
    assert {p.name for p in deep} == {"a.csv", "b.csv"}

"""Tests for directory file pairing."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.file_pairing import auto_match_files_by_name, list_files_in_directory


def test_auto_match_by_basename(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    tgt_dir = tmp_path / "tgt"
    src_dir.mkdir()
    tgt_dir.mkdir()
    (src_dir / "a.csv").write_text("1\n", encoding="utf-8")
    (src_dir / "b.csv").write_text("2\n", encoding="utf-8")
    (tgt_dir / "a.csv").write_text("1\n", encoding="utf-8")
    (tgt_dir / "c.csv").write_text("3\n", encoding="utf-8")

    result = auto_match_files_by_name(
        list_files_in_directory(src_dir, file_format="csv"),
        list_files_in_directory(tgt_dir, file_format="csv"),
    )
    assert len(result.pairs) == 1
    assert result.pairs[0].source_path.name == "a.csv"
    assert result.pairs[0].target_path.name == "a.csv"
    assert result.pairs[0].auto_matched is True
    assert [p.name for p in result.unmatched_sources] == ["b.csv"]
    assert [p.name for p in result.unmatched_targets] == ["c.csv"]

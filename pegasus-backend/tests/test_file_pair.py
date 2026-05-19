from __future__ import annotations

from pathlib import Path

from pegasus.core.file_pair import compute_file_pair_key, normalize_validation_path


def test_compute_file_pair_key_stable_for_same_paths(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text("a", encoding="utf-8")
    tgt.write_text("b", encoding="utf-8")
    k1 = compute_file_pair_key(str(src), str(tgt))
    k2 = compute_file_pair_key(str(src.resolve()), str(tgt.resolve()))
    assert k1 is not None
    assert k1 == k2


def test_compute_file_pair_key_differs_for_different_targets(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    t1 = tmp_path / "target1.csv"
    t2 = tmp_path / "target2.csv"
    for p in (src, t1, t2):
        p.write_text("x", encoding="utf-8")
    assert compute_file_pair_key(str(src), str(t1)) != compute_file_pair_key(str(src), str(t2))


def test_normalize_validation_path_returns_none_for_blank() -> None:
    assert normalize_validation_path("   ") is None

"""Tests for shared delimiter resolution across source/target CSV pairs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pegasus.validation.readers.delimiter_detection import (
    DelimiterDetectionResult,
    resolve_shared_auto_delimiter,
)


def test_resolve_shared_picks_consistent_multichar_when_sniffers_disagree(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text("id||name||v\n1||a||10\n2||b||20\n", encoding="utf-8")
    tgt.write_text("id||name||v\n3||c||30\n", encoding="utf-8")

    real = __import__(
        "pegasus.validation.readers.delimiter_detection",
        fromlist=["detect_delimiter"],
    )

    def _fake_detect(path: Path) -> DelimiterDetectionResult:
        if path.name == "source.csv":
            return DelimiterDetectionResult(",", strategy="forced-wrong")
        return DelimiterDetectionResult("||", strategy="forced-right")

    with patch.object(real, "detect_delimiter", side_effect=_fake_detect):
        result = resolve_shared_auto_delimiter(src, tgt)

    assert result.delimiter == "||"


def test_resolve_shared_agrees_when_per_file_detection_matches(tmp_path: Path) -> None:
    p1 = tmp_path / "a.csv"
    p2 = tmp_path / "b.csv"
    p1.write_text("id,name\n1,x\n", encoding="utf-8")
    p2.write_text("id,name\n2,y\n", encoding="utf-8")
    result = resolve_shared_auto_delimiter(p1, p2)
    assert result.delimiter == ","

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T10:19:19Z
# --- END GENERATED FILE METADATA ---

"""Multi-character delimiter parsing tests."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.column_preview import build_column_preview
from pegasus.validation.delimiter_resolve import resolve_delimiter_token
from pegasus.validation.flat_file import normalize_delimiter, split_line


def test_split_line_multi_character() -> None:
    assert split_line("a||b||c", "||") == ["a", "b", "c"]


def test_split_line_emoji_delimiter() -> None:
    assert split_line("x🚀y🚀z", "🚀") == ["x", "y", "z"]


def test_normalize_delimiter_escape_sequences() -> None:
    assert normalize_delimiter("\\t") == "\t"
    assert normalize_delimiter("||") == "||"
    assert normalize_delimiter("🚀") == "🚀"


def test_resolve_delimiter_token_literal_multi_char() -> None:
    assert resolve_delimiter_token("||") == "||"
    assert resolve_delimiter_token("~^|~") == "~^|~"


def test_file_delimited_adapter_multi_char(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("uid||value\n1||alpha\n2||beta\n", encoding="utf-8")
    adapter = FileDelimitedAdapter(path, delimiter="||")
    assert adapter.get_schema().column_names == ["uid", "value"]
    batches = list(adapter.stream_records(10))
    assert batches[0][0]["uid"] == "1"
    assert batches[0][0]["value"] == "alpha"


def test_column_preview_multi_char(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text("id||name\n1||Alice\n", encoding="utf-8")
    tgt.write_text("id||name\n1||Alice\n", encoding="utf-8")
    preview = build_column_preview(
        source_path=src,
        target_path=tgt,
        uid_column="id",
        delimiter="||",
    )
    assert preview["delimiter"] == "||"
    assert preview["source_columns"] == ["id", "name"]
    assert preview["auto_mappings"] == [{"source_column": "name", "target_column": "name"}]


def test_shared_auto_delimiter_uses_lines_for_virtual_gcs_paths() -> None:
    from pegasus.validation.readers.delimiter_detection import resolve_shared_auto_delimiter

    source_path = Path("/gcs/bucket/test-data__generated-10k-fixed_width__source_data.txt")
    target_path = Path("/gcs/bucket/test-data__generated-10k-fixed_width__target_data.txt")
    source_lines = [
        "record_id    name               amount",
        "0000000001Alice               100.00",
        "0000000002Bob                 200.00",
    ]
    target_lines = [
        "record_id    name               amount",
        "0000000001Alice               100.00",
        "0000000002Bobby               200.00",
    ]
    result = resolve_shared_auto_delimiter(
        source_path,
        target_path,
        source_lines=source_lines,
        target_lines=target_lines,
    )
    assert result.delimiter
    assert not source_path.is_file()

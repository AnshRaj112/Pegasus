"""Tests for universal flat-file parsing and schema validation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pegasus.validation.flat_file import (
    ColumnSchema,
    ColumnType,
    EmptyDelimiterError,
    normalize_delimiter,
    parse_and_validate,
    parse_file,
    parse_lines,
    split_line,
    split_physical_lines,
    validate_schema,
)


# --- delimiter normalization ---


def test_normalize_delimiter_tab_aliases() -> None:
    assert normalize_delimiter("tab") == "\t"
    assert normalize_delimiter("\\t") == "\t"


def test_normalize_delimiter_hex_and_unicode_escapes() -> None:
    assert normalize_delimiter(r"\x01") == "\x01"
    assert normalize_delimiter(r"\x1E") == "\x1e"
    assert normalize_delimiter(r"\u200B") == "\u200b"


def test_normalize_delimiter_literal_multi_char_and_emoji() -> None:
    assert normalize_delimiter("|||") == "|||"
    assert normalize_delimiter("~*~") == "~*~"
    assert normalize_delimiter("DELIM") == "DELIM"
    assert normalize_delimiter("🚀") == "🚀"


def test_normalize_delimiter_empty_raises() -> None:
    with pytest.raises(EmptyDelimiterError):
        normalize_delimiter("")


# --- split_line: exotic delimiters with multilingual content ---


def test_split_line_emoji_delimiter_multilingual() -> None:
    delim = "🚀"
    line = f"姓名{delim}العربية{delim}Москва{delim}42"
    assert split_line(line, delim) == ["姓名", "العربية", "Москва", "42"]


def test_split_line_multi_letter_delimiter() -> None:
    line = "alpha" + "xx" + "beta" + "xx" + "gamma"
    assert split_line(line, "xx") == ["alpha", "beta", "gamma"]


def test_split_line_unprintable_control_character() -> None:
    delim = "\x1e"
    line = f"id{delim}value{delim}tail"
    assert split_line(line, delim) == ["id", "value", "tail"]


def test_split_line_standard_delimiters() -> None:
    assert split_line("a,b,c", ",") == ["a", "b", "c"]
    assert split_line("a|b|c", "|") == ["a", "b", "c"]
    assert split_line("a\tb\tc", "\t") == ["a", "b", "c"]
    assert split_line("a b c", " ") == ["a", "b", "c"]


def test_split_line_triple_pipe() -> None:
    assert split_line("one|||two|||three", "|||") == ["one", "two", "three"]


def test_split_line_preserves_unicode_in_fields() -> None:
    line = "हिन्दी🚀日本語"
    assert split_line(line, "🚀") == ["हिन्दी", "日本語"]


# --- full file parse ---


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_parse_file_emoji_delimiter(tmp_path: Path) -> None:
    delim = "🚀"
    _write(
        tmp_path / "data.txt",
        f"id{delim}city{delim}amount\n"
        f"1{delim}北京{delim}100\n"
        f"2{delim}الرياض{delim}200\n",
    )
    result = parse_file(tmp_path / "data.txt", delim)
    assert result.headers == ["id", "city", "amount"]
    assert result.rows == [["1", "北京", "100"], ["2", "الرياض", "200"]]
    assert result.ok


def test_parse_file_xx_delimiter(tmp_path: Path) -> None:
    # Field values must not contain the delimiter substring "xx".
    _write(tmp_path / "data.txt", "id" + "xx" + "label\n1" + "xx" + "ok\n")
    result = parse_file(tmp_path / "data.txt", "xx")
    assert result.headers == ["id", "label"]
    assert result.rows == [["1", "ok"]]


def test_parse_file_unprintable_delimiter(tmp_path: Path) -> None:
    delim = "\x1e"
    _write(tmp_path / "data.txt", f"name{delim}score\nAna{delim}9\n")
    result = parse_file(tmp_path / "data.txt", r"\x1E")
    assert result.delimiter == delim
    assert result.headers == ["name", "score"]
    assert result.rows == [["Ana", "9"]]


def test_parse_lines_column_count_mismatch() -> None:
    lines = ["a,b,c", "1,2", "4,5,6,7"]
    result = parse_lines(lines, ",")
    assert len(result.column_count_errors) == 2
    assert result.column_count_errors[0].row_number == 2
    assert result.column_count_errors[1].row_number == 3
    assert not result.ok


# --- schema validation (Unicode-aware) ---


def test_schema_integer_and_date() -> None:
    lines = ["id,created", "1,2024-01-15", "2,not-a-date"]
    result = parse_lines(lines, ",")
    schema = [
        ColumnSchema("id", type=ColumnType.INTEGER),
        ColumnSchema("created", type=ColumnType.DATE, date_format="%Y-%m-%d"),
    ]
    errors = validate_schema(result, schema)
    assert len(errors) == 1
    assert errors[0].column == "created"
    assert "date" in errors[0].message.lower()


def test_schema_regex_unicode_aware_length() -> None:
    lines = ["word", "café"]
    result = parse_lines(lines, ",")
    schema = [
        ColumnSchema(
            "word",
            min_length=3,
            max_length=10,
            pattern=r"[\w\u00c0-\u024f]+",
        ),
    ]
    errors = validate_schema(result, schema)
    assert errors == []


def test_schema_regex_rejects_non_word_token() -> None:
    lines = ["token", "!!!"]
    result = parse_lines(lines, ",")
    schema = [ColumnSchema("token", pattern=r"\w+")]
    errors = validate_schema(result, schema)
    assert len(errors) == 1


def test_parse_and_validate_end_to_end(tmp_path: Path) -> None:
    delim = "✨"
    _write(
        tmp_path / "full.txt",
        f"id{delim}qty{delim}day\n"
        f"10{delim}5{delim}2025-05-01\n"
        f"xx{delim}1{delim}bad-day\n",
    )
    schema = [
        ColumnSchema("id", type=ColumnType.INTEGER),
        ColumnSchema("qty", type=ColumnType.INTEGER),
        ColumnSchema("day", type=ColumnType.DATE, date_format="%Y-%m-%d"),
    ]
    result = parse_and_validate(tmp_path / "full.txt", delim, schema)
    assert result.headers == ["id", "qty", "day"]
    assert len(result.schema_errors) == 2
    cols = {e.column for e in result.schema_errors}
    assert cols == {"id", "day"}


def test_unicode_integer_digits() -> None:
    """int() accepts digit strings from other scripts (e.g. Arabic-Indic)."""
    lines = ["n", "١٢٣"]
    result = parse_lines(lines, ",")
    schema = [ColumnSchema("n", type=ColumnType.INTEGER)]
    assert validate_schema(result, schema) == []


def test_parse_lines_via_parse_file_multilingual_pipe(tmp_path: Path) -> None:
    _write(
        tmp_path / "pipe.csv",
        "uid|名前|город\n1|太郎|Москва\n",
    )
    result = parse_file(tmp_path / "pipe.csv", "|")
    assert result.rows[0] == ["1", "太郎", "Москва"]


def test_split_physical_lines_does_not_break_on_record_separator() -> None:
    delim = "\x1e"
    text = f"a{delim}b\nc{delim}d\n"
    assert split_physical_lines(text) == [f"a{delim}b", f"c{delim}d"]


def test_split_line_quoted_comma_in_address() -> None:
    line = '1,"Vidit J. Tiwari","Pune, Maharashtra, 123456"'
    assert split_line(line, ",") == [
        "1",
        "Vidit J. Tiwari",
        "Pune, Maharashtra, 123456",
    ]


def test_split_line_unquoted_name_with_periods() -> None:
    assert split_line("42,Vidit J. Tiwari,active", ",") == ["42", "Vidit J. Tiwari", "active"]


def test_parse_lines_quoted_address_column() -> None:
    lines = [
        "id,name,address",
        '10,Alice,"Pune, Maharashtra, 123456"',
        '11,Bob,"Mumbai, MH, 400001"',
    ]
    result = parse_lines(lines, ",")
    assert result.headers == ["id", "name", "address"]
    assert len(result.rows) == 2
    assert result.rows[0][2] == "Pune, Maharashtra, 123456"
    assert result.ok


def test_split_line_empty_delimiter_raises() -> None:
    with pytest.raises(EmptyDelimiterError):
        split_line("a,b", "")


def test_datetime_parsed_in_schema() -> None:
    lines = ["d", "2020-12-31"]
    result = parse_lines(lines, ",")
    schema = [ColumnSchema("d", type=ColumnType.DATE, date_format="%Y-%m-%d")]
    assert validate_schema(result, schema) == []
    parsed = datetime.strptime(result.rows[0][0], "%Y-%m-%d")
    assert parsed.year == 2020

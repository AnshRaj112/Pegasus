"""Tests for delimiter storage normalization."""

import pytest

from pegasus.validation.delimiter_tokens import (
    FIXED_WIDTH_DELIMITER,
    is_fixed_width_delimiter,
    normalize_delimiter_for_storage,
)


def test_fixed_width_aliases_normalize_to_fixed() -> None:
    assert normalize_delimiter_for_storage("fixed-width") == FIXED_WIDTH_DELIMITER
    assert normalize_delimiter_for_storage("fixed_width") == FIXED_WIDTH_DELIMITER
    assert normalize_delimiter_for_storage("fixed") == FIXED_WIDTH_DELIMITER
    assert len(FIXED_WIDTH_DELIMITER) <= 8


def test_csv_delimiter_unchanged() -> None:
    assert normalize_delimiter_for_storage("auto") == "auto"
    assert normalize_delimiter_for_storage(",") == ","


def test_delimiter_too_long_raises() -> None:
    with pytest.raises(ValueError, match="exceeds 8"):
        normalize_delimiter_for_storage("123456789")


def test_is_fixed_width_delimiter() -> None:
    assert is_fixed_width_delimiter("fixed-width")
    assert is_fixed_width_delimiter("fixed")
    assert not is_fixed_width_delimiter(",")

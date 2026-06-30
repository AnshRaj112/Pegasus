# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:37:33Z
# --- END GENERATED FILE METADATA ---

"""Preview column safety cap."""

from __future__ import annotations

import pytest

from pegasus.validation.column_preview import (
    PreviewColumnLimitError,
    _enforce_preview_column_cap,
)


def test_enforce_preview_column_cap_allows_small_sets() -> None:
    _enforce_preview_column_cap(["a", "b"], ["a", "b"])


def test_enforce_preview_column_cap_rejects_wide_parse() -> None:
    wide = [f"col_{i}" for i in range(201)]
    with pytest.raises(PreviewColumnLimitError, match="Too many columns"):
        _enforce_preview_column_cap(wide, ["a"])

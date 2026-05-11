"""Shared typing helpers for the validation engine."""

from __future__ import annotations

from typing import Any, TypeAlias

import polars as pl

FrameLike: TypeAlias = pl.DataFrame | pl.LazyFrame
"""Polars frame types used across readers, parsers, and normalizers."""

JSONDict: TypeAlias = dict[str, Any]
"""Loose structured metadata (options, rule payloads, report headers)."""

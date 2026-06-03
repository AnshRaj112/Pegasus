"""Load Parquet, ORC, Avro, and Excel files into Polars frames."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


class ColumnarReadError(ValueError):
    """Columnar file could not be read."""


def read_columnar_file(path: Path, file_format: str) -> pl.DataFrame:
    """Read a columnar/spreadsheet file into a Polars DataFrame."""
    fmt = (file_format or "").strip().lower().replace("_", "-")
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ColumnarReadError(f"Not a file: {path}")

    try:
        if fmt == "parquet":
            return pl.read_parquet(resolved)
        if fmt == "orc":
            return _read_orc(resolved)
        if fmt == "avro":
            return _read_avro(resolved)
        if fmt in {"excel", "xlsx"}:
            return _read_excel(resolved)
    except Exception as exc:
        raise ColumnarReadError(f"Failed to read {fmt} file {resolved.name}: {exc}") from exc

    raise ColumnarReadError(f"Unsupported columnar format: {fmt!r}")


def columnar_schema(path: Path, file_format: str) -> dict[str, pl.DataType]:
    df = read_columnar_file(path, file_format)
    return dict(zip(df.columns, df.dtypes, strict=True))


def _read_orc(path: Path) -> pl.DataFrame:
    try:
        import pyarrow.orc as orc  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ColumnarReadError("pyarrow ORC support is required for .orc files") from exc
    table = orc.ORCFile(path).read()
    return pl.from_arrow(table)


def _read_avro(path: Path) -> pl.DataFrame:
    try:
        import fastavro  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ColumnarReadError("fastavro is required for .avro files") from exc
    rows: list[dict] = []
    with path.open("rb") as fh:
        reader = fastavro.reader(fh)
        for i, row in enumerate(reader):
            if i >= 2_000_000:
                logger.warning("Avro read capped at 2M rows for %s", path.name)
                break
            if isinstance(row, dict):
                rows.append(row)
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows)


def _read_excel(path: Path) -> pl.DataFrame:
    try:
        import pandas as pd  # noqa: PLC0415 — optional heavy import
    except ImportError as exc:
        raise ColumnarReadError("pandas is required for Excel files") from exc
    try:
        pdf = pd.read_excel(path, engine="openpyxl")
    except ImportError as exc:
        raise ColumnarReadError("openpyxl is required for .xlsx files") from exc
    return pl.from_pandas(pdf, include_index=False)

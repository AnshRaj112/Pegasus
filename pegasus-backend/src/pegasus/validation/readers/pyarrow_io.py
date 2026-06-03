"""PyArrow-backed tabular I/O for validation (CSV, Parquet, ORC).

Single-byte delimiters use :mod:`pyarrow.csv`. Multi-character / emoji delimiters
fall back to the flat-file parser in :mod:`pegasus.validation.flat_file`.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Iterator

import polars as pl
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter

__all__ = (
    "batch_to_dicts",
    "iter_csv_batches",
    "iter_parquet_batches",
    "pyarrow_supports_delimiter",
    "read_csv_binary",
    "read_csv_table",
    "read_orc_table",
    "read_parquet_table",
    "table_to_polars",
)


def pyarrow_supports_delimiter(delimiter: str) -> bool:
    """True when *delimiter* can be parsed by PyArrow CSV (single UTF-8 code unit)."""
    return polars_supports_csv_delimiter(delimiter)


def _csv_read_options(
    *,
    has_header: bool,
    skip_rows: int,
    column_names: list[str] | None = None,
) -> pacsv.ReadOptions:
    if not has_header and column_names:
        return pacsv.ReadOptions(
            skip_rows=skip_rows,
            column_names=column_names,
            autogenerate_column_names=False,
            encoding="UTF8",
        )
    return pacsv.ReadOptions(
        skip_rows=skip_rows,
        autogenerate_column_names=not has_header,
        encoding="UTF8",
    )


def _csv_parse_options(delimiter: str) -> pacsv.ParseOptions:
    return pacsv.ParseOptions(delimiter=delimiter)


def _csv_convert_options() -> pacsv.ConvertOptions:
    return pacsv.ConvertOptions(
        strings_can_be_null=True,
        null_values=["", "NULL", "null", "NA", "N/A", "na", "n/a"],
    )


def read_csv_binary(
    source: BinaryIO,
    *,
    delimiter: str,
    has_header: bool = True,
    skip_rows: int = 0,
    max_rows: int | None = None,
    column_names: list[str] | None = None,
) -> pa.Table:
    """Read delimited bytes from an open binary stream (e.g. GCS object handle)."""
    if not pyarrow_supports_delimiter(delimiter):
        raise ValueError(f"PyArrow CSV does not support delimiter {delimiter!r}")

    read_options = _csv_read_options(
        has_header=has_header,
        skip_rows=skip_rows,
        column_names=column_names,
    )
    parse_options = _csv_parse_options(delimiter)
    convert_options = _csv_convert_options()

    if max_rows is None:
        return pacsv.read_csv(
            source,
            read_options=read_options,
            parse_options=parse_options,
            convert_options=convert_options,
        )

    reader = pacsv.open_csv(
        source,
        read_options=read_options,
        parse_options=parse_options,
        convert_options=convert_options,
    )
    collected: list[pa.RecordBatch] = []
    remaining = max_rows
    for batch in reader:
        if remaining <= 0:
            break
        if batch.num_rows > remaining:
            collected.append(batch.slice(0, remaining))
            remaining = 0
        else:
            collected.append(batch)
            remaining -= batch.num_rows
    if not collected:
        return pa.table({})
    return pa.Table.from_batches(collected)


def read_csv_table(
    path: Path,
    *,
    delimiter: str,
    has_header: bool = True,
    skip_rows: int = 0,
    max_rows: int | None = None,
    column_names: list[str] | None = None,
) -> pa.Table:
    """Read a delimited text file into a PyArrow table."""
    if not pyarrow_supports_delimiter(delimiter):
        raise ValueError(f"PyArrow CSV does not support delimiter {delimiter!r}")

    if max_rows is None:
        with open(path, "rb") as handle:
            return read_csv_binary(
                handle,
                delimiter=delimiter,
                has_header=has_header,
                skip_rows=skip_rows,
                column_names=column_names,
            )

    reader = pacsv.open_csv(
        path,
        read_options=_csv_read_options(
            has_header=has_header,
            skip_rows=skip_rows,
            column_names=column_names,
        ),
        parse_options=_csv_parse_options(delimiter),
        convert_options=_csv_convert_options(),
    )
    collected: list[pa.RecordBatch] = []
    remaining = max_rows
    for batch in reader:
        if remaining <= 0:
            break
        if batch.num_rows > remaining:
            collected.append(batch.slice(0, remaining))
            remaining = 0
        else:
            collected.append(batch)
            remaining -= batch.num_rows
    if not collected:
        return pa.table({})
    return pa.Table.from_batches(collected)


def read_csv_bytes(
    data: bytes,
    *,
    delimiter: str,
    has_header: bool = True,
    skip_rows: int = 0,
    column_names: list[str] | None = None,
) -> pa.Table:
    """Parse in-memory CSV bytes (reuses a cached GCS prefix when the blob is small)."""
    return read_csv_binary(
        BytesIO(data),
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=skip_rows,
        column_names=column_names,
    )


def iter_csv_batches(
    path: Path,
    *,
    delimiter: str,
    chunk_rows: int,
    has_header: bool = True,
    skip_rows: int = 0,
) -> Iterator[pa.RecordBatch]:
    """Stream a delimited file as PyArrow record batches."""
    if not pyarrow_supports_delimiter(delimiter):
        raise ValueError(f"PyArrow CSV does not support delimiter {delimiter!r}")

    reader = pacsv.open_csv(
        path,
        read_options=_csv_read_options(has_header=has_header, skip_rows=skip_rows),
        parse_options=_csv_parse_options(delimiter),
        convert_options=_csv_convert_options(),
    )
    target = max(1, chunk_rows)
    for batch in reader:
        if batch.num_rows == 0:
            continue
        if batch.num_rows <= target:
            yield batch
            continue
        offset = 0
        while offset < batch.num_rows:
            size = min(target, batch.num_rows - offset)
            yield batch.slice(offset, size)
            offset += size


def read_parquet_table(path: Path) -> pa.Table:
    return pq.read_table(path)


def iter_parquet_batches(path: Path, *, batch_size: int) -> Iterator[pa.RecordBatch]:
    parquet_file = pq.ParquetFile(path)
    yield from parquet_file.iter_batches(batch_size=max(1, batch_size))


def read_orc_table(path: Path) -> pa.Table:
    import pyarrow.orc as porc

    return porc.read_table(path)


def iter_orc_batches(path: Path, *, batch_size: int) -> Iterator[pa.RecordBatch]:
    """Yield ORC rows in batches (loads via PyArrow then slices)."""
    table = read_orc_table(path)
    if table.num_rows == 0:
        return
    step = max(1, batch_size)
    for offset in range(0, table.num_rows, step):
        yield table.slice(offset, min(step, table.num_rows - offset)).to_batches()[0]


def table_to_polars(table: pa.Table) -> pl.DataFrame:
    string_cols = [table.column(i).cast(pa.string()) for i in range(table.num_columns)]
    string_table = pa.table({name: col for name, col in zip(table.column_names, string_cols)})
    return pl.from_arrow(string_table)


def batch_to_dicts(batch: pa.RecordBatch) -> list[dict[str, Any]]:
    string_cols = [batch.column(i).cast(pa.string()) for i in range(batch.num_columns)]
    string_batch = pa.RecordBatch.from_arrays(string_cols, names=list(batch.schema.names))
    return pl.from_arrow(string_batch).to_dicts()

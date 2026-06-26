# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T06:51:30Z
# --- END GENERATED FILE METADATA ---

"""Delimited file adapter (CSV, TSV, PSV) with chunked streaming."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterator

import xxhash

from pegasus.validation.adapters.base import TabularColumn, TabularSchema
from pegasus.validation.csv_header import count_fields_first_row, read_first_row_fields, synthetic_column_names
from pegasus.validation.flat_file import split_line
from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter
from pegasus.validation.readers.pyarrow_io import batch_to_dicts, iter_csv_batches, pyarrow_supports_delimiter


class FileDelimitedAdapter:
    """Streams delimited text files without loading the full dataset."""

    __slots__ = (
        "path",
        "_delimiter",
        "_has_header",
        "_skip_rows",
        "_encoding",
        "_column_names",
        "_data_row_count",
        "_content_digest_hex",
    )

    def __init__(
        self,
        path: Path,
        *,
        delimiter: str = ",",
        has_header: bool = True,
        skip_rows: int = 0,
        encoding: str = "utf-8",
    ) -> None:
        self.path = Path(path)
        self._delimiter = delimiter
        self._has_header = has_header
        self._skip_rows = skip_rows
        self._encoding = encoding
        self._column_names: list[str] | None = None
        self._data_row_count: int | None = None
        self._content_digest_hex: str | None = None

    _DIGEST_BLOCK_BYTES = 4 * 1024 * 1024

    def content_digest_hex(self) -> str | None:
        """Lazy xxhash64 of raw file bytes for content-digest precheck."""
        if self._content_digest_hex is not None:
            return self._content_digest_hex
        if not self.path.is_file():
            return None
        hasher = xxhash.xxh64()
        try:
            with open(self.path, "rb") as f:
                while True:
                    block = f.read(self._DIGEST_BLOCK_BYTES)
                    if not block:
                        break
                    hasher.update(block)
        except OSError:
            return None
        self._content_digest_hex = f"xxh64:{hasher.hexdigest()}"
        return self._content_digest_hex

    def get_size_bytes(self) -> int:
        return self.path.stat().st_size

    def get_bytes_read(self) -> int:
        return self.get_size_bytes()

    def _effective_delimiter(self, physical_line: str) -> str:
        delim = self._delimiter
        if delim == "xx" and "xx" not in physical_line and r"~\^|~" in physical_line:
            return r"~\^|~"
        return delim

    def _split_physical_line(self, line: str) -> list[str]:
        physical = line.rstrip("\r\n")
        if not physical:
            return []
        delim = self._effective_delimiter(physical)
        if polars_supports_csv_delimiter(delim):
            try:
                return next(
                    csv.reader(
                        [physical],
                        delimiter=delim,
                        quotechar='"',
                        doublequote=True,
                    )
                )
            except csv.Error:
                pass
        return split_line(physical, delim)

    def _read_header(self) -> list[str]:
        if self._column_names is not None:
            return self._column_names
        if self._has_header:
            self._column_names = read_first_row_fields(self.path, self._delimiter)
        else:
            n_cols = count_fields_first_row(self.path, self._delimiter)
            self._column_names = synthetic_column_names(n_cols)
        return self._column_names

    def _iter_data_rows(self) -> Iterator[list[str]]:
        with open(self.path, encoding=self._encoding, newline="", errors="replace") as f:
            for _ in range(self._skip_rows):
                f.readline()
            if self._has_header:
                f.readline()
            if polars_supports_csv_delimiter(self._delimiter):
                reader = csv.reader(f, delimiter=self._delimiter, quotechar='"', doublequote=True)
                for row in reader:
                    if not row or (len(row) == 1 and not row[0].strip()):
                        continue
                    yield row
                return
            for line in f:
                if not line.strip():
                    continue
                fields = self._split_physical_line(line)
                if fields:
                    yield fields

    def _stream_records_pyarrow(self, chunk_rows: int) -> Iterator[list[dict[str, Any]]]:
        header_names = self._read_header()
        for batch in iter_csv_batches(
            self.path,
            delimiter=self._delimiter,
            chunk_rows=chunk_rows,
            has_header=self._has_header,
            skip_rows=self._skip_rows,
            column_names=header_names,
        ):
            records = batch_to_dicts(batch)
            if records:
                yield records

    def get_schema(self) -> TabularSchema:
        names = self._read_header()
        return TabularSchema(
            columns=[TabularColumn(name=n, data_type="string") for n in names]
        )

    def get_row_count(self) -> int | None:
        if self._data_row_count is not None:
            return self._data_row_count
        from pegasus.validation.row_count import count_delimited_data_rows

        self._data_row_count = count_delimited_data_rows(self)
        return self._data_row_count

    def stream_records(self, chunk_rows: int) -> Iterator[list[dict[str, Any]]]:
        if pyarrow_supports_delimiter(self._delimiter):
            yield from self._stream_records_pyarrow(chunk_rows)
            return

        names = self._read_header()
        chunk: list[dict[str, Any]] = []
        for row in self._iter_data_rows():
            record = {names[i]: (row[i] if i < len(row) else None) for i in range(len(names))}
            chunk.append(record)
            if len(chunk) >= chunk_rows:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

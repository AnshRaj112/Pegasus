# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-11T09:32:43Z
# --- END GENERATED FILE METADATA ---

"""Stream delimited objects from GCS — no full-object download or local materialization."""

from __future__ import annotations

import csv
import io
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterator

from pegasus.validation.adapters.base import TabularColumn, TabularSchema
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.csv_header import synthetic_column_names
from pegasus.validation.flat_file import split_line
from pegasus.validation.gcs_object import GcsObjectRef, gcs_blob_fingerprints
from pegasus.validation.gcs_stream import GcsStreamSession, get_gcs_stream_session
from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter
from pegasus.validation.readers.pyarrow_io import batch_to_dicts, pyarrow_supports_delimiter

_HEADER_PREFIX_BYTES = 256 * 1024
_SAMPLE_PREFIX_BYTES = 512 * 1024


def inherit_gcs_metadata(
    source: GcsDelimitedAdapter | None,
    target: GcsDelimitedAdapter,
) -> None:
    """Copy metadata and session stats when rebuilding an adapter (e.g. delimiter resolve)."""
    if source is None or source is target:
        return
    if source._size_bytes is not None:
        target._size_bytes = source._size_bytes
    target._crc32c = source._crc32c
    target._md5_hex = source._md5_hex
    target._metadata_digest = source._metadata_digest
    target._network_transfer_seconds = max(
        target._network_transfer_seconds,
        source._network_transfer_seconds,
    )
    if source._header_prefix is not None:
        target._header_prefix = source._header_prefix
    target._prefix_bytes_requested = max(
        target._prefix_bytes_requested,
        source._prefix_bytes_requested,
    )
    if source._column_names is not None:
        target._column_names = list(source._column_names)
    if source._data_row_count is not None:
        target._data_row_count = source._data_row_count


# Backward-compatible alias
inherit_gcs_cache = inherit_gcs_metadata


def prefetch_gcs_delimited_pair(
    source: FileDelimitedAdapter | GcsDelimitedAdapter,
    target: FileDelimitedAdapter | GcsDelimitedAdapter,
    *,
    max_cache_bytes: int = 0,  # noqa: ARG001 — kept for API compat; no full download
) -> None:
    """Warm GCS metadata in parallel (no object body download)."""
    adapters: list[GcsDelimitedAdapter] = []
    for adapter in (source, target):
        if isinstance(adapter, GcsDelimitedAdapter):
            adapters.append(adapter)
    if not adapters:
        return

    def _warm(adapter: GcsDelimitedAdapter) -> None:
        adapter.warm_metadata()

    if len(adapters) == 1:
        _warm(adapters[0])
        return

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(_warm, adapters))


class GcsDelimitedAdapter:
    """Streams a GCS object as delimited rows via PyArrow CSV or line iteration."""

    __slots__ = (
        "_ref",
        "_delimiter",
        "_has_header",
        "_skip_rows",
        "_encoding",
        "_column_names",
        "_size_bytes",
        "_header_prefix",
        "_prefix_bytes_requested",
        "_metadata_digest",
        "_crc32c",
        "_md5_hex",
        "_network_transfer_seconds",
        "_session",
        "_data_row_count",
    )

    def __init__(
        self,
        ref: GcsObjectRef,
        *,
        delimiter: str = ",",
        has_header: bool = True,
        skip_rows: int = 0,
        encoding: str = "utf-8",
        size_bytes: int | None = None,
    ) -> None:
        self._ref = ref
        self._delimiter = delimiter
        self._has_header = has_header
        self._skip_rows = skip_rows
        self._encoding = encoding
        self._column_names: list[str] | None = None
        self._size_bytes = size_bytes
        self._header_prefix: bytes | None = None
        self._prefix_bytes_requested: int = 0
        self._metadata_digest: str | None = None
        self._crc32c: str | None = None
        self._md5_hex: str | None = None
        self._network_transfer_seconds: float = 0.0
        self._session: GcsStreamSession | None = None
        self._data_row_count: int | None = None

    def _stream_session(self) -> GcsStreamSession:
        if self._session is None:
            self._session = get_gcs_stream_session(self._ref)
        return self._session

    def _sync_network_stats(self) -> None:
        self._network_transfer_seconds = max(
            self._network_transfer_seconds,
            self._stream_session().network_transfer_seconds,
        )

    @property
    def network_transfer_seconds(self) -> float:
        self._sync_network_stats()
        return self._network_transfer_seconds

    @property
    def path(self) -> Path:
        return self._ref.display_path

    @property
    def gcs_uri(self) -> str:
        return self._ref.uri

    def get_size_bytes(self) -> int:
        if self._size_bytes is None:
            self._size_bytes = gcs_blob_fingerprints(self._ref)[0]
        return self._size_bytes

    def get_bytes_read(self) -> int:
        """Bytes consumed from GCS during streaming (falls back to object size)."""
        self._sync_network_stats()
        nbytes = self._stream_session().bytes_read
        if nbytes > 0:
            return nbytes
        return self.get_size_bytes()

    def warm_metadata(self) -> None:
        """Fetch size/CRC32C/MD5 from GCS metadata (no body read)."""
        if self._crc32c is not None and self._md5_hex is not None and self._size_bytes is not None:
            return
        try:
            size, crc, md5 = gcs_blob_fingerprints(self._ref)
            if self._size_bytes is None:
                self._size_bytes = size
            self._crc32c = crc
            self._md5_hex = md5
            if md5:
                self._metadata_digest = f"md5:{md5}"
            elif crc:
                self._metadata_digest = f"crc32c:{crc}"
        except Exception:
            pass

    def content_digest_hex(self) -> str | None:
        """Metadata-based identity (GCS MD5/CRC32C), not a full-file hash."""
        if self._metadata_digest is None:
            self.warm_metadata()
        return self._metadata_digest

    def cached_object_bytes(self) -> bytes | None:
        """Full-object cache is intentionally unavailable (streaming-only)."""
        return None

    def ensure_object_cached(self, *, max_cache_bytes: int = 0) -> None:
        """No-op — retained for callers that previously prefetched full objects."""
        self.warm_metadata()

    def _ensure_prefix_bytes(self, limit: int) -> bytes:
        """Single cached prefix fetch shared by header and delimiter sampling."""
        size = self.get_size_bytes()
        fetch = min(limit, size) if size > 0 else limit
        if self._header_prefix is not None and self._prefix_bytes_requested >= fetch:
            return self._header_prefix
        t0 = time.perf_counter()
        prefix = self._stream_session().read_prefix(max_bytes=fetch)
        self._network_transfer_seconds += time.perf_counter() - t0
        if self._header_prefix is None or len(prefix) > len(self._header_prefix):
            self._header_prefix = prefix
        self._prefix_bytes_requested = max(self._prefix_bytes_requested, fetch)
        return self._header_prefix

    def _load_header_prefix(self) -> bytes:
        return self._ensure_prefix_bytes(_HEADER_PREFIX_BYTES)

    def _load_sample_prefix(self) -> bytes:
        return self._ensure_prefix_bytes(_SAMPLE_PREFIX_BYTES)

    def sample_lines(self, *, max_lines: int = 500) -> list[str]:
        prefix = self._load_sample_prefix().decode(self._encoding, errors="replace")
        out: list[str] = []
        for line in prefix.splitlines():
            stripped = line.strip()
            if stripped:
                out.append(stripped)
            if len(out) >= max_lines:
                break
        return out

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
                return next(csv.reader([physical], delimiter=delim, quotechar='"', doublequote=True))
            except csv.Error:
                pass
        return split_line(physical, delim)

    def _read_header_from_prefix(self) -> list[str]:
        prefix = self._load_header_prefix().decode("utf-8-sig", errors="replace")
        if self._has_header:
            if polars_supports_csv_delimiter(self._delimiter):
                reader = csv.reader(
                    io.StringIO(prefix),
                    delimiter=self._delimiter,
                    quotechar='"',
                    doublequote=True,
                )
                for _ in range(self._skip_rows):
                    next(reader, None)
                first = next(reader, None)
                if not first:
                    return []
                return [cell.strip() for cell in first]
            lines = prefix.splitlines()
            idx = self._skip_rows
            while idx < len(lines) and not lines[idx].strip():
                idx += 1
            if idx >= len(lines):
                return []
            return [cell.strip() for cell in self._split_physical_line(lines[idx])]

        lines = [line for line in prefix.splitlines() if line.strip()]
        data_idx = self._skip_rows
        if data_idx >= len(lines):
            return synthetic_column_names(1)
        fields = self._split_physical_line(lines[data_idx])
        return synthetic_column_names(max(1, len(fields)))

    def _read_header(self) -> list[str]:
        if self._column_names is not None:
            return self._column_names
        self._column_names = self._read_header_from_prefix()
        return self._column_names

    def _iter_data_rows(self) -> Iterator[list[str]]:
        with self._stream_session().open_binary() as handle:
            text = io.TextIOWrapper(handle, encoding=self._encoding, errors="replace", newline="")
            yield from self._iter_text_rows(text)

    def _iter_text_rows(self, text: io.TextIOWrapper) -> Iterator[list[str]]:
        for _ in range(self._skip_rows):
            text.readline()
        if self._has_header:
            text.readline()
        if polars_supports_csv_delimiter(self._delimiter):
            reader = csv.reader(text, delimiter=self._delimiter, quotechar='"', doublequote=True)
            for row in reader:
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue
                yield row
            return
        for line in text:
            if not line.strip():
                continue
            fields = self._split_physical_line(line)
            if fields:
                yield fields

    def _stream_records_pyarrow(self, chunk_rows: int) -> Iterator[list[dict[str, Any]]]:
        import pyarrow.csv as pacsv

        from pegasus.validation.readers.pyarrow_io import (
            _csv_convert_options,
            _csv_parse_options,
            _csv_read_options,
        )

        header_names = self._read_header()
        with self._stream_session().open_binary() as handle:
            reader = pacsv.open_csv(
                handle,
                read_options=_csv_read_options(
                    has_header=self._has_header,
                    skip_rows=self._skip_rows,
                    column_names=header_names,
                ),
                parse_options=_csv_parse_options(self._delimiter),
                convert_options=_csv_convert_options(column_names=header_names),
            )
            target = max(1, chunk_rows)
            for batch in reader:
                if batch.num_rows == 0:
                    continue
                if batch.num_rows <= target:
                    records = batch_to_dicts(batch)
                    if records:
                        yield records
                    continue
                offset = 0
                while offset < batch.num_rows:
                    size = min(target, batch.num_rows - offset)
                    slice_batch = batch.slice(offset, size)
                    records = batch_to_dicts(slice_batch)
                    if records:
                        yield records
                    offset += size
        self._sync_network_stats()

    def get_schema(self) -> TabularSchema:
        names = self._read_header()
        return TabularSchema(columns=[TabularColumn(name=n, data_type="string") for n in names])

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


def create_delimited_adapter(
    *,
    path: Path | None,
    ref: GcsObjectRef | None,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
) -> FileDelimitedAdapter | GcsDelimitedAdapter:
    if ref is not None:
        return GcsDelimitedAdapter(
            ref,
            delimiter=delimiter,
            has_header=has_header,
            skip_rows=skip_rows,
        )
    if path is None:
        raise ValueError("path or GCS reference is required")
    return FileDelimitedAdapter(
        path,
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=skip_rows,
    )

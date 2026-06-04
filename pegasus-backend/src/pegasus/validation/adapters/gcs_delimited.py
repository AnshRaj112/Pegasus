# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-03T15:30:26+05:30
# --- END GENERATED FILE METADATA ---

"""Stream delimited objects from GCS without downloading the full file."""

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
from pegasus.validation.gcs_object import (
    GcsObjectRef,
    gcs_blob_size,
    open_gcs_binary,
    read_gcs_object_bytes,
    read_gcs_prefix,
)
from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter
from pegasus.validation.readers.pyarrow_io import batch_to_dicts, pyarrow_supports_delimiter

_DEFAULT_MAX_CACHE_BYTES = 512 * 1024 * 1024


def inherit_gcs_cache(
    source: GcsDelimitedAdapter | None,
    target: GcsDelimitedAdapter,
) -> None:
    """Copy downloaded bytes from *source* adapter onto *target* (e.g. after delimiter rebuild)."""
    if source is None or source is target:
        return
    if source._cached_full is not None:
        target._cached_full = source._cached_full
        target._cached_prefix = source._cached_prefix
        target._digest_hex = source._digest_hex
    elif source._cached_prefix is not None and (
        target._cached_prefix is None or len(source._cached_prefix) > len(target._cached_prefix)
    ):
        target._cached_prefix = source._cached_prefix
    if source._size_bytes is not None:
        target._size_bytes = source._size_bytes
    target._crc32c = source._crc32c
    target._md5_hex = source._md5_hex
    target._network_transfer_seconds = max(
        target._network_transfer_seconds,
        source._network_transfer_seconds,
    )


def _digest_payload(payload: bytes) -> str:
    try:
        import xxhash

        return xxhash.xxh64(payload).hexdigest()
    except ImportError:
        import hashlib

        return hashlib.sha256(payload).hexdigest()


def prefetch_gcs_delimited_pair(
    source: FileDelimitedAdapter | GcsDelimitedAdapter,
    target: FileDelimitedAdapter | GcsDelimitedAdapter,
    *,
    max_cache_bytes: int = _DEFAULT_MAX_CACHE_BYTES,
) -> None:
    """Parallel one-shot download for GCS objects that fit in the cache budget."""
    adapters: list[GcsDelimitedAdapter] = []
    for adapter in (source, target):
        if isinstance(adapter, GcsDelimitedAdapter):
            adapters.append(adapter)
    if not adapters:
        return

    def _warm(adapter: GcsDelimitedAdapter) -> None:
        adapter.warm_metadata()
        adapter.ensure_object_cached(max_cache_bytes=max_cache_bytes)

    if len(adapters) == 1:
        _warm(adapters[0])
        return

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(_warm, adapters))


class GcsDelimitedAdapter:
    """Streams a GCS object as delimited rows (chunked reads only)."""

    __slots__ = (
        "_ref",
        "_delimiter",
        "_has_header",
        "_skip_rows",
        "_encoding",
        "_column_names",
        "_size_bytes",
        "_cached_prefix",
        "_cached_full",
        "_digest_hex",
        "_crc32c",
        "_md5_hex",
        "_network_transfer_seconds",
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
        self._cached_prefix: bytes | None = None
        self._cached_full: bytes | None = None
        self._digest_hex: str | None = None
        self._crc32c: str | None = None
        self._md5_hex: str | None = None
        self._network_transfer_seconds: float = 0.0

    @property
    def network_transfer_seconds(self) -> float:
        return self._network_transfer_seconds

    @property
    def path(self) -> Path:
        return self._ref.display_path

    @property
    def gcs_uri(self) -> str:
        return self._ref.uri

    def get_size_bytes(self) -> int:
        if self._size_bytes is None:
            self._size_bytes = gcs_blob_size(self._ref)
        return self._size_bytes

    def warm_metadata(self) -> None:
        """Fetch GCS CRC32C/MD5 once when not already supplied by the caller."""
        if self._crc32c is not None or self._md5_hex is not None:
            return
        if self._size_bytes is not None:
            return
        try:
            from pegasus.validation.gcs_object import gcs_blob_fingerprints

            size, crc, md5 = gcs_blob_fingerprints(self._ref)
            if self._size_bytes is None:
                self._size_bytes = size
            self._crc32c = crc
            self._md5_hex = md5
        except Exception:
            pass

    def content_digest_hex(self) -> str | None:
        return self._digest_hex

    def ensure_object_cached(self, *, max_cache_bytes: int = _DEFAULT_MAX_CACHE_BYTES) -> bytes | None:
        """Download the full object once when it fits *max_cache_bytes*."""
        if self._cached_full is not None:
            return self._cached_full
        size = self.get_size_bytes()
        if size <= 0 or size > max_cache_bytes:
            return None
        t0 = time.perf_counter()
        payload = read_gcs_object_bytes(self._ref)
        self._network_transfer_seconds += time.perf_counter() - t0
        self._cached_full = payload
        self._cached_prefix = payload
        self._digest_hex = _digest_payload(payload)
        return payload

    def _load_prefix_bytes(self, *, max_bytes: int) -> bytes:
        if self._cached_full is not None:
            return self._cached_full[:max_bytes]
        if self._cached_prefix is not None and len(self._cached_prefix) >= max_bytes:
            return self._cached_prefix[:max_bytes]
        size = self.get_size_bytes()
        if size > 0 and size <= max_bytes:
            full = self.ensure_object_cached(max_cache_bytes=size)
            if full is not None:
                return full
        read_limit = min(max_bytes, size) if size > 0 else max_bytes
        t0 = time.perf_counter()
        payload = read_gcs_prefix(self._ref, max_bytes=read_limit)
        self._network_transfer_seconds += time.perf_counter() - t0
        if self._cached_prefix is None or len(payload) > len(self._cached_prefix):
            self._cached_prefix = payload
        return payload

    def cached_object_bytes(self) -> bytes | None:
        """Return cached object bytes when the full blob is available locally."""
        if self._cached_full is not None:
            return self._cached_full
        if self._cached_prefix is None:
            return None
        size = self.get_size_bytes()
        if size > 0 and len(self._cached_prefix) >= size:
            return self._cached_prefix
        return None

    def sample_lines(self, *, max_lines: int = 500) -> list[str]:
        size = self.get_size_bytes()
        if size > 0 and size <= _DEFAULT_MAX_CACHE_BYTES:
            payload = self.ensure_object_cached(max_cache_bytes=_DEFAULT_MAX_CACHE_BYTES)
            if payload is not None:
                prefix = payload.decode(self._encoding, errors="replace")
            else:
                prefix = self._load_prefix_bytes(
                    max_bytes=min(512 * 1024, size),
                ).decode(self._encoding, errors="replace")
        else:
            max_bytes = min(512 * 1024, size) if size > 0 else 512 * 1024
            prefix = self._load_prefix_bytes(max_bytes=max_bytes).decode(
                self._encoding, errors="replace"
            )
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
        size = self.get_size_bytes()
        if size > 0 and size <= _DEFAULT_MAX_CACHE_BYTES:
            payload = self.ensure_object_cached(max_cache_bytes=_DEFAULT_MAX_CACHE_BYTES)
            if payload is None:
                max_bytes = min(256 * 1024, size)
                prefix = self._load_prefix_bytes(max_bytes=max_bytes).decode(
                    self._encoding, errors="replace"
                )
            else:
                prefix = payload.decode(self._encoding, errors="replace")
        else:
            max_bytes = min(256 * 1024, size) if size > 0 else 256 * 1024
            prefix = self._load_prefix_bytes(max_bytes=max_bytes).decode(
                self._encoding, errors="replace"
            )
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
        cached = self.cached_object_bytes()
        if cached is not None:
            text = io.BytesIO(cached)
            wrapper = io.TextIOWrapper(text, encoding=self._encoding, errors="replace", newline="")
            yield from self._iter_text_rows(wrapper)
            return

        with open_gcs_binary(self._ref) as handle:
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
            read_csv_bytes,
        )

        cached = self.cached_object_bytes()
        if cached is not None:
            table = read_csv_bytes(
                cached,
                delimiter=self._delimiter,
                has_header=self._has_header,
                skip_rows=self._skip_rows,
            )
            target = max(1, chunk_rows)
            for batch in table.to_batches(max_chunksize=target):
                if batch.num_rows == 0:
                    continue
                records = batch_to_dicts(batch)
                if records:
                    yield records
            return

        with open_gcs_binary(self._ref) as handle:
            reader = pacsv.open_csv(
                handle,
                read_options=_csv_read_options(has_header=self._has_header, skip_rows=self._skip_rows),
                parse_options=_csv_parse_options(self._delimiter),
                convert_options=_csv_convert_options(),
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

    def get_schema(self) -> TabularSchema:
        names = self._read_header()
        return TabularSchema(columns=[TabularColumn(name=n, data_type="string") for n in names])

    def get_row_count(self) -> int | None:
        return None

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

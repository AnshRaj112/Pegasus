# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T07:47:43Z
# --- END GENERATED FILE METADATA ---

"""Stream columnar objects from GCS — bounded download for schema/profile/preview."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Iterator

from pegasus.validation.adapters.base import TabularSchema
from pegasus.validation.adapters.file_columnar import FileColumnarAdapter
from pegasus.validation.file_format import normalize_file_format
from pegasus.validation.gcs_object import GcsObjectRef, gcs_blob_fingerprints
from pegasus.validation.gcs_stream import get_gcs_stream_session

# Profile/preview materialize the full object when it fits this budget.
_COLUMNAR_MATERIALIZE_MAX_BYTES = 32 * 1024 * 1024


def columnar_row_count(path: Path, file_format: str) -> int:
    """Return row count from columnar metadata (no full table scan when possible)."""
    fmt = normalize_file_format(file_format)
    if fmt in ("parquet", "pq"):
        import pyarrow.parquet as pq

        metadata = pq.ParquetFile(path).metadata
        return int(metadata.num_rows) if metadata is not None else 0
    if fmt == "orc":
        from pegasus.validation.readers.pyarrow_io import read_orc_table

        return int(read_orc_table(path).num_rows)
    if fmt == "avro":
        adapter = FileColumnarAdapter(path, file_format="avro")
        total = 0
        for batch in adapter.stream_records(10_000):
            total += len(batch)
        return total
    if fmt == "excel":
        import polars as pl

        return int(pl.read_excel(path).height)
    import pyarrow.parquet as pq

    metadata = pq.ParquetFile(path).metadata
    return int(metadata.num_rows) if metadata is not None else 0


class GcsColumnarAdapter:
    """Materializes small GCS columnar objects locally for PyArrow/Polars reads."""

    __slots__ = (
        "_ref",
        "_file_format",
        "_size_bytes",
        "_local_path",
        "_inner",
        "_network_transfer_seconds",
    )

    def __init__(
        self,
        ref: GcsObjectRef,
        *,
        file_format: str = "parquet",
        size_bytes: int | None = None,
    ) -> None:
        self._ref = ref
        self._file_format = normalize_file_format(file_format)
        self._size_bytes = size_bytes
        self._local_path: Path | None = None
        self._inner: FileColumnarAdapter | None = None
        self._network_transfer_seconds = 0.0

    @property
    def path(self) -> Path:
        return self._ref.display_path

    @property
    def gcs_uri(self) -> str:
        return self._ref.uri

    @property
    def file_format(self) -> str:
        return self._file_format

    @property
    def network_transfer_seconds(self) -> float:
        return self._network_transfer_seconds

    def get_size_bytes(self) -> int:
        if self._size_bytes is None:
            self._size_bytes = gcs_blob_fingerprints(self._ref)[0]
        return int(self._size_bytes)

    def warm_metadata(self) -> None:
        self.get_size_bytes()

    def _materialize(self) -> FileColumnarAdapter:
        if self._inner is not None:
            return self._inner

        size = self.get_size_bytes()
        if size > _COLUMNAR_MATERIALIZE_MAX_BYTES:
            raise ValueError(
                f"GCS object {self._ref.uri} is {size:,} bytes; "
                f"columnar profile/preview supports objects up to "
                f"{_COLUMNAR_MATERIALIZE_MAX_BYTES:,} bytes"
            )

        session = get_gcs_stream_session(self._ref)
        cached = session.cached_object_body()
        if cached is None:
            import time

            t0 = time.perf_counter()
            with session.open_binary(read_ahead=False) as handle:
                data = handle.read()
            self._network_transfer_seconds += time.perf_counter() - t0
            session.store_cached_object_body(data)
            cached = data
        else:
            self._network_transfer_seconds = max(
                self._network_transfer_seconds,
                session.network_transfer_seconds,
            )

        suffix = Path(self._ref.object_name).suffix or f".{self._file_format}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(cached)
            local_path = Path(tmp.name)
        self._local_path = local_path
        self._inner = FileColumnarAdapter(local_path, file_format=self._file_format)
        return self._inner

    def get_schema(self) -> TabularSchema:
        return self._materialize().get_schema()

    def get_row_count(self) -> int:
        self._materialize()
        assert self._local_path is not None
        return columnar_row_count(self._local_path, self._file_format)

    def stream_records(self, chunk_rows: int) -> Iterator[list[dict[str, Any]]]:
        yield from self._materialize().stream_records(chunk_rows)

    def cleanup(self) -> None:
        if self._local_path is not None:
            self._local_path.unlink(missing_ok=True)
            self._local_path = None
        self._inner = None


def create_columnar_adapter(
    *,
    path: Path | None,
    ref: GcsObjectRef | None,
    file_format: str,
) -> FileColumnarAdapter | GcsColumnarAdapter:
    if ref is not None:
        return GcsColumnarAdapter(ref, file_format=file_format)
    if path is None:
        raise ValueError("path or GCS reference is required")
    return FileColumnarAdapter(path, file_format=file_format)

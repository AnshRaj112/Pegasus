# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:32:01Z
# --- END GENERATED FILE METADATA ---

"""GCS streaming I/O — connection reuse, chunked reads, no full-object materialization."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from io import BytesIO
from typing import IO, Any, Iterator

from pegasus.validation.gcs_object import GcsObjectRef

_DEFAULT_CHUNK_BYTES = 4 * 1024 * 1024
_DEFAULT_READAHEAD_CHUNKS = 2

_CLIENT_LOCK = threading.Lock()
_CLIENTS: dict[str, Any] = {}


def _credentials_cache_key(ref: GcsObjectRef) -> str:
    payload = json.dumps(ref.credentials_info, sort_keys=True, default=str)
    project = ref.project_id or ""
    return hashlib.sha256(f"{project}:{payload}".encode()).hexdigest()


def get_storage_client(ref: GcsObjectRef):
    """Return a cached ``google.cloud.storage.Client`` (one per credential set)."""
    key = _credentials_cache_key(ref)
    with _CLIENT_LOCK:
        client = _CLIENTS.get(key)
        if client is not None:
            return client
    from google.cloud import storage as gcs_storage
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(ref.credentials_info)
    client = gcs_storage.Client(credentials=credentials, project=ref.project_id)
    with _CLIENT_LOCK:
        _CLIENTS[key] = client
    return client


def get_blob(ref: GcsObjectRef):
    """Return a cached blob handle (reuses the storage client)."""
    client = get_storage_client(ref)
    return client.bucket(ref.bucket.strip()).blob(ref.object_name.strip().lstrip("/"))


class _ReadAheadBinaryIO:
    """Buffered reader over a GCS binary handle with chunked read-ahead."""

    __slots__ = ("_raw", "_chunk_size", "_buffer", "_eof", "_bytes_read")

    def __init__(self, raw: IO[bytes], *, chunk_size: int = _DEFAULT_CHUNK_BYTES) -> None:
        self._raw = raw
        self._chunk_size = max(4096, chunk_size)
        self._buffer = bytearray()
        self._eof = False
        self._bytes_read = 0

    @property
    def bytes_read(self) -> int:
        return self._bytes_read

    def _fill(self) -> bool:
        if self._eof:
            return False
        chunk = self._raw.read(self._chunk_size)
        if not chunk:
            self._eof = True
            return False
        self._bytes_read += len(chunk)
        self._buffer.extend(chunk)
        return True

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            while self._fill():
                pass
            out = bytes(self._buffer)
            self._buffer.clear()
            return out
        while len(self._buffer) < size and self._fill():
            pass
        n = min(size, len(self._buffer))
        out = bytes(self._buffer[:n])
        del self._buffer[:n]
        return out

    def readline(self, size: int = -1) -> bytes:
        while True:
            nl = self._buffer.find(b"\n")
            if nl >= 0:
                line_end = nl + 1
                if size >= 0:
                    line_end = min(line_end, size)
                out = bytes(self._buffer[:line_end])
                del self._buffer[:line_end]
                return out
            if not self._fill():
                if self._buffer:
                    out = bytes(self._buffer)
                    self._buffer.clear()
                    return out
                return b""
            if size >= 0 and len(self._buffer) >= size:
                out = bytes(self._buffer[:size])
                del self._buffer[:size]
                return out

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return bool(getattr(self._raw, "seekable", lambda: False)())

    @property
    def closed(self) -> bool:
        return bool(getattr(self._raw, "closed", False))

    def close(self) -> None:
        closer = getattr(self._raw, "close", None)
        if callable(closer):
            closer()

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        if hasattr(self._raw, "fileno"):
            return int(self._raw.fileno())
        raise OSError("fileno not available on GCS stream")


class GcsStreamSession:
    """Per-object streaming session — reuses client/blob; tracks network time and bytes."""

    __slots__ = (
        "_ref",
        "_blob",
        "network_transfer_seconds",
        "bytes_read",
        "_open_count",
        "_cached_object_body",
    )

    def __init__(self, ref: GcsObjectRef) -> None:
        self._ref = ref
        self._blob: Any = None
        self.network_transfer_seconds = 0.0
        self.bytes_read = 0
        self._open_count = 0
        self._cached_object_body: bytes | None = None

    @property
    def ref(self) -> GcsObjectRef:
        return self._ref

    def _ensure_blob(self):
        if self._blob is None:
            self._blob = get_blob(self._ref)
        return self._blob

    def cached_object_body(self) -> bytes | None:
        """Full object bytes from a prior in-memory load (avoids re-download on spill)."""
        return self._cached_object_body

    def store_cached_object_body(self, data: bytes) -> None:
        """Retain object bytes for reuse within this validation job."""
        if data:
            self._cached_object_body = data

    @contextmanager
    def open_binary(
        self,
        *,
        chunk_size: int = _DEFAULT_CHUNK_BYTES,
        read_ahead: bool = True,
    ) -> Iterator[IO[bytes]]:
        """Open one sequential read on the object (connection reused via cached client)."""
        if self._cached_object_body is not None:
            yield BytesIO(self._cached_object_body)
            return

        t0 = time.perf_counter()
        self._open_count += 1
        with self._ensure_blob().open("rb") as raw:
            self.network_transfer_seconds += time.perf_counter() - t0
            if read_ahead:
                wrapper: IO[bytes] = _ReadAheadBinaryIO(raw, chunk_size=chunk_size)
            else:
                wrapper = raw
            try:
                yield wrapper
            finally:
                if read_ahead and isinstance(wrapper, _ReadAheadBinaryIO):
                    self.bytes_read += wrapper.bytes_read

    def read_prefix(self, *, max_bytes: int) -> bytes:
        """Bounded prefix read for header / delimiter detection only."""
        limit = max(0, max_bytes)
        if limit == 0:
            return b""
        with self.open_binary(read_ahead=False) as handle:
            return handle.read(limit)

    def iter_chunks(self, *, chunk_size: int = _DEFAULT_CHUNK_BYTES) -> Iterator[bytes]:
        """Block iterator over the object without loading it entirely."""
        with self.open_binary(chunk_size=chunk_size, read_ahead=True) as handle:
            while True:
                block = handle.read(chunk_size)
                if not block:
                    break
                yield block

    def metadata_fingerprint(self) -> str | None:
        """Stable digest from GCS metadata (no full-object read)."""
        blob = self._ensure_blob()
        if blob.md5_hash:
            return f"md5:{blob.md5_hash}"
        crc = getattr(blob, "crc32c", None)
        if crc:
            return f"crc32c:{crc}"
        return None


_SESSION_LOCK = threading.Lock()
_SESSIONS: dict[tuple[str, str, str], GcsStreamSession] = {}


def get_gcs_stream_session(ref: GcsObjectRef) -> GcsStreamSession:
    """Return a process-wide session per ``gs://bucket/object`` (connection reuse)."""
    key = (ref.bucket.strip(), ref.object_name.strip().lstrip("/"), _credentials_cache_key(ref))
    with _SESSION_LOCK:
        session = _SESSIONS.get(key)
        if session is None:
            session = GcsStreamSession(ref)
            _SESSIONS[key] = session
        return session


def clear_gcs_stream_sessions() -> None:
    """Test helper — drop cached sessions."""
    with _SESSION_LOCK:
        _SESSIONS.clear()

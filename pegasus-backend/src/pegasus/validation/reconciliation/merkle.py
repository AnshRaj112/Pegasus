"""Streaming Merkle utilities for deterministic CSV equality prechecks."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import polars as pl

from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader


def _h(data: bytes) -> bytes:
    return sha256(data).digest()


def _row_hash(values: tuple[object, ...]) -> bytes:
    parts = []
    for v in values:
        text = "" if v is None else str(v)
        encoded = text.encode("utf-8", errors="replace")
        parts.append(len(encoded).to_bytes(4, "big"))
        parts.append(encoded)
    return _h(b"row" + b"".join(parts))


def _node_hash(left: bytes, right: bytes) -> bytes:
    return _h(b"node" + left + right)


def _reduce_level(nodes: list[bytes]) -> list[bytes]:
    if len(nodes) <= 1:
        return nodes
    out: list[bytes] = []
    i = 0
    while i < len(nodes):
        left = nodes[i]
        right = nodes[i + 1] if i + 1 < len(nodes) else left
        out.append(_node_hash(left, right))
        i += 2
    return out


def compute_csv_merkle_root(
    *,
    path: Path,
    reader: PolarsCSVReader,
    delimiter: str,
    has_header: bool,
    batch_rows: int,
    columns: list[str],
) -> tuple[str, int]:
    """Compute deterministic Merkle root and row count using streaming batches."""
    if not columns:
        columns = ["__empty__"]
    read_opts: dict[str, object] = {
        "separator": delimiter,
        "has_header": has_header,
        "encoding": "utf-8",
    }
    leaves: list[bytes] = []
    row_count = 0
    for batch in reader.iter_batches(path, batch_size=batch_rows, read_options=read_opts):
        if "__empty__" in columns:
            rows = [tuple() for _ in range(batch.height)]
        else:
            missing = [c for c in columns if c not in batch.columns]
            if missing:
                raise ValueError(f"columns missing in batch: {missing}")
            rows = batch.select([pl.col(c) for c in columns]).iter_rows()
        for row in rows:
            leaves.append(_row_hash(tuple(row)))
            row_count += 1
    if not leaves:
        return sha256(b"empty").hexdigest(), 0
    level = leaves
    while len(level) > 1:
        level = _reduce_level(level)
    return level[0].hex(), row_count

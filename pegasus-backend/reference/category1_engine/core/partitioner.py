# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:57:27Z
# --- END GENERATED FILE METADATA ---

"""Deterministic partitioning with platform-side hashing."""

import json
import struct
from pathlib import Path
from typing import Any, Iterator, Optional

from category1.core.fingerprint import FingerprintEngine
from category1.models.schemas import KeyStrategy


class PartitionRecord:
    """A single record stored in a partition file."""

    __slots__ = ("identity_key", "fingerprint", "partition_id", "raw_data")

    def __init__(
        self,
        identity_key: str,
        fingerprint: str,
        partition_id: int,
        raw_data: dict[str, Any],
    ):
        self.identity_key = identity_key
        self.fingerprint = fingerprint
        self.partition_id = partition_id
        self.raw_data = raw_data

    def serialize(self) -> bytes:
        payload = json.dumps(
            {
                "k": self.identity_key,
                "f": self.fingerprint,
                "d": self.raw_data,
            },
            separators=(",", ":"),
            default=str,
        )
        header = struct.pack(">I", len(payload))
        return header + payload.encode("utf-8")

    @classmethod
    def deserialize(cls, data: bytes) -> "PartitionRecord":
        length = struct.unpack(">I", data[:4])[0]
        return cls.deserialize_payload(data[4 : 4 + length])

    @classmethod
    def deserialize_payload(cls, payload: bytes) -> "PartitionRecord":
        obj = json.loads(payload)
        return cls(
            identity_key=obj["k"],
            fingerprint=obj["f"],
            partition_id=-1,
            raw_data=obj["d"],
        )


class PartitionWriter:
    """Writes records to partition-specific files on disk."""

    def __init__(self, base_dir: Path, side: str, num_partitions: int):
        self.base_dir = base_dir / side / "partitions"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.num_partitions = num_partitions
        self._handles: dict[int, Any] = {}
        self._counts: dict[int, int] = {i: 0 for i in range(num_partitions)}

    def write_record(self, record: PartitionRecord) -> None:
        pid = record.partition_id
        path = self.base_dir / f"part_{pid:05d}.bin"
        if pid not in self._handles:
            self._handles[pid] = open(path, "ab")  # noqa: SIM115
        self._handles[pid].write(record.serialize())
        self._counts[pid] += 1

    def close(self) -> dict[int, int]:
        for h in self._handles.values():
            h.close()
        self._handles.clear()
        return dict(self._counts)

    def get_partition_path(self, partition_id: int) -> Path:
        return self.base_dir / f"part_{partition_id:05d}.bin"


class PartitionReader:
    """Streams records from a partition file."""

    def __init__(self, path: Path):
        self.path = path

    def __iter__(self) -> Iterator[PartitionRecord]:
        if not self.path.exists():
            return
        with open(self.path, "rb") as f:
            while True:
                header = f.read(4)
                if len(header) < 4:
                    break
                length = struct.unpack(">I", header)[0]
                data = f.read(length)
                if len(data) < length:
                    break
                yield PartitionRecord.deserialize_payload(data)


class StreamingPartitioner:
    """Assigns records to deterministic partitions during streaming ingestion."""

    def __init__(
        self,
        fingerprint_engine: FingerprintEngine,
        key_columns: list[str],
        compare_columns: list[str],
        num_partitions: int,
        key_strategy: KeyStrategy = KeyStrategy.PRIMARY,
        column_mapping: Optional[dict[str, str]] = None,
        column_types: Optional[dict[str, str]] = None,
    ):
        self.fp = fingerprint_engine
        self.key_columns = key_columns
        self.compare_columns = compare_columns
        self.num_partitions = num_partitions
        self.key_strategy = key_strategy
        self.column_mapping = column_mapping or {}
        self.column_types = column_types or {}

    def partition_record(self, record: dict[str, Any]) -> PartitionRecord:
        identity = self.fp.compute_identity_key(
            record, self.key_columns, self.column_mapping, self.key_strategy.value
        )
        fingerprint = self.fp.compute_fingerprint(
            record, self.compare_columns, self.column_types, self.column_mapping
        )
        pid = self.fp.compute_partition_id(identity, self.num_partitions)
        return PartitionRecord(identity, fingerprint, pid, record)

    def process_chunk(
        self,
        records: list[dict[str, Any]],
        writer: PartitionWriter,
    ) -> int:
        count = 0
        for record in records:
            pr = self.partition_record(record)
            writer.write_record(pr)
            count += 1
        return count

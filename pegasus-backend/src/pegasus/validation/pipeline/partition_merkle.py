# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:27:19Z
# --- END GENERATED FILE METADATA ---

"""Order-independent per-partition digests computed during spill (no re-read)."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

import polars as pl

_CBL2_MAGIC = b"CBL2"
_KEY_LEN = struct.Struct(">H")


def _row_xor_digest(identity: str, fp_hash: int) -> int:
    try:
        import xxhash
    except ImportError:
        return hash((identity, int(fp_hash))) & ((1 << 64) - 1)
    payload = f"{identity}\x1f{int(fp_hash)}".encode("utf-8", errors="replace")
    return int(xxhash.xxh64(payload).intdigest())


@dataclass
class PartitionMerkleAccumulator:
    """Commutative XOR digest per hash partition — identical row multisets match."""

    _partition_xor: dict[int, int] = field(default_factory=dict)
    row_count: int = 0

    def add_group(self, pid: int, identities: pl.Series, fp_hashes: pl.Series) -> None:
        acc = self._partition_xor.get(pid, 0)
        for identity, fp_hash in zip(identities.to_list(), fp_hashes.to_list(), strict=False):
            acc ^= _row_xor_digest(str(identity), int(fp_hash))
            self.row_count += 1
        self._partition_xor[pid] = acc

    def absorb_native_spill(self, digest_map: dict[int, int], rows: int) -> None:
        """Merge per-partition XOR digests produced by pegasus_native direct spill."""
        for pid, xor in digest_map.items():
            self._partition_xor[int(pid)] = int(xor)
        self.row_count += rows

    def add_cbl2_group(self, pid: int, data: bytes) -> None:
        """Accumulate XOR digest from a native CBL2 partition block."""
        if not data.startswith(_CBL2_MAGIC) or len(data) < 8:
            return
        row_count = struct.unpack_from(">I", data, 4)[0]
        offset = 8
        keys: list[str] = []
        for _ in range(row_count):
            key_len = _KEY_LEN.unpack_from(data, offset)[0]
            offset += _KEY_LEN.size
            keys.append(data[offset : offset + key_len].decode("utf-8"))
            offset += key_len
        acc = self._partition_xor.get(pid, 0)
        for identity in keys:
            fp_hash = int.from_bytes(data[offset : offset + 8], "big")
            offset += 8
            acc ^= _row_xor_digest(identity, fp_hash)
            self.row_count += 1
        self._partition_xor[pid] = acc

    def digest_map(self) -> dict[int, int]:
        return dict(self._partition_xor)

    def global_digest(self, active_pids: set[int]) -> int:
        """Root digest over active partitions (order-independent)."""
        root = 0
        for pid in sorted(active_pids):
            root ^= self._partition_xor.get(pid, 0) ^ ((pid & ((1 << 64) - 1)) << 1)
        return root

    def identical_to(
        self,
        other: PartitionMerkleAccumulator,
        active_pids: set[int],
    ) -> bool:
        if self.row_count != other.row_count:
            return False
        for pid in active_pids:
            if self._partition_xor.get(pid, 0) != other._partition_xor.get(pid, 0):
                return False
        return True

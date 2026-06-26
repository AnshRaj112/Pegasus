# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T07:48:09Z
# --- END GENERATED FILE METADATA ---

"""Fast row fingerprinting for reconciliation."""

from __future__ import annotations

import hashlib
from typing import Any, Callable

try:
    import xxhash as _xxhash  # type: ignore[import-not-found]

    _HAS_XXHASH = True
except ImportError:
    _HAS_XXHASH = False
    _xxhash = None  # type: ignore[assignment]

from pegasus.validation.comparators.policy import ComparePolicy, active_compare_policy

# Separator between canonicalized column values (matches in-memory Polars path).
_FIELD_SEP = "\x1f"

# xxHash64 provides ~16x throughput vs SHA256 with negligible collision risk for
# reconciliation (birthday bound ~2^32 records before ~50% collision).
DEFAULT_ALGORITHM = "xxhash64"


def canonical(
    value: Any,
    *,
    column: str | None = None,
    policy: ComparePolicy | None = None,
) -> str:
    """Normalize a cell value for deterministic comparison."""
    pol = policy if policy is not None else active_compare_policy()
    if pol is not None and column is not None:
        return pol.canonical(column, value)
    if value is None:
        return "__NULL__"
    text = str(value).strip()
    if text.lower() in ("", "null", "none", "na", "n/a"):
        return "__NULL__"
    return text


def _identity_parts(record: dict[str, Any], columns: list[str]) -> list[str]:
    """Plain text identity parts — never apply compare-policy canonicalization."""
    return [canonical(record.get(c)) for c in columns]


def parse_identity_columns(uid_column: str) -> list[str]:
    """Split comma-separated UID column names (e.g. ``region,id``)."""
    return [c.strip() for c in uid_column.split(",") if c.strip()]


def identity_key(record: dict[str, Any], columns: list[str]) -> str:
    return identity_key_from_parts(_identity_parts(record, columns))


def identity_key_from_parts(parts: list[str]) -> str:
    return "|".join(parts)


def _canonical_parts(
    record: dict[str, Any],
    columns: list[str],
    *,
    policy: ComparePolicy | None = None,
    side: str = "source",
) -> list[str]:
    pol = policy if policy is not None else active_compare_policy()
    if pol is not None and pol.fields:
        return pol.canonical_parts_for_record(record, side=side)  # type: ignore[arg-type]
    return [canonical(record.get(c), column=c, policy=pol) for c in columns]


def filter_compare_columns(compare_columns: list[str], available: list[str]) -> list[str]:
    """Keep only compare columns present in the loaded frame/schema."""
    available_set = set(available)
    return [col for col in compare_columns if col in available_set]


def _fingerprint_sha256(parts: list[str]) -> bytes:
    return hashlib.sha256(_FIELD_SEP.join(parts).encode()).digest()


def _fingerprint_xxhash64(parts: list[str]) -> bytes:
    h = _xxhash.xxh64(_FIELD_SEP.join(parts).encode())
    return h.digest()


def _fingerprint_xxhash128(parts: list[str]) -> bytes:
    h = _xxhash.xxh128(_FIELD_SEP.join(parts).encode())
    return h.digest()[:8]


def _fingerprint_crc64(parts: list[str]) -> bytes:
    # zlib.crc32 is 32-bit; use first 8 bytes of sha256 truncated as fallback
    # when xxhash unavailable — callers should prefer xxhash64.
    return hashlib.sha256(_FIELD_SEP.join(parts).encode()).digest()[:8]


def _select_hasher(algorithm: str) -> Callable[[list[str]], bytes]:
    algo = algorithm.lower()
    if algo == "sha256":
        return _fingerprint_sha256
    if algo in ("xxhash64", "xxhash"):
        if not _HAS_XXHASH:
            return _fingerprint_sha256
        return _fingerprint_xxhash64
    if algo == "xxhash128":
        if not _HAS_XXHASH:
            return _fingerprint_sha256
        return _fingerprint_xxhash128
    if algo == "crc64":
        return _fingerprint_crc64
    if not _HAS_XXHASH:
        return _fingerprint_sha256
    return _fingerprint_xxhash64


def row_fingerprint_bytes(
    record: dict[str, Any],
    columns: list[str],
    *,
    algorithm: str = DEFAULT_ALGORITHM,
    policy: ComparePolicy | None = None,
    side: str = "source",
) -> bytes:
    """Return an 8-byte (or 32-byte for sha256) fingerprint digest."""
    if not columns:
        return b""
    return row_fingerprint_from_parts(
        _canonical_parts(record, columns, policy=policy, side=side),
        algorithm=algorithm,
    )


def row_fingerprint_from_parts(
    parts: list[str],
    *,
    algorithm: str = DEFAULT_ALGORITHM,
) -> bytes:
    if not parts:
        return b""
    return _select_hasher(algorithm)(parts)


def row_fingerprint_hex(
    record: dict[str, Any],
    columns: list[str],
    *,
    algorithm: str = DEFAULT_ALGORITHM,
    policy: ComparePolicy | None = None,
) -> str:
    return row_fingerprint_bytes(record, columns, algorithm=algorithm, policy=policy).hex()


def partition_id(key: str, num_partitions: int) -> int:
    if _HAS_XXHASH:
        return _xxhash.xxh64(key.encode()).intdigest() % num_partitions
    h = hashlib.md5(key.encode()).digest()
    return int.from_bytes(h[:4], "big") % num_partitions


def compare_columns_payload(
    record: dict[str, Any],
    columns: list[str],
    *,
    policy: ComparePolicy | None = None,
    side: str = "source",
) -> dict[str, str]:
    """Extract logical compare columns (canonicalized) for drilldown storage."""
    pol = policy if policy is not None else active_compare_policy()
    if pol is not None and pol.fields:
        return {
            key: pol.canonical_side_part(record, key, side=side)  # type: ignore[arg-type]
            for key in columns
        }
    return {col: canonical(record.get(col), column=col, policy=pol) for col in columns}

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:32:01Z
# --- END GENERATED FILE METADATA ---

"""Record fingerprinting using canonicalized values."""

import hashlib
import json
from typing import Any, Optional

from category1.core.canonicalization import CanonicalizationEngine


class FingerprintEngine:
    """Generates deterministic fingerprints for records."""

    def __init__(self, canonicalizer: Optional[CanonicalizationEngine] = None):
        self.canonicalizer = canonicalizer or CanonicalizationEngine()

    def compute_identity_key(
        self,
        record: dict[str, Any],
        key_columns: list[str],
        column_mapping: Optional[dict[str, str]] = None,
        strategy: str = "primary",
    ) -> str:
        mapping = column_mapping or {}
        if not key_columns:
            return self._hash_all_columns(record)

        parts: list[str] = []
        for col in key_columns:
            mapped = mapping.get(col, col)
            val = record.get(mapped)
            canon = self.canonicalizer.canonicalize_value(val)
            parts.append(canon)
        return "|".join(parts)

    def compute_fingerprint(
        self,
        record: dict[str, Any],
        compare_columns: list[str],
        column_types: Optional[dict[str, str]] = None,
        column_mapping: Optional[dict[str, str]] = None,
    ) -> str:
        canonical = self.canonicalizer.canonicalize_record(
            record, compare_columns, column_types, column_mapping
        )
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def compute_partition_id(self, identity_key: str, num_partitions: int) -> int:
        h = hashlib.md5(identity_key.encode("utf-8")).digest()
        return int.from_bytes(h[:4], "big") % num_partitions

    def _hash_all_columns(self, record: dict[str, Any]) -> str:
        sorted_items = sorted(
            (k, self.canonicalizer.canonicalize_value(v)) for k, v in record.items()
        )
        payload = json.dumps(sorted_items, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

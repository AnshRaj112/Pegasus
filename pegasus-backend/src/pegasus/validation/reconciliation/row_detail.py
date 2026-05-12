"""JSON encoding for mismatch row snapshots (keeps comparators import-light)."""

from __future__ import annotations

import json
from typing import Any


def encode_row_detail(
    source_record: dict[str, Any] | None,
    target_record: dict[str, Any] | None,
) -> str:
    """JSON payload for UIs: full source/target rows when available."""
    return json.dumps(
        {"source_record": source_record, "target_record": target_record},
        default=str,
        ensure_ascii=False,
    )

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Hard byte limits for streaming readers (chunk / line bombs)."""

from __future__ import annotations

# Default 50 MiB — max bytes per read chunk or single logical line.
DEFAULT_MAX_READ_CHUNK_BYTES: int = 50 * 1024 * 1024


def clamp_read_chunk_bytes(
    requested: int,
    *,
    max_bytes: int = DEFAULT_MAX_READ_CHUNK_BYTES,
) -> int:
    """Clamp a requested read size to a safe upper bound."""
    cap = max(4096, int(max_bytes))
    return max(4096, min(int(requested), cap))


class StreamLimitExceededError(ValueError):
    """Raised when a stream would exceed configured memory bounds."""

# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Runtime admission checks for standalone validation-worker processes."""

from __future__ import annotations

from pathlib import Path

from pegasus.core.config import Settings
from pegasus.services.host_memory import admission_available_ram_bytes
from pegasus.services.job_resource_meta import estimate_job_csv_bytes, job_column_count, read_job_meta
from pegasus.services.resource_governor import format_mib
from pegasus.services.resource_models import estimate_job_ram_bytes


def should_defer_job(job_dir: Path, settings: Settings) -> tuple[bool, str]:
    """Return (True, reason) when the worker should requeue and wait for RAM."""
    meta = read_job_meta(job_dir)
    combined = int(meta.get("combined_bytes") or 0) or estimate_job_csv_bytes(job_dir)
    cols = job_column_count(meta)
    need = estimate_job_ram_bytes(
        combined,
        ram_multiplier=settings.validation_queue_ram_multiplier,
        min_ram_per_job_bytes=settings.validation_queue_min_ram_per_job_bytes,
        streaming=settings.validation_gcs_streaming_only,
        chunk_rows=settings.validation_reconciliation_chunk_rows,
        compare_column_count=cols,
    )
    reserve = int(settings.validation_queue_ram_reserve_bytes)
    avail = max(0, admission_available_ram_bytes(settings) - reserve)
    if need > avail:
        return True, (
            f"Worker waiting for RAM (needs ~{format_mib(need)}, "
            f"{format_mib(avail)} available after reserve)"
        )
    return False, ""

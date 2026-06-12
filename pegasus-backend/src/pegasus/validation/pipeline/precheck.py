# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-11T12:51:39+05:30
# --- END GENERATED FILE METADATA ---

"""Fast prechecks before full reconciliation (metadata, content digest, partition hashes)."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.adapters.base import TabularSourceAdapter
from pegasus.validation.pipeline.result import PipelineResult


def _adapter_size_bytes(adapter: object) -> int | None:
    getter = getattr(adapter, "get_size_bytes", None)
    if not callable(getter):
        return None
    try:
        return int(getter())
    except (OSError, ValueError):
        return None


def _stored_digest(adapter: object) -> str | None:
    getter = getattr(adapter, "content_digest_hex", None)
    if callable(getter):
        return getter()
    return None


def _stored_cloud_hashes(adapter: object) -> tuple[str | None, str | None]:
    return (
        getattr(adapter, "_crc32c", None),
        getattr(adapter, "_md5_hex", None),
    )


def _metadata_identical(source: TabularSourceAdapter, target: TabularSourceAdapter) -> bool:
    """True when size and cloud CRC32C or MD5 match (no extra API calls)."""
    src_size = _adapter_size_bytes(source)
    tgt_size = _adapter_size_bytes(target)
    if src_size is None or tgt_size is None or src_size != tgt_size or src_size <= 0:
        return False
    src_crc, src_md5 = _stored_cloud_hashes(source)
    tgt_crc, tgt_md5 = _stored_cloud_hashes(target)
    if src_crc and tgt_crc and src_crc == tgt_crc:
        return True
    if src_md5 and tgt_md5 and src_md5 == tgt_md5:
        return True
    return False


def _precomputed_digest_identical(source: TabularSourceAdapter, target: TabularSourceAdapter) -> bool:
    """Compare digests computed once during GCS prefetch (never re-hash here)."""
    src_digest = _stored_digest(source)
    tgt_digest = _stored_digest(target)
    if not src_digest or not tgt_digest:
        return False
    return src_digest == tgt_digest


def _identical_pipeline_result(
    source: TabularSourceAdapter,
    target: TabularSourceAdapter,
    *,
    compare_columns: list[str],
    method: str,
) -> PipelineResult:
    src_rows = _estimate_row_count(source)
    tgt_rows = _estimate_row_count(target)
    count = src_rows if src_rows == tgt_rows else max(src_rows, tgt_rows)
    return PipelineResult(
        schema_valid=True,
        source_row_count=src_rows,
        target_row_count=tgt_rows,
        row_count_match=src_rows == tgt_rows,
        missing_count=0,
        extra_count=0,
        changed_count=0,
        matching_count=count,
        partitions_processed=0,
        mismatched_partitions=0,
        compared_columns=list(compare_columns),
        execution_seconds=0.0,
        extra_stats={"path": "precheck_identical", "precheck_method": method},
    )


def _estimate_row_count(adapter: TabularSourceAdapter) -> int:
    getter = getattr(adapter, "get_row_count", None)
    if callable(getter):
        count = getter()
        if isinstance(count, int) and count > 0:
            return count
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
    from pegasus.validation.row_count import count_delimited_data_rows

    if isinstance(adapter, (FileDelimitedAdapter, GcsDelimitedAdapter)):
        return count_delimited_data_rows(adapter)
    size = _adapter_size_bytes(adapter)
    if size is None or size <= 0:
        return 0
    try:
        column_count = len(adapter.get_schema().column_names)
    except Exception:
        column_count = 8
    from pegasus.validation.pipeline.pipeline import _estimate_row_count_from_bytes

    return _estimate_row_count_from_bytes(size, column_count=column_count)


def try_identical_precheck(
    source: TabularSourceAdapter,
    target: TabularSourceAdapter,
    *,
    compare_columns: list[str],
    enable_metadata: bool = True,
    enable_content_digest: bool = True,
) -> PipelineResult | None:
    """Skip full reconcile when blobs are byte-identical.

    Never hashes full file contents here — only compares sizes and GCS metadata digests.
    """
    src_size = _adapter_size_bytes(source)
    tgt_size = _adapter_size_bytes(target)
    if src_size is None or tgt_size is None:
        return None
    if src_size != tgt_size:
        return None

    if enable_content_digest and _precomputed_digest_identical(source, target):
        return _identical_pipeline_result(
            source, target, compare_columns=compare_columns, method="content_digest"
        )
    if enable_metadata and _metadata_identical(source, target):
        return _identical_pipeline_result(
            source, target, compare_columns=compare_columns, method="metadata"
        )
    return None


def spill_partitions_identical(
    work: Path,
    active_pids: set[int],
    *,
    max_bytes_to_hash: int = 32 * 1024 * 1024,
) -> bool:
    """Compare spill partitions by digest when total spill size is small."""
    try:
        import xxhash
    except ImportError:
        return False

    total = 0
    for pid in active_pids:
        src_path = work / "source" / f"part_{pid:05d}.bin"
        tgt_path = work / "target" / f"part_{pid:05d}.bin"
        if not src_path.is_file() or not tgt_path.is_file():
            return False
        src_sz = src_path.stat().st_size
        tgt_sz = tgt_path.stat().st_size
        if src_sz != tgt_sz:
            return False
        total += src_sz + tgt_sz
        if total > max_bytes_to_hash:
            return False

    if total == 0:
        return False

    for pid in active_pids:
        src_path = work / "source" / f"part_{pid:05d}.bin"
        tgt_path = work / "target" / f"part_{pid:05d}.bin"
        if xxhash.xxh64(src_path.read_bytes()).hexdigest() != xxhash.xxh64(tgt_path.read_bytes()).hexdigest():
            return False
    return True

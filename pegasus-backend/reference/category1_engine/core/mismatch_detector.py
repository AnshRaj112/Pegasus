# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:05:47Z
# --- END GENERATED FILE METADATA ---

"""Partition-level mismatch detection with column drilldown."""

from pathlib import Path
from typing import Iterator, Optional

from category1.core.canonicalization import CanonicalizationEngine
from category1.core.external_memory import ExternalHashTable, MemoryMonitor
from category1.core.partitioner import PartitionReader, PartitionRecord
from category1.models.schemas import ColumnDifference, MismatchRecord, PartitionStats


class MismatchDetector:
    """Detects missing, extra, and changed records within a partition."""

    def __init__(
        self,
        compare_columns: list[str],
        column_mapping: Optional[dict[str, str]] = None,
        column_types: Optional[dict[str, str]] = None,
        enable_drilldown: bool = True,
        sample_limit: int = 1000,
    ):
        self.compare_columns = compare_columns
        self.column_mapping = column_mapping or {}
        self.column_types = column_types or {}
        self.enable_drilldown = enable_drilldown
        self.sample_limit = sample_limit
        self.canonicalizer = CanonicalizationEngine()

    def reconcile_partition(
        self,
        source_path: Path,
        target_path: Path,
        partition_id: int,
        spill_dir: Path,
        memory_monitor: MemoryMonitor,
    ) -> tuple[PartitionStats, list[MismatchRecord]]:
        import time

        start = time.perf_counter()
        stats = PartitionStats(partition_id=partition_id)
        mismatches: list[MismatchRecord] = []

        source_table = ExternalHashTable(spill_dir / "source", memory_monitor)
        for record in PartitionReader(source_path):
            source_table.insert(record.identity_key, record.fingerprint, record.raw_data)
            stats.source_records += 1
        source_table.flush_all()

        target_keys_seen: set[str] = set()
        for record in PartitionReader(target_path):
            stats.target_records += 1
            target_keys_seen.add(record.identity_key)
            source_entry = source_table.lookup(record.identity_key)

            if source_entry is None:
                stats.extra += 1
                if len(mismatches) < self.sample_limit:
                    mismatches.append(MismatchRecord(
                        record_key=record.identity_key,
                        partition_id=partition_id,
                        mismatch_type="extra",
                        target_fingerprint=record.fingerprint,
                    ))
            else:
                src_fp, src_data = source_entry
                if src_fp != record.fingerprint:
                    stats.mismatched += 1
                    col_diffs = []
                    if self.enable_drilldown:
                        col_diffs = self._column_drilldown(src_data, record.raw_data)
                    if len(mismatches) < self.sample_limit:
                        mismatches.append(MismatchRecord(
                            record_key=record.identity_key,
                            partition_id=partition_id,
                            mismatch_type="changed",
                            source_fingerprint=src_fp,
                            target_fingerprint=record.fingerprint,
                            column_differences=col_diffs,
                        ))

        for key in source_table.iter_all_keys():
            if key not in target_keys_seen:
                stats.missing += 1
                if len(mismatches) < self.sample_limit:
                    entry = source_table.lookup(key)
                    mismatches.append(MismatchRecord(
                        record_key=key,
                        partition_id=partition_id,
                        mismatch_type="missing",
                        source_fingerprint=entry[0] if entry else None,
                    ))

        stats.processing_time_ms = (time.perf_counter() - start) * 1000
        return stats, mismatches

    def _column_drilldown(
        self,
        source_data: dict,
        target_data: dict,
    ) -> list[ColumnDifference]:
        diffs: list[ColumnDifference] = []
        for col in self.compare_columns:
            mapped = self.column_mapping.get(col, col)
            src_val = source_data.get(mapped)
            tgt_val = target_data.get(col)
            dtype = self.column_types.get(col, "string")
            src_canon = self.canonicalizer.canonicalize_value(src_val, dtype)
            tgt_canon = self.canonicalizer.canonicalize_value(tgt_val, dtype)
            if src_canon != tgt_canon:
                diffs.append(ColumnDifference(
                    column=col,
                    source_value=str(src_val) if src_val is not None else None,
                    target_value=str(tgt_val) if tgt_val is not None else None,
                ))
        return diffs

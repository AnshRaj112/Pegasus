"""Ordered UID stream merge comparison (Polars spill path).

This module name mirrors the high-level architecture; the implementation lives in
:class:`~pegasus.validation.reconciliation.partition_comparator.PartitionComparator`.
"""

from __future__ import annotations

from pegasus.validation.reconciliation.partition_comparator import PartitionComparator as MergeStreamComparator

__all__ = ["MergeStreamComparator"]

"""External-memory CSV reconciliation (Polars streaming, spill, partition, external sort)."""

from pegasus.validation.reconciliation.checkpoint import ReconciliationCheckpoint
from pegasus.validation.reconciliation.checkpoint import ReconciliationCheckpoint
from pegasus.validation.reconciliation.config import (
    ReconciliationBackend,
    ReconciliationRuntimeConfig,
    ReconciliationStrategy,
)
from pegasus.validation.reconciliation.coordinator import (
    ReconciliationCoordinator,
    auto_external_enabled,
)
from pegasus.validation.reconciliation.exceptions import ReconciliationError, ReconciliationStrategyError
from pegasus.validation.reconciliation.metrics import NoOpReconciliationMetrics, ReconciliationMetrics
from pegasus.validation.reconciliation.mismatch_writer import MismatchWriter
from pegasus.validation.reconciliation.partition_comparator import PartitionComparator
from pegasus.validation.reconciliation.partition_manager import PartitionManager
from pegasus.validation.reconciliation.partition_writer import PartitionWriter
from pegasus.validation.reconciliation.stream_csv_reader import StreamCSVReader
from pegasus.validation.reconciliation.temp_workspace import temp_reconciliation_workspace
from pegasus.validation.reconciliation.uid_generator import SHA256CompositeUIDGenerator, attach_composite_uid_column

__all__ = [
    "ReconciliationBackend",
    "ReconciliationCheckpoint",
    "ReconciliationCoordinator",
    "ReconciliationError",
    "ReconciliationMetrics",
    "ReconciliationRuntimeConfig",
    "ReconciliationStrategy",
    "ReconciliationStrategyError",
    "NoOpReconciliationMetrics",
    "SHA256CompositeUIDGenerator",
    "StreamCSVReader",
    "PartitionManager",
    "PartitionWriter",
    "PartitionComparator",
    "MismatchWriter",
    "attach_composite_uid_column",
    "auto_external_enabled",
    "temp_reconciliation_workspace",
]

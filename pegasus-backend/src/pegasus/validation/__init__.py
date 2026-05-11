"""Pegasus file validation engine (interfaces and modular layout)."""

from pegasus.validation.comparators import (
    ComparisonError,
    MismatchReport,
    MismatchType,
    UIDBasedComparator,
    UIDComparisonError,
    UIDKeyedLazyComparator,
    ValidationComparator,
)
from pegasus.validation.engine import ValidationEngine
from pegasus.validation.normalizers.base import Normalizer
from pegasus.validation.parsers.base import FrameParser
from pegasus.validation.readers.base import CSVReader
from pegasus.validation.reporters.base import MismatchReporter
from pegasus.validation.uids import SHA256CompositeUIDGenerator
from pegasus.validation.uids.base import UIDGenerator
from pegasus.validation.uids.exceptions import (
    UIDColumnNotFoundError,
    UIDConfigurationError,
    UIDGeneratorError,
)

__all__ = [
    "CSVReader",
    "ComparisonError",
    "FrameParser",
    "MismatchReport",
    "MismatchReporter",
    "MismatchType",
    "Normalizer",
    "SHA256CompositeUIDGenerator",
    "UIDBasedComparator",
    "UIDColumnNotFoundError",
    "UIDComparisonError",
    "UIDConfigurationError",
    "UIDGenerator",
    "UIDGeneratorError",
    "UIDKeyedLazyComparator",
    "ValidationComparator",
    "ValidationEngine",
]

"""High-level orchestration shell (wiring only; no validation logic yet)."""

from __future__ import annotations

from dataclasses import dataclass

from pegasus.validation.comparators.base import ValidationComparator
from pegasus.validation.normalizers.base import Normalizer
from pegasus.validation.parsers.base import FrameParser
from pegasus.validation.readers.base import CSVReader
from pegasus.validation.reporters.base import MismatchReporter
from pegasus.validation.uids.base import UIDGenerator


@dataclass(slots=True)
class ValidationEngine:
    """Composable validation pipeline dependencies.

    Individual stages (read → parse → normalize → key → compare → report)
    will be orchestrated here once business rules exist.
    """

    csv_reader: CSVReader
    parsers: tuple[FrameParser, ...]
    normalizers: tuple[Normalizer, ...]
    uid_generator: UIDGenerator
    comparator: ValidationComparator
    reporter: MismatchReporter

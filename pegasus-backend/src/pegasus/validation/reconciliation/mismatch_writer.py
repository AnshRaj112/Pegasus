"""Incremental mismatch serialization (JSON Lines) for huge validation runs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import TracebackType
from typing import Any, IO

logger = logging.getLogger(__name__)


class MismatchWriter:
    """Append canonical mismatch dicts to a newline-delimited JSON file.

    Each line is one JSON object compatible with :class:`MismatchCollector` row
    semantics (``uid``, ``mismatch_type``, ``column_name``, ``source_value``,
    ``target_value``, ``row_detail``). Callers flush explicitly via :meth:`close`.
    """

    __slots__ = ("_path", "_fp", "_lines")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp: IO[str] | None = None
        self._lines = 0

    def __enter__(self) -> MismatchWriter:
        self._fp = self._path.open("w", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def write_record(self, record: dict[str, Any]) -> None:
        """Serialize *record* as one JSON line (UTF-8)."""
        if self._fp is None:
            raise RuntimeError("MismatchWriter is not open; use as context manager or call open()")
        self._fp.write(json.dumps(record, default=str, ensure_ascii=False))
        self._fp.write("\n")
        self._lines += 1
        if self._lines % 50_000 == 0:
            logger.info("MismatchWriter path=%s lines=%d", self._path.name, self._lines)

    @property
    def line_count(self) -> int:
        return self._lines

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None
            logger.info("MismatchWriter closed path=%s total_lines=%d", self._path, self._lines)

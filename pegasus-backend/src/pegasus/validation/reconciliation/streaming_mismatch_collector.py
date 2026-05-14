"""Stream mismatch rows to NDJSON; finish() returns an empty in-memory frame plus counts."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, TextIO

import polars as pl

from pegasus.validation.comparators.models import (
    MismatchReport,
    MismatchType,
    empty_mismatch_frame,
)

from .row_detail import encode_row_detail

logger = logging.getLogger(__name__)


class StreamingMismatchCollector:
    """Like :class:`~.mismatch_collector.MismatchCollector` but persists each flush to *artifact_path*.

    Never builds a giant concatenated :class:`~polars.DataFrame`; :meth:`finish` returns an empty
    ``mismatches`` frame with accurate ``summary`` and sets :attr:`MismatchReport.mismatch_artifact_path`.
    """

    def __init__(
        self,
        artifact_path: Path,
        *,
        chunk_cap: int = 8192,
        stringify_null_in_report: bool = True,
        omit_row_detail: bool = False,
        ndjson_mirror_path: Path | None = None,
    ) -> None:
        if chunk_cap < 256:
            raise ValueError("chunk_cap must be >= 256")
        self._artifact_path = artifact_path
        self._artifact_path.parent.mkdir(parents=True, exist_ok=True)
        self._artifact_fp: TextIO = self._artifact_path.open("w", encoding="utf-8")
        self._chunk_cap = chunk_cap
        self._stringify_null = stringify_null_in_report
        self._omit_row_detail = omit_row_detail
        self._ndjson_mirror_path = ndjson_mirror_path
        self._ndjson_fp: TextIO | None = None
        self._incremental_summary: dict[str, int] = defaultdict(int)
        self._buf_missing: list[dict[str, Any]] = []
        self._buf_extra: list[dict[str, Any]] = []
        self._buf_value: list[dict[str, Any]] = []

    @property
    def omit_row_detail(self) -> bool:
        return self._omit_row_detail

    def _write_lines(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        fp = self._artifact_fp
        for r in rows:
            fp.write(json.dumps(r, default=str, ensure_ascii=False))
            fp.write("\n")
        fp.flush()

    def _maybe_flush(self) -> None:
        total = len(self._buf_missing) + len(self._buf_extra) + len(self._buf_value)
        if total < self._chunk_cap:
            return
        if len(self._buf_value) >= len(self._buf_missing) and len(self._buf_value) >= len(self._buf_extra):
            self._flush_value_buffer()
        elif len(self._buf_missing) >= len(self._buf_extra):
            self._flush_missing_buffer()
        else:
            self._flush_extra_buffer()

    def _flush_missing_buffer(self) -> None:
        if not self._buf_missing:
            return
        records = self._buf_missing
        self._buf_missing = []
        if self._omit_row_detail:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": "{}",
                }
                for r in records
            ]
        else:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": encode_row_detail(r["source_record"], None),
                }
                for r in records
            ]
        self._incremental_summary[MismatchType.MISSING_IN_TARGET.value] += len(rows)
        self._write_lines(rows)
        self._mirror_ndjson_rows(rows)

    def _flush_extra_buffer(self) -> None:
        if not self._buf_extra:
            return
        records = self._buf_extra
        self._buf_extra = []
        if self._omit_row_detail:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": "{}",
                }
                for r in records
            ]
        else:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": encode_row_detail(None, r["target_record"]),
                }
                for r in records
            ]
        self._incremental_summary[MismatchType.EXTRA_IN_TARGET.value] += len(rows)
        self._write_lines(rows)
        self._mirror_ndjson_rows(rows)

    def _flush_value_buffer(self) -> None:
        if not self._buf_value:
            return
        records = self._buf_value
        self._buf_value = []
        rows = [
            {
                "uid": r["uid"],
                "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                "column_name": r["column_name"],
                "source_value": r["source_value"],
                "target_value": r["target_value"],
                "row_detail": r["row_detail"],
            }
            for r in records
        ]
        self._incremental_summary[MismatchType.VALUE_MISMATCH.value] += len(rows)
        self._write_lines(rows)
        self._mirror_ndjson_rows(rows)

    def _mirror_ndjson_rows(self, rows: list[dict[str, Any]]) -> None:
        if self._ndjson_mirror_path is None or not rows:
            return
        if self._ndjson_fp is None:
            self._ndjson_mirror_path.parent.mkdir(parents=True, exist_ok=True)
            self._ndjson_fp = self._ndjson_mirror_path.open("w", encoding="utf-8")
        for r in rows:
            self._ndjson_fp.write(json.dumps(r, default=str, ensure_ascii=False))
            self._ndjson_fp.write("\n")

    def add_missing(self, *, uid: str, source_record: dict[str, Any]) -> None:
        self._buf_missing.append({"uid": uid, "source_record": source_record})
        self._maybe_flush()

    def add_extra(self, *, uid: str, target_record: dict[str, Any]) -> None:
        self._buf_extra.append({"uid": uid, "target_record": target_record})
        self._maybe_flush()

    def add_value_mismatch(
        self,
        *,
        uid: str,
        column_name: str,
        source_value: Any,
        target_value: Any,
        source_record: dict[str, Any],
        target_record: dict[str, Any],
        row_detail: str | None = None,
    ) -> None:
        sv = self._serialize_cell(source_value)
        tv = self._serialize_cell(target_value)
        if row_detail is not None:
            detail = row_detail
        else:
            detail = "{}" if self._omit_row_detail else encode_row_detail(source_record, target_record)
        self._buf_value.append(
            {
                "uid": uid,
                "column_name": column_name,
                "source_value": sv,
                "target_value": tv,
                "row_detail": detail,
            }
        )
        self._maybe_flush()

    def _serialize_cell(self, value: Any) -> str | None:
        if value is None and not self._stringify_null:
            return None
        if self._stringify_null and value is None:
            return "<null>"
        return str(value)

    def bulk_append_from_frame(self, frame: pl.DataFrame) -> None:
        """Vectorized append of formatted mismatch rows to the NDJSON artifact.
        
        The frame MUST already have the schema (uid, mismatch_type, column_name, source_value, target_value, row_detail).
        """
        if frame.is_empty():
            return
            
        # Use Polars to write NDJSON directly to a temp file, then append it to our artifact
        # This is 100x faster than a Python dictionary loop.
        temp_out = self._artifact_path.parent / f"bulk_{uuid.uuid4().hex}.ndjson"
        try:
            frame.write_ndjson(temp_out)
            with open(temp_out, "rb") as f_in:
                # Close our current handle temporarily to allow another writer or use atomic appends if possible
                # Actually, we can just write from the worker's own process.
                shutil.copyfileobj(f_in, self._artifact_fp.buffer)
                self._artifact_fp.buffer.flush()
        finally:
            if temp_out.exists():
                temp_out.unlink()

        # Update summary counts vectorized
        counts = frame.group_by("mismatch_type").len().collect() if isinstance(frame, pl.LazyFrame) else frame.group_by("mismatch_type").len()
        for row in counts.iter_rows(named=True):
            self._incremental_summary[str(row["mismatch_type"])] += int(row["len"])

    def finish(self) -> MismatchReport:
        self._flush_missing_buffer()
        self._flush_extra_buffer()
        self._flush_value_buffer()
        if self._ndjson_fp is not None:
            self._ndjson_fp.close()
            self._ndjson_fp = None
            logger.info("Mismatch NDJSON mirror closed path=%s", self._ndjson_mirror_path)
        self._artifact_fp.close()

        summary = {
            MismatchType.MISSING_IN_TARGET.value: int(
                self._incremental_summary.get(MismatchType.MISSING_IN_TARGET.value, 0)
            ),
            MismatchType.EXTRA_IN_TARGET.value: int(
                self._incremental_summary.get(MismatchType.EXTRA_IN_TARGET.value, 0)
            ),
            MismatchType.VALUE_MISMATCH.value: int(
                self._incremental_summary.get(MismatchType.VALUE_MISMATCH.value, 0)
            ),
        }
        logger.info(
            "StreamingMismatchCollector finished path=%s missing=%s extra=%s value=%s",
            self._artifact_path,
            summary[MismatchType.MISSING_IN_TARGET.value],
            summary[MismatchType.EXTRA_IN_TARGET.value],
            summary[MismatchType.VALUE_MISMATCH.value],
        )
        return MismatchReport(
            mismatches=empty_mismatch_frame(),
            summary=summary,
            mismatch_artifact_path=self._artifact_path,
        )

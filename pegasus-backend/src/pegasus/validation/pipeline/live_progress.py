# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T08:53:50Z
# --- END GENERATED FILE METADATA ---

"""Thread-safe live progress snapshots for long-running spill reconciliation."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class SideProgress:
    rows_processed: int = 0
    chunks_completed: int = 0
    current_chunk_rows: int = 0
    status: str = "pending"  # pending | active | done


@dataclass
class ReconcileProgress:
    partitions_total: int = 0
    partitions_done: int = 0


ProgressCallback = Callable[[dict[str, Any]], None]


class LiveProgressTracker:
    """Collect partition/reconcile counters and emit throttled status updates."""

    __slots__ = (
        "_callback",
        "_lock",
        "_chunk_rows",
        "_column_count",
        "_partition_buckets",
        "_partition_workers",
        "_reconcile_workers",
        "_est_rows",
        "_pipeline_phase",
        "_source",
        "_target",
        "_reconcile",
        "_last_emit",
        "_emit_interval",
    )

    def __init__(
        self,
        callback: ProgressCallback | None,
        *,
        chunk_rows: int,
        column_count: int,
        partition_buckets: int,
        partition_workers: int = 2,
        reconcile_workers: int = 1,
        est_rows: int | None = None,
        emit_interval_seconds: float = 0.75,
    ) -> None:
        self._callback = callback
        self._lock = threading.Lock()
        self._chunk_rows = max(1, int(chunk_rows))
        self._column_count = max(0, int(column_count))
        self._partition_buckets = max(1, int(partition_buckets))
        self._partition_workers = max(1, int(partition_workers))
        self._reconcile_workers = max(1, int(reconcile_workers))
        self._est_rows = int(est_rows) if est_rows and est_rows > 0 else None
        self._pipeline_phase = "partition"
        self._source = SideProgress()
        self._target = SideProgress()
        self._reconcile = ReconcileProgress()
        self._last_emit = 0.0
        self._emit_interval = max(0.0, float(emit_interval_seconds))

    def begin_partition(self) -> None:
        with self._lock:
            self._pipeline_phase = "partition"
            self._reconcile = ReconcileProgress()
        self._emit(force=True)

    def side_started(self, side: str) -> None:
        slot = self._side(side)
        with self._lock:
            slot.status = "active"
            slot.current_chunk_rows = 0
        self._emit()

    def on_chunk(self, side: str, *, chunk_index: int, rows_in_chunk: int) -> None:
        slot = self._side(side)
        with self._lock:
            slot.chunks_completed = max(slot.chunks_completed, chunk_index + 1)
            slot.current_chunk_rows = max(0, int(rows_in_chunk))
            slot.rows_processed += slot.current_chunk_rows
            slot.status = "active"
        self._emit()

    def side_finished(self, side: str, *, total_rows: int | None = None) -> None:
        slot = self._side(side)
        with self._lock:
            if total_rows is not None:
                slot.rows_processed = max(slot.rows_processed, int(total_rows))
            slot.current_chunk_rows = 0
            slot.status = "done"
        self._emit(force=True)

    def begin_reconcile(self, *, partitions_total: int, reconcile_workers: int | None = None) -> None:
        with self._lock:
            self._pipeline_phase = "reconcile"
            self._reconcile = ReconcileProgress(
                partitions_total=max(0, int(partitions_total)),
                partitions_done=0,
            )
            if reconcile_workers is not None:
                self._reconcile_workers = max(1, int(reconcile_workers))
        self._emit(force=True)

    def on_reconcile_done(self, *, partitions_done: int) -> None:
        with self._lock:
            self._reconcile.partitions_done = max(
                self._reconcile.partitions_done,
                int(partitions_done),
            )
        self._emit(force=True)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "pipeline_phase": self._pipeline_phase,
                "chunk_rows": self._chunk_rows,
                "column_count": self._column_count,
                "partition_buckets": self._partition_buckets,
                "partition_parallel_workers": self._partition_workers,
                "reconcile_parallel_workers": self._reconcile_workers,
                "estimated_rows": self._est_rows,
                "source": {
                    "rows_processed": self._source.rows_processed,
                    "chunks_completed": self._source.chunks_completed,
                    "current_chunk_rows": self._source.current_chunk_rows,
                    "status": self._source.status,
                },
                "target": {
                    "rows_processed": self._target.rows_processed,
                    "chunks_completed": self._target.chunks_completed,
                    "current_chunk_rows": self._target.current_chunk_rows,
                    "status": self._target.status,
                },
                "reconcile": {
                    "partitions_total": self._reconcile.partitions_total,
                    "partitions_done": self._reconcile.partitions_done,
                },
            }

    def _side(self, side: str) -> SideProgress:
        if side == "target":
            return self._target
        return self._source

    def _percent(self) -> float | None:
        with self._lock:
            phase = self._pipeline_phase
            if phase == "partition":
                if self._est_rows:
                    src_ratio = min(1.0, self._source.rows_processed / self._est_rows)
                    tgt_ratio = min(1.0, self._target.rows_processed / self._est_rows)
                    return round(((src_ratio + tgt_ratio) / 2.0) * 65.0, 1)
                chunks = self._source.chunks_completed + self._target.chunks_completed
                if chunks <= 0:
                    return 1.0
                return round(min(65.0, 5.0 + chunks * 2.0), 1)
            if phase == "reconcile":
                total = self._reconcile.partitions_total
                done = self._reconcile.partitions_done
                if total <= 0:
                    return 70.0
                return round(65.0 + (done / total) * 30.0, 1)
        return None

    def _message(self) -> str:
        snap = self.snapshot()
        phase = snap["pipeline_phase"]
        if phase == "partition":
            parts: list[str] = []
            for label, key in (("source", "source"), ("target", "target")):
                side = snap[key]
                if side["status"] == "active":
                    chunk_no = side["chunks_completed"] or 1
                    rows = side["current_chunk_rows"] or side["rows_processed"]
                    parts.append(f"{label} chunk {chunk_no} ({rows:,} rows)")
                elif side["status"] == "done":
                    parts.append(f"{label} done ({side['rows_processed']:,} rows)")
            detail = " · ".join(parts) if parts else "starting"
            cols = snap["column_count"]
            col_note = f" · {cols} columns" if cols else ""
            return (
                f"Partitioning {detail}{col_note} "
                f"· {snap['partition_parallel_workers']} parallel readers"
            )
        total = snap["reconcile"]["partitions_total"]
        done = snap["reconcile"]["partitions_done"]
        workers = snap["reconcile_parallel_workers"]
        return f"Reconciling partitions {done:,}/{total:,} · {workers} parallel workers"

    def _emit(self, *, force: bool = False) -> None:
        if self._callback is None:
            return
        now = time.time()
        if not force and now - self._last_emit < self._emit_interval:
            return
        self._last_emit = now
        percent = self._percent()
        payload: dict[str, Any] = {
            "phase": "partitioning" if self._pipeline_phase == "partition" else "reconciling",
            "message": self._message(),
            "live": True,
            "progress": {
                "live": self.snapshot(),
            },
        }
        if percent is not None:
            payload["percent"] = percent
        self._callback(payload)

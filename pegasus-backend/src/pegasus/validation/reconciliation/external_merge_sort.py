"""External merge-sort materialization for CSV inputs (Polars runs + merge_sorted)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader

from .exceptions import ReconciliationError
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics

logger = logging.getLogger(__name__)


class ExternalMergeSortEngine:
    """Chunk-sort CSV rows to Parquet runs, then merge into one sorted Parquet file."""

    __slots__ = ("_reader", "_metrics")

    def __init__(
        self,
        reader: PolarsCSVReader,
        *,
        metrics: ReconciliationMetrics | None = None,
    ) -> None:
        self._reader = reader
        self._metrics = metrics or NoOpReconciliationMetrics()

    def materialize_sorted_parquet(
        self,
        csv_path: Path,
        *,
        workspace: Path,
        side: str,
        uid_column: str,
        delimiter: str,
        chunk_rows: int,
        has_header: bool = True,
    ) -> Path:
        """Return path to a single sorted Parquet file under *workspace*.

        The output key column is cast to :class:`polars.String` for stable ordering.
        """
        runs_dir = workspace / "sort_runs" / side
        if runs_dir.exists():
            shutil.rmtree(runs_dir)
        runs_dir.mkdir(parents=True, exist_ok=True)

        read_opts: dict[str, object] = {
            "separator": delimiter,
            "encoding": "utf-8",
            "has_header": has_header,
        }
        out_path = workspace / f"{side}_sorted.parquet"

        self._metrics.on_phase_start("external_sort_runs", side=side, path=str(csv_path))
        run_idx = 0
        try:
            for batch in self._reader.iter_batches(csv_path, batch_size=chunk_rows, read_options=read_opts):
                if uid_column not in batch.columns:
                    raise ReconciliationError(
                        f"uid_column {uid_column!r} not in batch columns: {batch.columns}"
                    )
                sorted_batch = batch.with_columns(pl.col(uid_column).cast(pl.String)).sort(
                    uid_column,
                    maintain_order=False,
                )
                run_idx += 1
                sorted_batch.write_parquet(runs_dir / f"run_{run_idx:06d}.parquet")
        except pl_exc.PolarsError as exc:
            logger.exception("External sort run generation failed for %s", csv_path)
            raise ReconciliationError(f"External sort failed while reading {csv_path}") from exc

        self._metrics.on_phase_end("external_sort_runs", side=side, runs=run_idx)

        paths = sorted(runs_dir.glob("*.parquet"))
        if not paths:
            # Header-only or empty body: infer at least uid column exists via schema probe.
            schema = self._reader.detect_schema(
                csv_path,
                delimiter=delimiter,
                encoding="utf-8",
                has_header=has_header,
            )
            if uid_column not in schema:
                raise ReconciliationError(f"uid_column {uid_column!r} not present in CSV schema")
            empty = pl.DataFrame(schema={c: schema[c] for c in schema})
            empty.write_parquet(out_path)
            logger.info("External sort produced empty sorted output for %s", csv_path.name)
            return out_path

        self._metrics.on_phase_start("external_sort_merge", side=side, runs=len(paths))
        try:
            if len(paths) == 1:
                shutil.copy(paths[0], out_path)
            else:
                scans = [pl.scan_parquet(p) for p in paths]
                merged = pl.merge_sorted(scans, key=uid_column)
                merged.sink_parquet(out_path)
        except pl_exc.PolarsError as exc:
            logger.exception("External sort merge phase failed for %s", csv_path)
            raise ReconciliationError(f"External sort merge failed for {csv_path}") from exc

        self._metrics.on_phase_end("external_sort_merge", side=side, output=str(out_path))
        logger.info("External sort complete side=%s runs=%d output=%s", side, len(paths), out_path.name)
        return out_path

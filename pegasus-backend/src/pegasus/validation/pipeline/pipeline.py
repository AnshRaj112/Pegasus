"""Six-stage tabular reconciliation pipeline."""

from __future__ import annotations

import hashlib
import json
import struct
import time
from pathlib import Path
from typing import Any

from pegasus.validation.adapters.base import TabularSourceAdapter, TabularSchema
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.in_memory import try_in_memory_reconcile
from pegasus.validation.pipeline.result import (
    ColumnDifference,
    MismatchSample,
    PipelineResult,
    SchemaDifference,
)


def _canonical(value: Any) -> str:
    if value is None:
        return "__NULL__"
    text = str(value).strip()
    if text.lower() in ("", "null", "none", "na", "n/a"):
        return "__NULL__"
    return text


def _identity_key(record: dict[str, Any], columns: list[str]) -> str:
    return "|".join(_canonical(record.get(c)) for c in columns)


def _row_fingerprint(record: dict[str, Any], columns: list[str]) -> str:
    if not columns:
        return ""
    parts = [_canonical(record.get(c)) for c in columns]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _partition_id(key: str, num_partitions: int) -> int:
    h = hashlib.md5(key.encode()).digest()
    return int.from_bytes(h[:4], "big") % num_partitions


def _adapter_size_bytes(adapter: object) -> int:
    getter = getattr(adapter, "get_size_bytes", None)
    if callable(getter):
        return int(getter())
    return int(Path(getattr(adapter, "path")).stat().st_size)


def _adaptive_partition_count(
    *,
    source_bytes: int,
    target_bytes: int,
    requested: int,
) -> int:
    """Use fewer buckets for small files to avoid empty-partition overhead."""
    file_bytes = source_bytes + target_bytes
    if file_bytes <= 4 * 1024 * 1024:
        return min(requested, 16)
    if file_bytes <= 32 * 1024 * 1024:
        return min(requested, 64)
    if file_bytes <= 128 * 1024 * 1024:
        return min(requested, 256)
    return requested


class _PartitionWriter:
    def __init__(self, base: Path, side: str, *, store_payload: bool) -> None:
        self.base = base / side
        self.base.mkdir(parents=True, exist_ok=True)
        self._handles: dict[int, Any] = {}
        self._store_payload = store_payload

    def write(self, partition_id: int, identity: str, fingerprint: str, raw: dict) -> None:
        path = self.base / f"part_{partition_id:05d}.bin"
        if partition_id not in self._handles:
            self._handles[partition_id] = open(path, "ab")  # noqa: SIM115
        payload: dict[str, Any] = {"k": identity, "f": fingerprint}
        if self._store_payload:
            payload["d"] = raw
        data = json.dumps(payload, separators=(",", ":"), default=str).encode()
        self._handles[partition_id].write(struct.pack(">I", len(data)) + data)

    def close(self) -> None:
        for h in self._handles.values():
            h.close()
        self._handles.clear()


def _iter_partition(path: Path):
    if not path.exists():
        return
    with open(path, "rb") as f:
        while True:
            header = f.read(4)
            if len(header) < 4:
                break
            length = struct.unpack(">I", header)[0]
            body = f.read(length)
            if len(body) < length:
                break
            yield json.loads(body)


def _compare_schemas(source: TabularSchema, target: TabularSchema) -> list[SchemaDifference]:
    diffs: list[SchemaDifference] = []
    src = {c.name: c for c in source.columns}
    tgt = {c.name: c for c in target.columns}
    for name in src:
        if name not in tgt:
            diffs.append(SchemaDifference(name, "missing_in_target", source_value=name))
        elif src[name].data_type != tgt[name].data_type:
            diffs.append(SchemaDifference(
                name, "type_mismatch", src[name].data_type, tgt[name].data_type
            ))
    for name in tgt:
        if name not in src:
            diffs.append(SchemaDifference(name, "extra_in_target", target_value=name))
    return diffs


class TabularReconciliationPipeline:
    """Streaming partition-based reconciliation (Stages 1–6)."""

    __slots__ = ("_source", "_target", "_identity_columns", "_compare_columns", "_config")

    def __init__(
        self,
        source: TabularSourceAdapter,
        target: TabularSourceAdapter,
        *,
        identity_columns: list[str],
        compare_columns: list[str],
        config: TabularPipelineConfig,
    ) -> None:
        self._source = source
        self._target = target
        self._identity_columns = identity_columns
        self._compare_columns = compare_columns
        self._config = config

    def run(self, *, workspace: Path | None = None) -> PipelineResult:
        if self._config.enable_in_memory_reconcile:
            in_memory = try_in_memory_reconcile(
                self._source,
                self._target,
                identity_columns=self._identity_columns,
                compare_columns=self._compare_columns,
                memory_budget_bytes=self._config.memory_budget_bytes,
                enable_column_drilldown=self._config.enable_column_drilldown,
            )
            if in_memory is not None:
                return in_memory

        t0 = time.perf_counter()
        num_partitions = _adaptive_partition_count(
            source_bytes=_adapter_size_bytes(self._source),
            target_bytes=_adapter_size_bytes(self._target),
            requested=self._config.resolved_partition_count(),
        )
        chunk_rows = self._config.chunk_rows
        store_payload = self._config.enable_column_drilldown

        src_schema = self._source.get_schema()
        tgt_schema = self._target.get_schema()
        schema_diffs = _compare_schemas(src_schema, tgt_schema)

        work = workspace or Path("/tmp/pegasus_reconcile")
        work.mkdir(parents=True, exist_ok=True)
        src_writer = _PartitionWriter(work, "source", store_payload=store_payload)
        tgt_writer = _PartitionWriter(work, "target", store_payload=store_payload)

        src_rows = self._partition_side(self._source, src_writer, chunk_rows, num_partitions)
        tgt_rows = self._partition_side(self._target, tgt_writer, chunk_rows, num_partitions)
        src_writer.close()
        tgt_writer.close()

        missing = extra = changed = matching = 0
        mismatched_partitions = 0
        samples: list[MismatchSample] = []
        sample_limit = 1000

        for pid in range(num_partitions):
            src_path = work / "source" / f"part_{pid:05d}.bin"
            tgt_path = work / "target" / f"part_{pid:05d}.bin"
            if not src_path.exists() and not tgt_path.exists():
                continue

            if store_payload:
                src_map: dict[str, tuple[str, dict]] = {}
                for rec in _iter_partition(src_path):
                    src_map[rec["k"]] = (rec["f"], rec.get("d") or {})
            else:
                src_fp: dict[str, str] = {}
                for rec in _iter_partition(src_path):
                    src_fp[rec["k"]] = rec["f"]

            tgt_keys: set[str] = set()
            part_changed = part_missing = part_extra = 0

            for rec in _iter_partition(tgt_path):
                key = rec["k"]
                tgt_keys.add(key)
                if store_payload:
                    src_entry = src_map.get(key)
                    if src_entry is None:
                        part_extra += 1
                        if len(samples) < sample_limit:
                            samples.append(MismatchSample(key, "extra"))
                    elif src_entry[0] != rec["f"]:
                        part_changed += 1
                        col_diffs: list[ColumnDifference] = []
                        _, src_data = src_entry
                        for col in self._compare_columns:
                            sv = _canonical(src_data.get(col))
                            tv = _canonical((rec.get("d") or {}).get(col))
                            if sv != tv:
                                col_diffs.append(ColumnDifference(col, sv, tv))
                        if len(samples) < sample_limit:
                            samples.append(MismatchSample(key, "changed", col_diffs))
                    else:
                        matching += 1
                else:
                    fp = src_fp.get(key)
                    if fp is None:
                        part_extra += 1
                        if len(samples) < sample_limit:
                            samples.append(MismatchSample(key, "extra"))
                    elif fp != rec["f"]:
                        part_changed += 1
                        if len(samples) < sample_limit:
                            samples.append(MismatchSample(key, "changed"))
                    else:
                        matching += 1

            key_source = src_map if store_payload else src_fp
            for key in key_source:
                if key not in tgt_keys:
                    part_missing += 1
                    if len(samples) < sample_limit:
                        samples.append(MismatchSample(key, "missing"))

            missing += part_missing
            extra += part_extra
            changed += part_changed
            if part_missing or part_extra or part_changed:
                mismatched_partitions += 1

        elapsed = time.perf_counter() - t0
        return PipelineResult(
            schema_valid=len(schema_diffs) == 0,
            schema_differences=schema_diffs,
            source_row_count=src_rows,
            target_row_count=tgt_rows,
            row_count_match=(src_rows == tgt_rows),
            missing_count=missing,
            extra_count=extra,
            changed_count=changed,
            matching_count=matching,
            partitions_processed=num_partitions,
            mismatched_partitions=mismatched_partitions,
            sample_mismatches=samples,
            compared_columns=list(self._compare_columns),
            execution_seconds=elapsed,
        )

    def _partition_side(
        self,
        adapter: TabularSourceAdapter,
        writer: _PartitionWriter,
        chunk_rows: int,
        num_partitions: int,
    ) -> int:
        total = 0
        for chunk in adapter.stream_records(chunk_rows):
            for record in chunk:
                identity = _identity_key(record, self._identity_columns)
                fp = _row_fingerprint(record, self._compare_columns)
                pid = _partition_id(identity, num_partitions)
                writer.write(pid, identity, fp, record)
                total += 1
        return total

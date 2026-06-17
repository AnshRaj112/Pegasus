# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T11:17:59Z
# --- END GENERATED FILE METADATA ---

"""External-memory management with disk spilling and backpressure."""

import gc
import os
import resource
import tempfile
from pathlib import Path
from typing import Any, Optional


class MemoryMonitor:
    """Tracks memory usage and triggers spill when threshold exceeded."""

    def __init__(self, limit_mb: int, spill_threshold_pct: float = 0.75):
        self.limit_bytes = limit_mb * 1024 * 1024
        self.spill_threshold = int(self.limit_bytes * spill_threshold_pct)
        self.peak_bytes = 0
        self.spill_bytes = 0

    def current_usage_bytes(self) -> int:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KB, macOS reports bytes
        if os.uname().sysname == "Linux":
            usage *= 1024
        self.peak_bytes = max(self.peak_bytes, usage)
        return usage

    def should_spill(self) -> bool:
        return self.current_usage_bytes() >= self.spill_threshold

    def record_spill(self, bytes_written: int) -> None:
        self.spill_bytes += bytes_written
        gc.collect()

    @property
    def peak_mb(self) -> float:
        peak = self.peak_bytes
        if os.uname().sysname == "Linux":
            peak = self.peak_bytes  # already converted
        return peak / (1024 * 1024)

    @property
    def spill_mb(self) -> float:
        return self.spill_bytes / (1024 * 1024)


class SpillBuffer:
    """In-memory buffer that spills to disk when memory threshold is reached."""

    def __init__(
        self,
        memory_monitor: MemoryMonitor,
        spill_dir: Path,
        max_buffer_records: int = 50000,
    ):
        self.monitor = memory_monitor
        self.spill_dir = spill_dir
        self.spill_dir.mkdir(parents=True, exist_ok=True)
        self.max_buffer_records = max_buffer_records
        self._buffer: list[Any] = []
        self._spill_files: list[Path] = []
        self._spill_index = 0

    def add(self, item: Any) -> None:
        self._buffer.append(item)
        if len(self._buffer) >= self.max_buffer_records or self.monitor.should_spill():
            self._flush_to_disk()

    def _flush_to_disk(self) -> None:
        if not self._buffer:
            return
        import json

        spill_path = self.spill_dir / f"spill_{self._spill_index:06d}.jsonl"
        with open(spill_path, "w") as f:
            for item in self._buffer:
                if hasattr(item, "serialize"):
                    f.write(item.serialize().decode("latin-1") + "\n")
                else:
                    f.write(json.dumps(item, default=str) + "\n")
        bytes_written = spill_path.stat().st_size
        self.monitor.record_spill(bytes_written)
        self._spill_files.append(spill_path)
        self._spill_index += 1
        self._buffer.clear()

    def flush(self) -> None:
        self._flush_to_disk()

    @property
    def spill_file_count(self) -> int:
        return len(self._spill_files)


class ExternalHashTable:
    """
    Disk-backed hash table for partition reconciliation.
    Uses external hash join technique: build phase spills buckets to disk,
    probe phase reads matching buckets sequentially.
    """

    def __init__(self, spill_dir: Path, memory_monitor: MemoryMonitor, bucket_count: int = 256):
        self.spill_dir = spill_dir
        self.spill_dir.mkdir(parents=True, exist_ok=True)
        self.monitor = memory_monitor
        self.bucket_count = bucket_count
        self._buckets: dict[int, dict[str, tuple[str, dict]]] = {
            i: {} for i in range(bucket_count)
        }
        self._bucket_sizes: dict[int, int] = {i: 0 for i in range(bucket_count)}
        self._max_bucket_size = 10000

    def _bucket_id(self, key: str) -> int:
        return hash(key) % self.bucket_count

    def insert(self, key: str, fingerprint: str, raw_data: dict) -> None:
        bid = self._bucket_id(key)
        if self._bucket_sizes[bid] >= self._max_bucket_size or self.monitor.should_spill():
            self._spill_bucket(bid)
        self._buckets[bid][key] = (fingerprint, raw_data)
        self._bucket_sizes[bid] += 1

    def _spill_bucket(self, bucket_id: int) -> None:
        bucket = self._buckets[bucket_id]
        if not bucket:
            return
        import json

        path = self.spill_dir / f"bucket_{bucket_id:04d}.jsonl"
        mode = "a" if path.exists() else "w"
        with open(path, mode) as f:
            for key, (fp, data) in bucket.items():
                line = json.dumps({"k": key, "f": fp, "d": data}, default=str)
                f.write(line + "\n")
        self.monitor.record_spill(path.stat().st_size if path.exists() else 0)
        bucket.clear()
        self._bucket_sizes[bucket_id] = 0

    def lookup(self, key: str) -> Optional[tuple[str, dict]]:
        bid = self._bucket_id(key)
        in_mem = self._buckets[bid].get(key)
        if in_mem:
            return in_mem
        return self._lookup_spilled(bid, key)

    def _lookup_spilled(self, bucket_id: int, key: str) -> Optional[tuple[str, dict]]:
        import json

        path = self.spill_dir / f"bucket_{bucket_id:04d}.jsonl"
        if not path.exists():
            return None
        with open(path) as f:
            for line in f:
                entry = json.loads(line)
                if entry["k"] == key:
                    return entry["f"], entry["d"]
        return None

    def iter_all_keys(self) -> Any:
        """Iterate all keys from memory and spilled buckets."""
        import json

        seen: set[str] = set()
        for bid, bucket in self._buckets.items():
            for key in bucket:
                if key not in seen:
                    seen.add(key)
                    yield key
        for path in sorted(self.spill_dir.glob("bucket_*.jsonl")):
            with open(path) as f:
                for line in f:
                    entry = json.loads(line)
                    if entry["k"] not in seen:
                        seen.add(entry["k"])
                        yield entry["k"]

    def flush_all(self) -> None:
        for bid in range(self.bucket_count):
            if self._buckets[bid]:
                self._spill_bucket(bid)


class ExternalMergeSorter:
    """External merge sort for partition files when ordering is needed."""

    def __init__(self, spill_dir: Path, memory_monitor: MemoryMonitor, chunk_size: int = 10000):
        self.spill_dir = spill_dir
        self.monitor = memory_monitor
        self.chunk_size = chunk_size

    def sort_file(self, input_path: Path, output_path: Path, key_fn: Any) -> None:
        if not input_path.exists() or input_path.stat().st_size == 0:
            output_path.touch()
            return

        from category1.core.partitioner import PartitionRecord, PartitionReader

        runs: list[Path] = []
        chunk: list[tuple[str, bytes]] = []
        run_idx = 0

        for record in PartitionReader(input_path):
            sort_key = key_fn(record)
            chunk.append((sort_key, record.serialize()))
            if len(chunk) >= self.chunk_size:
                runs.append(self._write_run(chunk, run_idx))
                run_idx += 1
                chunk = []

        if chunk:
            runs.append(self._write_run(chunk, run_idx))

        if len(runs) == 1:
            runs[0].rename(output_path)
            return

        self._merge_runs(runs, output_path)

    def _write_run(self, chunk: list[tuple[str, bytes]], run_idx: int) -> Path:
        chunk.sort(key=lambda x: x[0])
        run_path = self.spill_dir / f"run_{run_idx:06d}.bin"
        with open(run_path, "wb") as f:
            for _, data in chunk:
                f.write(data)
        self.monitor.record_spill(run_path.stat().st_size)
        return run_path

    def _merge_runs(self, runs: list[Path], output_path: Path) -> None:
        import struct

        from category1.core.partitioner import PartitionRecord

        iterators = []
        for run_path in runs:
            f = open(run_path, "rb")  # noqa: SIM115
            iterators.append((f, self._read_next(f)))

        with open(output_path, "wb") as out:
            while True:
                best = None
                best_idx = -1
                for i, (f, rec) in enumerate(iterators):
                    if rec is None:
                        continue
                    key = rec.identity_key
                    if best is None or key < best.identity_key:
                        best = rec
                        best_idx = i
                if best is None:
                    break
                out.write(best.serialize())
                f, _ = iterators[best_idx]
                iterators[best_idx] = (f, self._read_next(f))

        for f, _ in iterators:
            f.close()
        for run in runs:
            run.unlink(missing_ok=True)

    def _read_next(self, f: Any) -> Any:
        from category1.core.partitioner import PartitionRecord

        header = f.read(4)
        if len(header) < 4:
            return None
        length = struct.unpack(">I", header)[0]
        data = f.read(length)
        if len(data) < length:
            return None
        return PartitionRecord.deserialize(data)

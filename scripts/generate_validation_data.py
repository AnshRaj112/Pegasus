#!/usr/bin/env python3
"""
Generate paired source/target CSVs for Pegasus UID-based validation.

Join key is the UID column (default ``id``). **Physical row order does not matter**:
target rows may appear in any order; only matching UIDs are compared.

Expected counts (same semantics as ``POST /api/v1/validate``):

- **missing_in_target**: UIDs that appear in source but not in target (whole-row gaps).
- **extra_in_target**: UIDs that appear in target but not in source.
- **value_mismatch**: *Long-form* records — one row **per compared column** that differs
  for a UID present in both files. If you flip *C* columns on *V* UIDs, this adds
  ``V * C`` to ``value_mismatch`` (not ``V`` alone).

- **total_mismatch_records**: ``missing_in_target + extra_in_target + value_mismatch``.

Very large ``--source-rows`` (e.g. 100_000_000) uses chunked streaming writes and avoids
holding the full dataset in memory. Use a fast disk; generation time is dominated by I/O.

Shell notes:

- **Required:** every run needs ``--source-rows`` (and ``--out-dir`` unless ``--dry-run``).
- Use ``--out-dir`` / ``--value-mismatch-uids`` (one hyphen after ``--``). A space like
  ``-- out-dir`` is wrong and drops flags so you see "``--source-rows`` required".

Examples (single lines — safe to copy-paste). **Use a real writable directory on your machine**
(``./test-data/...``, ``~/bench/...``, or an absolute path you own). Do not use placeholder paths
from old docs such as ``/path/with/plenty/of/disk`` — that is not a real folder.

::

  python scripts/generate_validation_data.py --source-rows 5000 --missing 200 --extra 50 --value-mismatch-uids 300 --out-dir test-data/generated

  python scripts/generate_validation_data.py --source-rows 100000000 --missing 1000000 --extra 500000 --value-mismatch-uids 2000000 --out-dir ./test-data/generated-100m
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Paths that look like documentation placeholders (not real on most machines).
_OUT_DIR_PLACEHOLDER_FRAGMENTS = (
    "with/plenty/of",
    "/path/with/plenty",
)


def _out_dir_looks_like_doc_placeholder(out: Path) -> bool:
    normalized = str(out.expanduser()).replace("\\", "/")
    return any(fragment in normalized for fragment in _OUT_DIR_PLACEHOLDER_FRAGMENTS)


@dataclass(frozen=True)
class ExpectedManifest:
    """Ground-truth counts you should see from Pegasus for this pair."""

    uid_column: str
    delimiter: str
    source_rows: int
    target_rows: int
    compared_columns: list[str]
    missing_in_target: int
    extra_in_target: int
    value_mismatch_records: int
    total_mismatch_records: int
    value_mismatch_columns_per_uid: int
    value_mismatch_uids: int
    notes: str


_REGIONS = ("EMEA", "APAC", "AMER", "LATAM", "MEA")


def source_cells(uid: int) -> tuple[str, str, str, str]:
    sku = f"SKU-{uid:012d}"
    amount = str(1_000_000 + (uid * 1_000_003) % 899_000_000)
    region = _REGIONS[uid % 5]
    return str(uid), sku, amount, region


def join_delim(d: str) -> str:
    return d


def write_source_stream(
    path: Path,
    *,
    n: int,
    delim: str,
    uid_key: str,
    chunk_size: int,
) -> None:
    cols = [uid_key, "sku", "amount", "region"]
    line_ending = "\n"
    sep = join_delim(delim)
    header = sep.join(cols) + line_ending
    path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    with path.open("w", encoding="utf-8", buffering=1024 * 1024) as f:
        f.write(header)
        for uid in range(1, n + 1):
            uid_s, sku, amount, region = source_cells(uid)
            f.write(sep.join([uid_s, sku, amount, region]) + line_ending)
            if uid % chunk_size == 0:
                dt = time.perf_counter() - t0
                rate = uid / max(dt, 1e-9)
                print(f"  source: wrote {uid:,} rows ({rate:,.0f} rows/s)", file=sys.stderr)
    print(f"  source: done {n:,} rows in {time.perf_counter() - t0:.1f}s", file=sys.stderr)


def write_target_stream(
    path: Path,
    *,
    n_source: int,
    missing: int,
    extra: int,
    value_uids: int,
    value_cols: int,
    delim: str,
    uid_key: str,
    chunk_size: int,
    rng: random.Random,
    target_order: str,
    shuffle_max_ids: int,
) -> None:
    """
    Overlap UIDs: ``1 .. (n_source - missing)``.
    First ``value_uids`` of those get wrong ``amount`` (and next columns if value_cols>1).
    Extra UIDs: ``n_source + 1 .. n_source + extra``.
    """
    overlap = n_source - missing
    if overlap < 0:
        raise ValueError("missing cannot exceed source_rows")
    if value_uids > overlap:
        raise ValueError(f"value_mismatch_uids={value_uids} exceeds overlap uids={overlap}")
    if value_cols < 1 or value_cols > 3:
        raise ValueError("value_mismatch_columns must be 1..3 (sku, amount, region)")

    cols = [uid_key, "sku", "amount", "region"]
    sep = join_delim(delim)
    header = sep.join(cols) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)

    def target_row_for_uid(uid: int) -> tuple[str, str, str, str]:
        uid_s, sku, amount, region = source_cells(uid)
        if 1 <= uid <= value_uids:
            if value_cols >= 1:
                amount = str(int(amount) + 9_999_999)  # guaranteed diff vs source
            if value_cols >= 2:
                sku = sku + "_WRONG"
            if value_cols >= 3:
                region = _REGIONS[(uid + 2) % 5]
        return uid_s, sku, amount, region

    def extra_row(uid: int) -> tuple[str, str, str, str]:
        return (
            str(uid),
            f"XTRA-{uid:012d}",
            str(500_000 + uid % 10_000),
            "EXTRA",
        )

    def overlap_uid_sequence() -> list[int] | range:
        """Yield order for overlap UIDs without O(N) memory when possible."""
        if target_order == "sorted":
            return range(1, overlap + 1)
        if target_order == "reversed":
            return range(overlap, 0, -1)
        if target_order == "shuffled":
            if overlap > shuffle_max_ids:
                print(
                    f"warning: overlap={overlap:,} > --shuffle-max-ids={shuffle_max_ids:,}; "
                    "using 'reversed' emission order to avoid O(N) memory",
                    file=sys.stderr,
                )
                return range(overlap, 0, -1)
            ids = list(range(1, overlap + 1))
            rng.shuffle(ids)
            return ids
        raise ValueError(f"unknown target_order={target_order!r}")

    def extra_uid_sequence() -> list[int] | range:
        if target_order != "shuffled" or extra > shuffle_max_ids:
            return range(n_source + 1, n_source + extra + 1)
        ids = list(range(n_source + 1, n_source + extra + 1))
        rng.shuffle(ids)
        return ids

    overlap_seq = overlap_uid_sequence()
    extra_seq = extra_uid_sequence()

    t0 = time.perf_counter()
    written = 0
    with path.open("w", encoding="utf-8", buffering=1024 * 1024) as f:
        f.write(header)
        for uid in overlap_seq:
            f.write(sep.join(target_row_for_uid(uid)) + "\n")
            written += 1
            if written % chunk_size == 0:
                dt = time.perf_counter() - t0
                print(f"  target: wrote {written:,} rows ({written/max(dt,1e-9):,.0f} rows/s)", file=sys.stderr)
        for uid in extra_seq:
            f.write(sep.join(extra_row(uid)) + "\n")
            written += 1
            if written % chunk_size == 0:
                dt = time.perf_counter() - t0
                print(f"  target: wrote {written:,} rows ({written/max(dt,1e-9):,.0f} rows/s)", file=sys.stderr)

    print(f"  target: done {written:,} rows in {time.perf_counter() - t0:.1f}s", file=sys.stderr)


def build_manifest(
    *,
    uid_column: str,
    delim: str,
    n_source: int,
    missing: int,
    extra: int,
    value_uids: int,
    value_cols: int,
    target_order: str,
) -> ExpectedManifest:
    overlap = n_source - missing
    vm_records = value_uids * value_cols
    total = missing + extra + vm_records
    target_rows = overlap + extra
    notes = (
        "Compare on UID only; row order in the files is unrelated. "
        f"Target overlap UID emission order: {target_order!r}."
    )
    return ExpectedManifest(
        uid_column=uid_column,
        delimiter=delim,
        source_rows=n_source,
        target_rows=target_rows,
        compared_columns=["sku", "amount", "region"],
        missing_in_target=missing,
        extra_in_target=extra,
        value_mismatch_records=vm_records,
        total_mismatch_records=total,
        value_mismatch_columns_per_uid=value_cols,
        value_mismatch_uids=value_uids,
        notes=notes,
    )


def main() -> int:
    epilog = (
        "Copy-paste check: flags look like --out-dir and --source-rows (no space after --).\n"
        "Dry run (no files written): add --dry-run and you may omit --out-dir."
    )
    p = argparse.ArgumentParser(
        description=__doc__,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--source-rows", type=int, required=True, help="Number of rows in source (UIDs 1..N)")
    p.add_argument("--missing", type=int, default=0, help="UIDs only in source (removed from target tail)")
    p.add_argument("--extra", type=int, default=0, help="UIDs only in target (after last source UID)")
    p.add_argument(
        "--value-mismatch-uids",
        type=int,
        default=0,
        help="Among overlap UIDs 1..(N-missing), how many leading UIDs get wrong cells in target",
    )
    p.add_argument(
        "--value-mismatch-columns",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="How many compared columns differ per mismatched UID (1=amount, +sku, +region)",
    )
    p.add_argument("--delimiter", type=str, default="||", help="Field separator written into CSVs")
    p.add_argument("--uid-column", type=str, default="id", help="Column name in both files (join key)")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for source.csv, target.csv, manifest.json (required unless --dry-run)",
    )
    p.add_argument("--seed", type=int, default=42, help="RNG seed (for reproducible sku/region and shuffled order)")
    p.add_argument(
        "--target-order",
        choices=["sorted", "reversed", "shuffled"],
        default="reversed",
        help="Order of overlap UID rows in target CSV (proves row index ≠ join)",
    )
    p.add_argument(
        "--chunk-log-interval",
        type=int,
        default=5_000_000,
        help="Print progress every this many rows (stderr)",
    )
    p.add_argument(
        "--shuffle-max-ids",
        type=int,
        default=2_000_000,
        help="Max overlap/extra IDs kept in RAM for --target-order shuffled; larger sets fall back to reversed",
    )
    p.add_argument("--dry-run", action="store_true", help="Print manifest only; do not write files")
    args = p.parse_args()
    if not args.dry_run and args.out_dir is None:
        p.error("--out-dir is required unless --dry-run")

    rng = random.Random(args.seed)
    n = args.source_rows
    if n < 1:
        p.error("--source-rows must be >= 1")

    if args.missing + args.extra + args.value_mismatch_uids == 0:
        print("warning: all mismatch knobs are zero — files will be identical on overlap", file=sys.stderr)

    manifest = build_manifest(
        uid_column=args.uid_column,
        delim=args.delimiter,
        n_source=n,
        missing=args.missing,
        extra=args.extra,
        value_uids=args.value_mismatch_uids,
        value_cols=args.value_mismatch_columns,
        target_order=args.target_order,
    )

    print("Expected validation summary (POST /api/v1/validate):", file=sys.stderr)
    print(json.dumps(asdict(manifest), indent=2), file=sys.stderr)

    if args.dry_run:
        print(json.dumps(asdict(manifest), indent=2))
        return 0

    out = args.out_dir.expanduser().resolve()
    if _out_dir_looks_like_doc_placeholder(out):
        print(
            f"Refusing --out-dir={args.out_dir!r}: it looks like a documentation placeholder, "
            "not a real directory on your computer.\n"
            "Use something you can create and write to, for example:\n"
            "  --out-dir ./test-data/generated-100m\n"
            "  --out-dir ~/pegasus-bench\n"
            "  --out-dir /mnt/fastssd/pegasus_csv",
            file=sys.stderr,
        )
        return 1
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"Cannot create output directory {out}: {exc}\n"
            "Pick a path under your home directory or project (e.g. ./test-data/generated) "
            "that exists or that your user may create.",
            file=sys.stderr,
        )
        return 1
    src_path = out / "source.csv"
    tgt_path = out / "target.csv"
    man_path = out / "manifest.json"

    print(f"Writing {src_path} …", file=sys.stderr)
    write_source_stream(
        src_path,
        n=n,
        delim=args.delimiter,
        uid_key=args.uid_column,
        chunk_size=args.chunk_log_interval,
    )
    print(f"Writing {tgt_path} …", file=sys.stderr)
    write_target_stream(
        tgt_path,
        n_source=n,
        missing=args.missing,
        extra=args.extra,
        value_uids=args.value_mismatch_uids,
        value_cols=args.value_mismatch_columns,
        delim=args.delimiter,
        uid_key=args.uid_column,
        chunk_size=args.chunk_log_interval,
        rng=rng,
        target_order=args.target_order,
        shuffle_max_ids=args.shuffle_max_ids,
    )

    payload = asdict(manifest)
    payload["files"] = {"source": str(src_path), "target": str(tgt_path)}
    man_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {man_path}", file=sys.stderr)

    # Rough size hint
    for label, path in ("source", src_path), ("target", tgt_path):
        sz = path.stat().st_size
        print(f"  {label}: {sz / (1024**2):,.1f} MiB on disk", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

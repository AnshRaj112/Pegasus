#!/usr/bin/env python3
"""
Generate paired source/target CSVs for Pegasus UID-based validation.
Features an interactive setup with emoji delimiter support and 
generates multi-lingual mock data (Chinese, Japanese, Hindi, Arabic, etc.).
"""

from __future__ import annotations

import json
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# --- Multi-Language UI Strings (for the console prompts) ---
UI = {
    "en": {
        "lang_name": "English",
        "source_rows": "Number of rows in source",
        "missing": "UIDs only in source (removed from target)",
        "extra": "UIDs only in target (extra rows)",
        "columns": "Total columns per file",
        "mismatches": "Overlap UIDs with mismatched values in target",
        "value_uids": "How many overlap UIDs get wrong cells in target",
        "value_cols": "How many compared columns differ per mismatched UID",
        "delimiter": "Field separator (can be an emoji like 🚀, or standard like ||)",
        "uid_column": "Column name for UID (join key)",
        "out_dir": "Output directory path (e.g., ./test-data)",
        "target_order": "Target UID order (sorted/reversed/shuffled)",
        "err_empty": "Input cannot be empty.",
        "err_int": "Please enter a valid integer.",
        "err_min": "Value must be at least {min_val}.",
        "err_max": "Value must be at most {max_val}.",
        "err_choices": "Please choose one of: {choices}.",
        "prog_src_write": "  source: wrote {count:,} rows ({rate:,.0f} rows/s)",
        "prog_src_done": "  source: done {count:,} rows in {time:.1f}s",
        "prog_tgt_write": "  target: wrote {count:,} rows ({rate:,.0f} rows/s)",
        "prog_tgt_done": "  target: done {count:,} rows in {time:.1f}s",
        "summary": "Expected validation summary:",
        "writing": "Writing {path} …",
        "done": "Done! Manifest written to {path}"
    }
}

# --- Multi-Language Data Dictionaries (for the CSV content) ---
_REGIONS = (
    "North America",    # English
    "América Latina",   # Spanish
    "欧洲",             # Chinese (Europe)
    "東アジア",         # Japanese (East Asia)
    "दक्षिण एशिया",     # Hindi (South Asia)
    "أفريقيا"           # Arabic (Africa)
)

_ATTR_PREFIXES = ("VAL", "Valor", "值", "値", "मान", "قيمة")
_WRONG_SUFFIXES = ("_WRONG", "_INCORRECTO", "_错误", "_エラー", "_गलत", "_خطأ")
_EXTRA_PREFIXES = ("XTRA", "EXTRA", "额外", "追加", "अतिरिक्त", "إضافي")

def get_input(prompt_key: str, default=None, is_int=False, min_val=None, max_val=None, choices=None):
    """Handles interactive prompts with validation."""
    prompt_text = UI["en"][prompt_key]
    if default is not None:
        prompt_text += f" [{default}]: "
    else:
        prompt_text += ": "

    while True:
        val = input(prompt_text).strip()
        if not val and default is not None:
            val = str(default)
        if not val and default is None:
            print(UI["en"]["err_empty"])
            continue

        if is_int:
            try:
                val = int(val)
                if min_val is not None and val < min_val:
                    print(UI["en"]["err_min"].format(min_val=min_val))
                    continue
                if max_val is not None and val > max_val:
                    print(UI["en"]["err_max"].format(max_val=max_val))
                    continue
                return val
            except ValueError:
                print(UI["en"]["err_int"])
                continue
                
        if choices and val not in choices:
            print(UI["en"]["err_choices"].format(choices="/".join(choices)))
            continue

        return val

@dataclass(frozen=True)
class ExpectedManifest:
    uid_column: str
    delimiter: str
    column_count: int
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

def _column_names(column_count: int) -> list[str]:
    names = ["sku", "amount", "region"]
    if column_count > 4:
        names.extend(f"attr{i}" for i in range(4, column_count))
    return names[: column_count - 1]

def source_cells(uid: int, column_count: int) -> list[str]:
    sku = f"SKU-{uid:012d}"
    amount = str(1_000_000 + (uid * 1_000_003) % 899_000_000)
    
    # Pick a region dynamically in different languages
    region = _REGIONS[uid % len(_REGIONS)]
    row = [sku, amount, region]
    
    if column_count > 4:
        # Pick an attribute prefix in different languages
        prefix = _ATTR_PREFIXES[uid % len(_ATTR_PREFIXES)]
        row.extend(f"{prefix}-{i}-{uid:012d}" for i in range(4, column_count))
        
    return [str(uid), *row[: column_count - 1]]

def write_source_stream(path: Path, *, n: int, column_count: int, delim: str, uid_key: str, chunk_size: int) -> None:
    cols = [uid_key, *_column_names(column_count)]
    line_ending = "\n"
    header = delim.join(cols) + line_ending
    path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    
    # encoding="utf-8" guarantees Chinese/Japanese/Arabic etc. writes safely
    with path.open("w", encoding="utf-8", buffering=1024 * 1024) as f:
        f.write(header)
        for uid in range(1, n + 1):
            f.write(delim.join(source_cells(uid, column_count)) + line_ending)
            if uid % chunk_size == 0:
                dt = time.perf_counter() - t0
                rate = uid / max(dt, 1e-9)
                print(UI["en"]["prog_src_write"].format(count=uid, rate=rate), file=sys.stderr)
    
    total_time = time.perf_counter() - t0
    print(UI["en"]["prog_src_done"].format(count=n, time=total_time), file=sys.stderr)

def write_target_stream(path: Path, *, n_source: int, missing: int, extra: int, value_uids: int, value_cols: int, column_count: int, delim: str, uid_key: str, chunk_size: int, target_order: str) -> None:
    overlap = n_source - missing
    cols = [uid_key, *_column_names(column_count)]
    header = delim.join(cols) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    def target_row_for_uid(uid: int) -> list[str]:
        row = source_cells(uid, column_count)
        if 1 <= uid <= value_uids:
            # Pick an error suffix in different languages
            suffix = _WRONG_SUFFIXES[uid % len(_WRONG_SUFFIXES)]
            for idx in range(1, min(column_count, value_cols + 1)):
                if idx == 1:
                    row[idx] = row[idx] + suffix
                elif idx == 2:
                    row[idx] = str(int(row[idx]) + 9_999_999) 
                elif idx == 3:
                    row[idx] = _REGIONS[(uid + 2) % len(_REGIONS)]
                else:
                    row[idx] = row[idx] + suffix
        return row

    def extra_row(uid: int) -> list[str]:
        # Pick an "extra" indicator in different languages
        prefix = _EXTRA_PREFIXES[uid % len(_EXTRA_PREFIXES)]
        row = [str(uid), f"{prefix}-{uid:012d}", str(500_000 + uid % 10_000), f"{prefix}-REG"]
        if column_count > 4:
            row.extend(f"{prefix}-{i}-{uid:012d}" for i in range(4, column_count))
        return row[:column_count]

    overlap_seq = list(range(1, overlap + 1))
    if target_order == "reversed":
        overlap_seq.reverse()
    elif target_order == "shuffled":
        rng.shuffle(overlap_seq)

    extra_seq = list(range(n_source + 1, n_source + extra + 1))
    if target_order == "shuffled":
        rng.shuffle(extra_seq)

    t0 = time.perf_counter()
    written = 0
    with path.open("w", encoding="utf-8", buffering=1024 * 1024) as f:
        f.write(header)
        for uid in overlap_seq:
            f.write(delim.join(target_row_for_uid(uid)) + "\n")
            written += 1
            if written % chunk_size == 0:
                dt = time.perf_counter() - t0
                print(UI["en"]["prog_tgt_write"].format(count=written, rate=written/max(dt,1e-9)), file=sys.stderr)
        
        for uid in extra_seq:
            f.write(delim.join(extra_row(uid)) + "\n")
            written += 1
            if written % chunk_size == 0:
                dt = time.perf_counter() - t0
                print(UI["en"]["prog_tgt_write"].format(count=written, rate=written/max(dt,1e-9)), file=sys.stderr)

    print(UI["en"]["prog_tgt_done"].format(count=written, time=time.perf_counter() - t0), file=sys.stderr)

def main() -> int:
    print("--- Multilingual Mock Data Generator ---")
    n = get_input("source_rows", default=1000, is_int=True, min_val=1)
    missing = get_input("missing", default=0, is_int=True, min_val=0, max_val=n)
    extra = get_input("extra", default=0, is_int=True, min_val=0)
    columns = get_input("columns", default=5, is_int=True, min_val=2)

    max_overlap = n - missing
    mismatches = get_input("mismatches", default=0, is_int=True, min_val=0, max_val=max_overlap)
    value_uids = mismatches
    value_cols = 1
    
    delimiter = get_input("delimiter", default="🚀")
    uid_column = get_input("uid_column", default="id")
    target_order = get_input("target_order", default="reversed", choices=["sorted", "reversed", "shuffled"])
    out_dir_str = get_input("out_dir", default="./test-data/generated")
    
    print("-" * 40 + "\n")

    manifest = ExpectedManifest(
        uid_column=uid_column,
        delimiter=delimiter,
        column_count=columns,
        source_rows=n,
        target_rows=(n - missing) + extra,
        compared_columns=_column_names(columns),
        missing_in_target=missing,
        extra_in_target=extra,
        value_mismatch_records=value_uids * value_cols,
        total_mismatch_records=missing + extra + (value_uids * value_cols),
        value_mismatch_columns_per_uid=value_cols,
        value_mismatch_uids=value_uids,
        notes=f"Compare on UID only. Target overlap UID emission order: {target_order!r}."
    )

    print(UI["en"]["summary"])
    print(json.dumps(asdict(manifest), indent=2), file=sys.stderr)
    print("\n")

    out = Path(out_dir_str).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    
    src_path = out / "source.csv"
    tgt_path = out / "target.csv"
    man_path = out / "manifest.json"

    print(UI["en"]["writing"].format(path=src_path), file=sys.stderr)
    write_source_stream(src_path, n=n, column_count=columns, delim=delimiter, uid_key=uid_column, chunk_size=5_000_000)
    
    print(UI["en"]["writing"].format(path=tgt_path), file=sys.stderr)
    write_target_stream(tgt_path, n_source=n, missing=missing, extra=extra, value_uids=value_uids, value_cols=value_cols, column_count=columns, delim=delimiter, uid_key=uid_column, chunk_size=5_000_000, target_order=target_order)

    payload = asdict(manifest)
    payload["files"] = {"source": str(src_path), "target": str(tgt_path)}
    man_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    
    print("\n" + UI["en"]["done"].format(path=man_path))

    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nProcess cancelled.")
        sys.exit(1)
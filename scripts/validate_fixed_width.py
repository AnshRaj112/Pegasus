#!/usr/bin/env python3
"""
High-Performance Streaming Validation Script for Large Fixed-Width Files (100GB+).
Validates date fields using user-defined slices and formats, without holding 
entire files in memory.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from itertools import zip_longest
from pathlib import Path


def load_config(config_path: str) -> dict:
    """Loads and validates the configuration JSON file."""
    path = Path(config_path)
    if not path.is_file():
        print(f"Error: Configuration file '{config_path}' not found.", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse configuration JSON: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Basic validation of config keys
    required_sections = ["source", "target", "validation"]
    for sec in required_sections:
        if sec not in config:
            print(f"Error: Missing section '{sec}' in configuration.", file=sys.stderr)
            sys.exit(1)
            
    # Validate structure
    for key in ["file_path", "date_field"]:
        if key not in config["source"]:
            print(f"Error: Missing '{key}' in 'source' section of config.", file=sys.stderr)
            sys.exit(1)
        if key not in config["target"]:
            print(f"Error: Missing '{key}' in 'target' section of config.", file=sys.stderr)
            sys.exit(1)
            
    for key in ["start", "end", "format"]:
        if key not in config["source"]["date_field"]:
            print(f"Error: Missing '{key}' in source 'date_field'.", file=sys.stderr)
            sys.exit(1)
        if key not in config["target"]["date_field"]:
            print(f"Error: Missing '{key}' in target 'date_field'.", file=sys.stderr)
            sys.exit(1)
            
    return config


def parse_date(date_str: str, date_format: str) -> datetime.date:
    """Parses a string into a datetime.date object, raising ValueError if invalid."""
    try:
        from pegasus.validation.fixed_width_dates import parse_fixed_width_date

        return parse_fixed_width_date(date_str, date_format)
    except ImportError:
        clean_str = date_str.strip()
        return datetime.strptime(clean_str, date_format).date()


def validate_files(config: dict) -> None:
    """Streams both files, performs validation, and logs mismatches."""
    source_cfg = config["source"]
    target_cfg = config["target"]
    val_cfg = config["validation"]
    
    src_path = Path(source_cfg["file_path"])
    tgt_path = Path(target_cfg["file_path"])
    log_path = Path(val_cfg.get("mismatch_log_path", "mismatches.log"))
    report_interval = val_cfg.get("report_interval_rows", 1_000_000)
    
    # Configure slicing
    src_start = source_cfg["date_field"]["start"]
    src_end = source_cfg["date_field"]["end"]
    src_format = source_cfg["date_field"]["format"]
    
    tgt_start = target_cfg["date_field"]["start"]
    tgt_end = target_cfg["date_field"]["end"]
    tgt_format = target_cfg["date_field"]["format"]
    
    # Counters
    total_rows = 0
    mismatches = 0
    parse_errors = 0
    missing_in_target = 0
    missing_in_source = 0
    
    # Large 16MB buffer for optimal sequential disk reads on massive 100GB files
    buffer_size = 16 * 1024 * 1024 
    
    t0 = time.perf_counter()
    
    print(f"Starting validation...")
    print(f"Source file: {src_path}")
    print(f"Target file: {tgt_path}")
    print(f"Output mismatch log: {log_path}\n")
    
    # Open all three file handles inside context managers
    with open(src_path, 'r', encoding='utf-8', buffering=buffer_size) as src_file, \
         open(tgt_path, 'r', encoding='utf-8', buffering=buffer_size) as tgt_file, \
         open(log_path, 'w', encoding='utf-8') as log_file:
             
        log_file.write(f"# Fixed-Width Validation Mismatch Log\n")
        log_file.write(f"# Source: {src_path}\n")
        log_file.write(f"# Target: {tgt_path}\n")
        log_file.write(f"# Generated: {datetime.now().isoformat()}\n")
        log_file.write(f"# Format: Line_Number | Mismatch_Type | Details\n")
        log_file.write("-" * 80 + "\n")
        
        # Use zip_longest to handle cases where one file is shorter than the other
        for line_idx, (src_line, tgt_line) in enumerate(zip_longest(src_file, tgt_file), start=1):
            total_rows += 1
            
            # Case 1: Source has extra rows
            if src_line is not None and tgt_line is None:
                mismatches += 1
                missing_in_target += 1
                log_file.write(
                    f"{line_idx} | Missing in Target | Target file reached EOF early. "
                    f"Source raw value: {src_line.rstrip()!r}\n"
                )
                continue
                
            # Case 2: Target has extra rows
            if src_line is None and tgt_line is not None:
                mismatches += 1
                missing_in_source += 1
                log_file.write(
                    f"{line_idx} | Missing in Source | Source file reached EOF early. "
                    f"Target raw value: {tgt_line.rstrip()!r}\n"
                )
                continue
                
            # Extract fields
            src_raw_date = src_line[src_start:src_end]
            tgt_raw_date = tgt_line[tgt_start:tgt_end]
            
            src_date = None
            tgt_date = None
            parse_failed = False
            
            # Parse source date
            try:
                src_date = parse_date(src_raw_date, src_format)
            except ValueError as e:
                parse_failed = True
                parse_errors += 1
                log_file.write(
                    f"{line_idx} | Source Parse Error | Value {src_raw_date!r} "
                    f"could not be parsed with format '{src_format}'. Error: {e}\n"
                )
                
            # Parse target date
            try:
                tgt_date = parse_date(tgt_raw_date, tgt_format)
            except ValueError as e:
                parse_failed = True
                parse_errors += 1
                log_file.write(
                    f"{line_idx} | Target Parse Error | Value {tgt_raw_date!r} "
                    f"could not be parsed with format '{tgt_format}'. Error: {e}\n"
                )
                
            # If parsing succeeded for both, compare dates
            if not parse_failed:
                if src_date != tgt_date:
                    mismatches += 1
                    log_file.write(
                        f"{line_idx} | Value Mismatch | "
                        f"Source raw: {src_raw_date!r} (parsed: {src_date}) vs "
                        f"Target raw: {tgt_raw_date!r} (parsed: {tgt_date})\n"
                    )
            else:
                # If parsing failed on either, we consider it a structural mismatch/conflict
                mismatches += 1
                
            # Periodic logging for large runs
            if line_idx % report_interval == 0:
                elapsed = time.perf_counter() - t0
                rate = line_idx / elapsed
                print(f"Processed {line_idx:,} lines... "
                      f"Mismatches: {mismatches:,} | "
                      f"Errors: {parse_errors:,} | "
                      f"Speed: {rate:,.0f} lines/sec")
                
    elapsed_total = time.perf_counter() - t0
    avg_rate = total_rows / max(elapsed_total, 1e-9)
    
    # Validation summary report
    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Total Rows Processed:      {total_rows:,}")
    print(f"Total Row Conflicts/Diffs: {mismatches:,}")
    print(f"  - Value Mismatches:      {mismatches - parse_errors - missing_in_target - missing_in_source:,}")
    print(f"  - Date Parsing Errors:   {parse_errors:,}")
    print(f"  - Missing in Target:     {missing_in_target:,}")
    print(f"  - Missing in Source:     {missing_in_source:,}")
    print(f"Status:                    {'FAILED' if mismatches > 0 else 'PASSED'}")
    print(f"Mismatch Log Written to:   {log_path.resolve()}")
    print("-" * 50)
    print(f"Execution Time:            {elapsed_total:.2f} seconds")
    print(f"Average Throughput:        {avg_rate:,.0f} lines/sec")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream and validate two massive fixed-width files on date fields."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to JSON configuration file (default: config.json)"
    )
    args = parser.parse_args()
    
    config = load_config(args.config)
    validate_files(config)


if __name__ == "__main__":
    main()

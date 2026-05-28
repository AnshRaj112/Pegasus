#!/usr/bin/env python3
"""
Generate CSV and fixed-width fixtures to exercise structured cell comparison.

Creates paired source/target files under test-data/structured-compare/ with a
manifest of expected mismatch counts. Optionally runs in-process validation.

Usage:
  python scripts/generate_structured_validation_data.py
  python scripts/generate_structured_validation_data.py --verify
  python scripts/generate_structured_validation_data.py --out-dir ./my-fixtures
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "test-data" / "structured-compare"

CSV_COLUMNS = ("id", "label", "tags", "metadata", "notes")

# Comma delimiter with RFC 4180 quoting (commas inside JSON/list cells are quoted).
CSV_DELIMITER = ","


@dataclass(frozen=True)
class RowSpec:
    """One logical test row (source and target cell values)."""

    row_id: str
    label: str
    source_tags: str
    target_tags: str
    source_metadata: str
    target_metadata: str
    source_notes: str
    target_notes: str
    expect: str  # match | value_mismatch | missing_in_target | extra_in_target


def _scenario_rows() -> list[RowSpec]:
    """Curated cases for auto structured compare (order ignored) vs real mismatches."""
    return [
        RowSpec(
            "1",
            "list_reordered",
            '["a", "b", "c"]',
            '["c", "b", "a"]',
            '{"k": 1}',
            '{"k": 1}',
            "auto: list order ignored",
            "auto: list order ignored",
            "match",
        ),
        RowSpec(
            "2",
            "dict_reordered",
            '{"x": 1, "y": 2}',
            '{"y": 2, "x": 1}',
            "{}",
            "{}",
            "auto: dict key order ignored",
            "auto: dict key order ignored",
            "match",
        ),
        RowSpec(
            "3",
            "tuple_python_literal",
            "(1, 2, 3)",
            "(3, 2, 1)",
            "[]",
            "[]",
            "auto: tuple vs reordered tuple",
            "auto: tuple vs reordered tuple",
            "match",
        ),
        RowSpec(
            "4",
            "spelling_mismatch",
            '["alpha", "beta"]',
            '["alpha", "gamma"]',
            '{"ok": true}',
            '{"ok": true}',
            "should mismatch (tags)",
            "should mismatch (tags)",
            "value_mismatch",
        ),
        RowSpec(
            "5",
            "nested_json",
            '{"items": [1, 2, 3], "name": "pkg"}',
            '{"name": "pkg", "items": [3, 2, 1]}',
            "",
            "",
            "nested list reorder",
            "nested list reorder",
            "match",
        ),
        RowSpec(
            "6",
            "plain_text_equal",
            "[]",
            "[]",
            "",
            "",
            "same plain note",
            "same plain note",
            "match",
        ),
        RowSpec(
            "7",
            "plain_text_diff",
            "[]",
            "[]",
            "",
            "",
            "hello world",
            "hello mars",
            "value_mismatch",
        ),
        RowSpec(
            "8",
            "metadata_list_reorder",
            "[10, 20, 30]",
            "[30, 10, 20]",
            '{"tags": ["z", "y", "x"]}',
            '{"tags": ["x", "y", "z"]}',
            "both structured cols match",
            "both structured cols match",
            "match",
        ),
        RowSpec(
            "9",
            "only_in_source",
            '["only", "source"]',
            "",
            '{"side": "source"}',
            "",
            "missing in target file",
            "",
            "missing_in_target",
        ),
        RowSpec(
            "10",
            "only_in_target",
            "",
            '["only", "target"]',
            "",
            '{"side": "target"}',
            "",
            "extra in target file",
            "extra_in_target",
        ),
        RowSpec(
            "11",
            "metadata_value_diff",
            "[]",
            "[]",
            '{"count": 5}',
            '{"count": 6}',
            "numeric field inside dict",
            "numeric field inside dict",
            "value_mismatch",
        ),
        RowSpec(
            "12",
            "python_single_quoted_dict",
            "{'id': 99, 'active': True}",
            "{'active': True, 'id': 99}",
            "",
            "",
            "Python literal dict",
            "Python literal dict",
            "match",
        ),
    ]


def _write_csv(path: Path, rows: list[dict[str, str]], *, header: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(CSV_COLUMNS),
            delimiter=CSV_DELIMITER,
            quoting=csv.QUOTE_MINIMAL,
        )
        if header:
            writer.writeheader()
        writer.writerows(rows)


def _csv_rows_from_specs(specs: list[RowSpec], *, side: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for spec in specs:
        if side == "source":
            if spec.expect == "extra_in_target":
                continue
            tags, metadata, notes = spec.source_tags, spec.source_metadata, spec.source_notes
        else:
            if spec.expect == "missing_in_target":
                continue
            tags, metadata, notes = spec.target_tags, spec.target_metadata, spec.target_notes
        out.append({
            "id": spec.row_id,
            "label": spec.label,
            "tags": tags,
            "metadata": metadata,
            "notes": notes,
        })
    return out


def _pad_field(value: str, width: int) -> str:
    text = value[:width]
    return text + (" " * (width - len(text)))


def _fixed_width_line(
    row_id: str,
    tags: str,
    metadata: str,
    *,
    id_width: int = 4,
    tags_width: int = 56,
    meta_width: int = 40,
) -> str:
    return (
        _pad_field(row_id, id_width)
        + _pad_field(tags, tags_width)
        + _pad_field(metadata, meta_width)
    )


def _write_fixed_width(
    path: Path,
    specs: list[RowSpec],
    *,
    side: str,
    id_width: int = 4,
    tags_width: int = 56,
    meta_width: int = 40,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for spec in specs:
        if side == "source":
            if spec.expect == "extra_in_target":
                continue
            line = _fixed_width_line(
                spec.row_id,
                spec.source_tags,
                spec.source_metadata,
                id_width=id_width,
                tags_width=tags_width,
                meta_width=meta_width,
            )
        else:
            if spec.expect == "missing_in_target":
                continue
            line = _fixed_width_line(
                spec.row_id,
                spec.target_tags,
                spec.target_metadata,
                id_width=id_width,
                tags_width=tags_width,
                meta_width=meta_width,
            )
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fixed_width_config(*, id_width: int, tags_width: int, meta_width: int) -> dict[str, Any]:
    tags_start = id_width
    tags_end = tags_start + tags_width
    meta_start = tags_end
    meta_end = meta_start + meta_width
    return {
        "uid_column": "record_id",
        "fields": [
            {
                "field_name": "record_id",
                "source_start": 0,
                "source_end": id_width,
                "target_start": 0,
                "target_end": id_width,
                "field_type": "text",
            },
            {
                "field_name": "tags",
                "source_start": tags_start,
                "source_end": tags_end,
                "target_start": tags_start,
                "target_end": tags_end,
                "field_type": "structured",
                "structured_order_sensitive": False,
            },
            {
                "field_name": "metadata",
                "source_start": meta_start,
                "source_end": meta_end,
                "target_start": meta_start,
                "target_end": meta_end,
                "field_type": "text",
            },
        ],
        "match_strategy": "exact",
    }


def _expected_summary(specs: list[RowSpec]) -> dict[str, int]:
    return {
        "missing_in_target": sum(1 for s in specs if s.expect == "missing_in_target"),
        "extra_in_target": sum(1 for s in specs if s.expect == "extra_in_target"),
        "value_mismatch": sum(1 for s in specs if s.expect == "value_mismatch"),
        "matching_rows": sum(1 for s in specs if s.expect == "match"),
    }


def _write_readme(out_dir: Path, manifest: dict[str, Any]) -> None:
    readme = out_dir / "README.md"
    readme.write_text(
        f"""# Structured compare test fixtures

Generated by `scripts/generate_structured_validation_data.py`.

## CSV (`csv/`)

| File | Role |
|------|------|
| `source.csv` | Source rows with list/dict/tuple literals in `tags` and `metadata` |
| `target.csv` | Target rows — mostly same data with **reordered** structured strings |

### Pegasus UI / API settings

- **Join key (UID):** `id`
- **Delimiter:** `,` (comma) or `auto` (quoted JSON/list cells are parsed correctly)
- **Header row:** yes (first row is column names)
- **Column mappings:** map `tags`, `metadata`, and `notes` (leave compare mode **Default (auto)**)

### Expected validation summary

```json
{json.dumps(manifest["expected_csv"], indent=2)}
```

Rows that should **match** despite different string order: ids `1`, `2`, `3`, `5`, `8`, `12`.
Rows that should **mismatch**: ids `4` (tags), `7` (notes), `11` (metadata).
Row `9` only in source; row `10` only in target.

## Fixed-width (`fixed-width/`)

| File | Role |
|------|------|
| `source.dat` / `target.dat` | Padded lines: id + tags slice + metadata slice |
| `config.json` | Pass as `fixed_width_config` in validate request |

Join key: `record_id` (field `record_id`). Field `tags` uses `field_type: structured`.

### Expected fixed-width summary

Same logical cases as CSV for shared ids (tags/metadata slices).

## Quick verify (no server)

```bash
python scripts/generate_structured_validation_data.py --verify
```

## Validate via API (server running)

```bash
curl -s -X POST http://localhost:8000/api/v1/validate/local \\
  -H 'Content-Type: application/json' \\
  -d @$(pwd)/test-data/structured-compare/validate_request.json
```

Then poll the returned `poll_url` until `status` is `completed`.

For strict element/key order checking, use:

```bash
curl -s -X POST http://localhost:8000/api/v1/validate/local \
  -H 'Content-Type: application/json' \
  -d @$(pwd)/test-data/structured-compare/validate_request_strict_order.json
```

""",
        encoding="utf-8",
    )


def _write_validate_request(out_dir: Path, manifest: dict[str, Any]) -> None:
    csv_dir = out_dir / "csv"
    payload_auto = {
        "source_path": str(csv_dir / "source.csv"),
        "target_path": str(csv_dir / "target.csv"),
        "uid_column": "id",
        "delimiter": CSV_DELIMITER,
        "has_header": True,
        "column_mappings": [
            {"source_column": "tags", "target_column": "tags"},
            {"source_column": "metadata", "target_column": "metadata"},
            {"source_column": "notes", "target_column": "notes"},
        ],
    }
    (out_dir / "validate_request.json").write_text(
        json.dumps(payload_auto, indent=2),
        encoding="utf-8",
    )
    payload_strict = {
        "source_path": str(csv_dir / "source.csv"),
        "target_path": str(csv_dir / "target.csv"),
        "uid_column": "id",
        "delimiter": CSV_DELIMITER,
        "has_header": True,
        "column_mappings": [
            {
                "source_column": "tags",
                "target_column": "tags",
                "compare_mode": "structured",
                "structured_order_sensitive": True,
            },
            {
                "source_column": "metadata",
                "target_column": "metadata",
                "compare_mode": "structured",
                "structured_order_sensitive": True,
            },
            {"source_column": "notes", "target_column": "notes"},
        ],
    }
    (out_dir / "validate_request_strict_order.json").write_text(
        json.dumps(payload_strict, indent=2),
        encoding="utf-8",
    )
    (out_dir / "validate_fixed_width_request.json").write_text(
        json.dumps(
            {
                "source_path": str(out_dir / "fixed-width" / "source.dat"),
                "target_path": str(out_dir / "fixed-width" / "target.dat"),
                "file_format": "fixed-width",
                "delimiter": "fixed-width",
                "uid_column": "record_id",
                "has_header": False,
                "column_mappings": [],
                "fixed_width_config": manifest["fixed_width_config"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def generate(out_dir: Path) -> dict[str, Any]:
    specs = _scenario_rows()
    csv_dir = out_dir / "csv"
    fw_dir = out_dir / "fixed-width"

    _write_csv(csv_dir / "source.csv", _csv_rows_from_specs(specs, side="source"))
    _write_csv(csv_dir / "target.csv", _csv_rows_from_specs(specs, side="target"))

    id_width, tags_width, meta_width = 4, 56, 40
    _write_fixed_width(
        fw_dir / "source.dat",
        specs,
        side="source",
        id_width=id_width,
        tags_width=tags_width,
        meta_width=meta_width,
    )
    _write_fixed_width(
        fw_dir / "target.dat",
        specs,
        side="target",
        id_width=id_width,
        tags_width=tags_width,
        meta_width=meta_width,
    )
    fw_config = _fixed_width_config(
        id_width=id_width,
        tags_width=tags_width,
        meta_width=meta_width,
    )
    (fw_dir / "config.json").write_text(json.dumps(fw_config, indent=2), encoding="utf-8")

    manifest: dict[str, Any] = {
        "description": "Structured literal comparison fixtures for CSV and fixed-width",
        "uid_column_csv": "id",
        "delimiter_csv": CSV_DELIMITER,
        "has_header_csv": True,
        "compared_columns_csv": ["tags", "metadata", "notes"],
        "expected_csv": _expected_summary(specs),
        "fixed_width_config": fw_config,
        "scenarios": [asdict(s) for s in specs],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_validate_request(out_dir, manifest)
    _write_readme(out_dir, manifest)
    return manifest


def verify(out_dir: Path, manifest: dict[str, Any]) -> int:
    """Run in-process validation and print results."""
    backend_src = REPO_ROOT / "pegasus-backend" / "src"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))

    from pegasus.core.config import get_settings
    from pegasus.schemas.validation import ColumnMapping
    from pegasus.services.validation_service import ValidationService

    get_settings.cache_clear()
    settings = get_settings()
    svc = ValidationService(settings)

    csv_dir = out_dir / "csv"
    mappings = [
        ColumnMapping(source_column="tags", target_column="tags"),
        ColumnMapping(source_column="metadata", target_column="metadata"),
        ColumnMapping(source_column="notes", target_column="notes"),
    ]
    print("Running CSV validation …")
    csv_result = svc._validate_csv_pair_sync(
        source_path=csv_dir / "source.csv",
        target_path=csv_dir / "target.csv",
        uid_column="id",
        delimiter=CSV_DELIMITER,
        column_mappings=mappings,
        has_header=True,
    )
    csv_summary = dict(csv_result.report.summary)
    expected = manifest["expected_csv"]
    print("  CSV summary:", csv_summary)
    print("  Expected:   ", expected)

    ok = True
    for key in ("missing_in_target", "extra_in_target", "value_mismatch"):
        if csv_summary.get(key, 0) != expected.get(key, 0):
            print(f"  FAIL: {key} got {csv_summary.get(key)!r}, want {expected.get(key)!r}")
            ok = False
        else:
            print(f"  OK:   {key} = {expected[key]}")

    fw_dir = out_dir / "fixed-width"
    print("\nRunning fixed-width validation …")
    fw_result = svc.validate_fixed_width_pair_sync(
        source_path=fw_dir / "source.dat",
        target_path=fw_dir / "target.dat",
        fixed_width_config=manifest["fixed_width_config"],
    )
    fw_summary = {
        "missing_in_target": fw_result.report.summary.get("missing_in_target", 0),
        "extra_in_target": fw_result.report.summary.get("extra_in_target", 0),
        "value_mismatch": fw_result.report.summary.get("value_mismatch", 0),
    }
    print("  Fixed-width summary:", fw_summary)
    # tags + metadata compared; notes omitted in FW layout
    fw_expected = {
        "missing_in_target": expected["missing_in_target"],
        "extra_in_target": expected["extra_in_target"],
        # value mismatches: id 4 tags, id 11 metadata (notes only in CSV)
        "value_mismatch": 2,
    }
    print("  Expected:           ", fw_expected)
    for key in fw_expected:
        if fw_summary.get(key, 0) != fw_expected[key]:
            print(f"  FAIL: {key} got {fw_summary.get(key)!r}, want {fw_expected[key]!r}")
            ok = False
        else:
            print(f"  OK:   {key} = {fw_expected[key]}")

    if ok:
        print("\nAll checks passed.")
        return 0
    print("\nSome checks failed — inspect mismatches in the UI or manifest.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run in-process validation and compare counts to manifest",
    )
    parser.add_argument(
        "--no-fixed-width",
        action="store_true",
        help="Skip writing fixed-width fixtures",
    )
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()

    if args.no_fixed_width:
        specs = _scenario_rows()
        csv_dir = out_dir / "csv"
        _write_csv(csv_dir / "source.csv", _csv_rows_from_specs(specs, side="source"))
        _write_csv(csv_dir / "target.csv", _csv_rows_from_specs(specs, side="target"))
        manifest = {
            "expected_csv": _expected_summary(specs),
            "scenarios": [asdict(s) for s in specs],
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    else:
        manifest = generate(out_dir)

    print(f"Wrote fixtures to {out_dir}")
    print(f"  CSV:          {out_dir / 'csv' / 'source.csv'}")
    print(f"                {out_dir / 'csv' / 'target.csv'}")
    if not args.no_fixed_width:
        print(f"  Fixed-width:  {out_dir / 'fixed-width'}")
    print(f"  Manifest:     {out_dir / 'manifest.json'}")
    print(f"  API payload:  {out_dir / 'validate_request.json'}")
    print(f"  README:       {out_dir / 'README.md'}")

    if args.verify:
        return verify(out_dir, manifest if not args.no_fixed_width else json.loads((out_dir / "manifest.json").read_text()))
    print("\nRun with --verify to validate in-process, or use the README for UI/API steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

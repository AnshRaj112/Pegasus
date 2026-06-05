# Parser Performance

**Fixtures:** `generated-10k-8cols`, `generated-100k-8cols`, delimiter `||`, no quoted fields.

## Parsers Evaluated

| Parser | 10K rows | 100K rows | CPU | Allocations | Notes |
|--------|----------|-----------|-----|-------------|-------|
| `flat_file_to_polars` (legacy) | ~70 ms | ~670 ms | High | All lines + column dicts | Quote-aware `split_line` |
| `clevercsv_to_polars` | N/A (returns None) | N/A | — | — | Not used on fixtures |
| **`load_multichar_csv_fast`** | **~15 ms** | **~120 ms** | Low | One bytes buffer + column lists | **New default** |
| PyArrow `read_csv` | — | — | — | — | **Rejected:** single-byte separator only |
| Polars `read_csv(separator='||')` | — | — | — | — | **Rejected:** Polars 1.40 enforces 1-byte |
| `csv.reader` streaming | ~200 ms/100K | Medium | Per-row list | Adapter fallback |

## Delimiter Tokens Tested in Production

| Delimiter | Fast path | Parser |
|-----------|-----------|--------|
| `,` `\t` `|` | PyArrow / Polars | `read_csv_table` |
| `||` `::` `xx` emoji | `can_use_fast_multichar_load` if no `"` in prefix | `load_multichar_csv_fast` |
| Quoted RFC 4180 | No | `split_line` + `parse_lines` |

## Measurements (after optimization)

| Metric | 10K | 100K |
|--------|-----|------|
| Rows/sec (load only) | ~650K | ~830K |
| MB/sec (source file) | ~350 | ~140 |
| CPU% during load | ~1 core saturated | ~1 core |

## Anti-patterns removed

- String split per field via regex on hot path
- `batch_to_dicts` for in-memory `||` workloads
- Full-file pandas round-trip

## Row / column loop audit

| Location | Loop type | Replacement |
|----------|-----------|-------------|
| `_partition_side_streaming` | per-row dict | **Dead path** for `||` when Polars load succeeds |
| `stream_records` | per-row dict | Only multi-char streaming fallback |
| `flat_file.parse_lines` | per-line | Fast bytes path bypasses |

# Pegasus validation internals

This document explains how Pegasus validation actually works in the backend code. It is written as an implementation walkthrough, not as a generic product overview.

The important idea is that validation is layered:

1. the service layer picks the right validator
2. the validator normalizes the input into a comparable shape
3. identities are built from configured key columns or paths
4. compare values are canonicalized and hashed when needed
5. changed rows are rehydrated for column-level drilldown
6. the backend emits a structured mismatch report for the API and UI

## Chapters

1. [Chapter 1: What the backend returns](#chapter-1-what-the-backend-returns)
2. [Chapter 2: How the service chooses a validator](#chapter-2-how-the-service-chooses-a-validator)
3. [Chapter 3: Supported file types](#chapter-3-supported-file-types)
4. [Chapter 4: The core tabular idea](#chapter-4-the-core-tabular-idea)
5. [Chapter 5: How Pegasus decides which column is mismatching](#chapter-5-how-pegasus-decides-which-column-is-mismatching)
6. [Chapter 6: Tabular pipeline for CSV-like and columnar files](#chapter-6-tabular-pipeline-for-csv-like-and-columnar-files)
7. [Chapter 7: CSV, TSV, PSV, DAT, and other delimited files](#chapter-7-csv-tsv-psv-dat-and-other-delimited-files)
8. [Chapter 8: Fixed-width files](#chapter-8-fixed-width-files)
9. [Chapter 9: JSON and NDJSON files](#chapter-9-json-and-ndjson-files)
10. [Chapter 10: Parquet, ORC, and Avro](#chapter-10-parquet-orc-and-avro)
11. [Chapter 11: Archives: ZIP and TAR](#chapter-11-archives-zip-and-tar)
12. [Chapter 12: How the final API report is assembled](#chapter-12-how-the-final-api-report-is-assembled)
13. [Chapter 13: Practical meaning of the mismatch types](#chapter-13-practical-meaning-of-the-mismatch-types)
14. [Chapter 14: End-to-end example for tabular data](#chapter-14-end-to-end-example-for-tabular-data)
15. [Chapter 15: Complexity summary](#chapter-15-complexity-summary)
16. [Chapter 16: Short summary](#chapter-16-short-summary)

---

## Chapter 1: What the backend returns

All validators eventually produce a `MismatchReport`. The shared schema is defined in [pegasus-backend/src/pegasus/validation/comparators/models.py](../pegasus-backend/src/pegasus/validation/comparators/models.py).

The mismatch frame contains these columns:

- `uid`: the row, record, path, or archive entry identity
- `mismatch_type`: the category of difference
- `column_name`: the compare field, JSON path, or metadata field that differs
- `source_value`: the source-side value for the mismatch cell
- `target_value`: the target-side value for the mismatch cell
- `row_detail`: JSON context used for drilldown or debugging

The shared mismatch categories are:

- `missing_in_target`
- `extra_in_target`
- `value_mismatch`
- `value_match`

Important detail: `value_mismatch` is a cell-level mismatch in the report, while `value_mismatch_rows` in summaries counts distinct UIDs that had at least one mismatching cell.

---

## Chapter 2: How the service chooses a validator

The API wires requests through `ValidationService`, which routes by file type and adapter. The routing surface is in [pegasus-backend/src/pegasus/services/validation_service.py](../pegasus-backend/src/pegasus/services/validation_service.py).

In practice, the backend splits input into these families:

- delimited/tabular files such as CSV, TSV, PSV, DAT, and ambiguous flat text
- columnar files such as Parquet, ORC, and Avro
- fixed-width files
- JSON and NDJSON
- archive files such as ZIP and TAR

The service does not use one monolithic comparator. It delegates to a format-specific path, then converges on the same mismatch model.

```mermaid
flowchart TD
    A[API / service call] --> B[ValidationService]
    B --> C{Input format}
    C -->|Delimited / tabular| D[Tabular pipeline]
    C -->|Columnar| D
    C -->|Fixed-width| E[Fixed-width comparator]
    C -->|JSON / NDJSON| F[JSON comparator]
    C -->|Archive| G[Archive comparator]

    D --> H[MismatchReport]
    E --> H
    F --> H
    G --> H
```

---

## Chapter 3: Supported file types

The backend can validate the following file families:

- delimited text files such as CSV, TSV, PSV, TXT, and DAT
- ambiguous flat files that are resolved as delimited text after sniffing
- columnar files such as Parquet, ORC, and Avro
- fixed-width text files
- JSON documents and NDJSON / JSONL streams
- archive files such as ZIP and TAR

The route chosen depends on the detected format and the adapter that can read it.

How that maps to the implementation:

- delimited and ambiguous flat files go through the tabular pipeline after delimiter/header resolution
- Parquet, ORC, and Avro are converted into a tabular representation and then sent through the same tabular reconciliation path
- fixed-width files use the fixed-width parser and field layout rules
- JSON and NDJSON use the JSON comparator and recursive path diffing
- ZIP and TAR use the archive comparator, with optional nested leaf validation when a payload file is found

Supported file types are therefore not just a list of extensions; they are a list of backend execution paths.

---

## Chapter 4: The core tabular idea

For CSV-like and columnar data, Pegasus compares rows in two stages:

1. identity matching tells the backend whether a row exists on both sides
2. fingerprint or drilldown comparison tells the backend whether the row content differs

That separation matters because a row can be present on both sides but still differ in only one field. The fingerprint catches the change cheaply; the drilldown step explains which column changed.

### 3.1 Canonicalization

Before hashing or comparing, the backend converts values into deterministic strings. The canonicalization logic lives in [pegasus-backend/src/pegasus/validation/pipeline/fingerprint.py](../pegasus-backend/src/pegasus/validation/pipeline/fingerprint.py).

The default normalization does the following:

- trims strings
- treats empty strings and null-like tokens such as `null`, `none`, `na`, and `n/a` as `__NULL__`
- lets compare-policy rules override the default behavior for specific fields

This is what prevents false mismatches caused by formatting differences alone.

### 3.2 Identity generation

Each tabular row gets a stable identity key from one or more identity columns. The identity parts are canonicalized, then joined with a pipe character.

Example:

```text
region|customer_id|account_number
```

Identity is used only for row matching. It is not the same as the compare fingerprint.

### 3.2.1 Multiple UID columns

When more than one UID column is configured, Pegasus treats them as one composite identity rather than as separate matches.

The implementation behavior is:

- the configured UID columns are split on commas
- each UID column is canonicalized on its own
- the canonical parts are joined into a single identity key with `|`
- the same composite key is used on both source and target

That means a row is considered the same only if the full UID tuple matches.

Example:

```text
UID columns: region, customer_id, account_number
Identity key: region|customer_id|account_number
```

If `region` matches but `customer_id` does not, the row is not treated as the same row. It is a different identity entirely. This is what lets the validator handle compound business keys correctly.

For mapped compare fields, the UID columns are excluded from compare-field resolution, so they are used only for identity and not for mismatch drilldown.

### 3.3 Fingerprint generation

After the compare columns are canonicalized, Pegasus joins them with the field separator `\x1f` and hashes the result. The default algorithm is `xxhash64`, with `sha256`, `xxhash128`, and `crc64` supported as options.

The fingerprint answers one question: does this row’s compare payload match the opposite side?

### 3.4 Partitioning for scale

Large tabular jobs are not compared in one giant join. The pipeline partitions rows by identity hash and writes partitions to disk when needed.

```mermaid
flowchart LR
    A[Row] --> B[Identity columns]
    B --> C[Identity key]
    C --> D[Partition hash]
    D --> E[Partition bucket]
    E --> F[Spill / reconcile]
```

The partition hash is based on the identity key, so identical identities always land in the same bucket.

### 3.5 Hash storage cost

The row fingerprint itself is small. With the default `xxhash64` path, the digest is 8 bytes per row. Other algorithms change that cost:

- `xxhash64`: 8 bytes
- `xxhash128`: stored as an 8-byte truncated digest in this pipeline path
- `sha256`: 32 bytes

So the fingerprint payload alone costs approximately:

```text
hash_bytes ~= row_count × digest_size
```

Examples:

- 10 million rows with `xxhash64` needs about 80 MB just for raw digests
- 100 million rows with `xxhash64` needs about 800 MB just for raw digests
- 100 million rows with `sha256` needs about 3.2 GB just for raw digests

That is only the hash bytes. Real memory is higher because the pipeline also stores keys, joins, frame metadata, temporary partitions, and drilldown payloads.

---

## Chapter 5: How Pegasus decides which column is mismatching

This is the part most people care about.

The backend does not infer a mismatching column directly from the row fingerprint. The fingerprint only says that some compare value changed. The actual column attribution comes from a second pass over the changed rows.

### 4.1 The first pass only finds changed identities

For tabular data, the pipeline joins source and target by identity, then compares fingerprints.

- if an identity exists only in source, it becomes `missing_in_target`
- if an identity exists only in target, it becomes `extra_in_target`
- if an identity exists on both sides but the fingerprints differ, the row is marked changed

That first pass is cheap because it avoids column-by-column comparison for every row.

```mermaid
flowchart TD
    A[Source rows] --> B[Build UID from identity columns]
    C[Target rows] --> D[Build UID from identity columns]
    B --> E[Join on UID]
    D --> E
    E --> F{UID only on one side?}
    F -->|Source only| G[missing_in_target]
    F -->|Target only| H[extra_in_target]
    F -->|Both sides| I[Compare fingerprints]
    I --> J{Fingerprint equal?}
    J -->|Yes| K[Match]
    J -->|No| L[Changed row]
```

### 4.2 The second pass rehydrates compare columns

Once the pipeline has a list of changed identities, it fetches the original row values for only those identities and compares the compare columns one by one.

The drilldown path is implemented in [pegasus-backend/src/pegasus/validation/pipeline/in_memory.py](../pegasus-backend/src/pegasus/validation/pipeline/in_memory.py) for RAM jobs and in [pegasus-backend/src/pegasus/validation/pipeline/partition_reconcile.py](../pegasus-backend/src/pegasus/validation/pipeline/partition_reconcile.py) for spill jobs.

The key rule is:

- each compare column is checked independently
- if a column differs, a `ColumnDifference` is recorded
- each difference becomes a `value_mismatch` row with `column_name` set to that logical compare field

```mermaid
flowchart TD
    A[Changed UID] --> B[Load source row]
    A --> C[Load target row]
    B --> D[Check compare column 1]
    C --> D
    D --> E{Values equal?}
    E -->|Yes| F[No mismatch for that column]
    E -->|No| G[Emit value_mismatch for column]
    G --> H[Repeat for next compare column]
```

### 4.3 What `column_name` means in tabular output

In tabular validation, `column_name` is the logical compare key, not always the raw physical source column.

This matters when column mappings are used. The mapping resolver in [pegasus-backend/src/pegasus/validation/comparators/mapping_resolver.py](../pegasus-backend/src/pegasus/validation/comparators/mapping_resolver.py) can map one logical compare key to one or more physical source/target columns.

So the backend may compare:

- one physical column on both sides
- multiple physical columns that are joined into one logical compare key
- different source and target column names under a single logical field

When that happens, the mismatch report still uses the logical key as `column_name`.

### 4.4 How values are compared

The compare policy in [pegasus-backend/src/pegasus/validation/comparators/policy.py](../pegasus-backend/src/pegasus/validation/comparators/policy.py) can change how values are canonicalized and compared.

The policy supports:

- text normalization
- automatic date parsing for simple columns
- structured comparisons for nested values
- regex replacement and prefix stripping per side
- sensitive-field masking in the returned report

If a field mapping is configured, the policy compares the logical compare key by canonicalizing the source-side physical columns and the target-side physical columns separately, then comparing the canonical results.

### 4.5 How the drilldown payload is built

For each changed row, Pegasus stores `row_detail` so the API can show context.

- source-side details are stored under `source_record`
- target-side details are stored under `target_record`
- the record includes the UID plus the compare columns used for the drilldown

This is what lets the UI show not just that a row changed, but what the row looked like on each side.

### 4.6 Concrete example

If a row has identity `region|123|abc` and the compare columns are `name`, `status`, and `amount`:

1. the partition join says the UID exists on both sides
2. the fingerprints differ
3. the drilldown step loads the source and target row for that UID
4. the backend compares `name`, `status`, and `amount` independently
5. if only `status` changed, the report gets one `value_mismatch` row with `column_name = status`
6. if `status` and `amount` both changed, the report gets two `value_mismatch` rows for the same UID

That is how the backend knows which column changed.

---

## Chapter 6: Tabular pipeline for CSV-like and columnar files

The main high-throughput path is the tabular reconciliation pipeline in [pegasus-backend/src/pegasus/validation/pipeline/pipeline.py](../pegasus-backend/src/pegasus/validation/pipeline/pipeline.py).

### 5.1 Entry point and planning

The pipeline first resolves schema, row-count estimates, and compare columns. It also decides whether to use an in-memory fast path or spill to disk.

The configuration can control:

- memory budget
- auto in-memory threshold
- partition count
- whether column drilldown is enabled
- whether fingerprints should be written to spill files
- which fingerprint algorithm to use

### 5.2 In-memory fast path

If the datasets are small enough, the backend loads both sides into memory and uses Polars joins directly.

The in-memory path still follows the same logic:

- join by identity
- find missing and extra identities
- compare fingerprints for inner-joined rows
- optionally drill down to column differences

When drilldown is enabled, [pegasus-backend/src/pegasus/validation/pipeline/in_memory.py](../pegasus-backend/src/pegasus/validation/pipeline/in_memory.py) calls `_column_diffs_for_row` to compare compare columns one at a time.

### 5.3 Spill path

For larger datasets, the pipeline partitions source and target rows to disk, then reconciles partitions independently.

The partition reconciliation step:

- loads a partition frame
- renames identity and fingerprint columns to a common shape
- performs anti joins for missing and extra identities
- performs inner joins for changed identities
- compares fingerprints to identify changed rows

If drilldown is enabled, it rehydrates the changed keys and compares the compare columns to produce `ColumnDifference` entries.

### 5.4 Why fingerprints are not the final answer

The fingerprint is only a filter. It is fast, but it does not say which column changed. The drilldown step is what converts a changed row into explicit per-column mismatch rows.

### 5.5 What happens when files are completely unsorted

Sorting is not required for validation.

The pipeline does not compare rows by physical position. It matches rows by identity key, then by fingerprint, and only then by per-column drilldown. So even if source and target are in completely different orders, the validator still finds the correct counterpart row by joining on the UID.

That is why an input like this still works:

- source rows in random order
- target rows in a different random order
- duplicate row positions across files

As long as the UID columns produce the same identity key, the row is matched even if it appears in a totally different place in the file.

One caveat: if the same UID appears more than once on a side, that is no longer a clean one-to-one identity match. The code paths are built around stable identities, so duplicate UIDs make the result ambiguous and can inflate joins or produce duplicate mismatch rows.

### 5.6 How changed UIDs are loaded

When Pegasus needs to inspect a changed UID, it does not start from the top of the original file and scan linearly until it finds the row again.

The backend already did the expensive part during the initial streaming pass:

- each source row and target row was read once from the adapter
- each row was canonicalized, hashed, and assigned to a partition id
- the row was written into a partition file for that side

Later, reconciliation only opens the matching partition files:

- `partition_reconcile.py` compares the source and target partition files for that partition id
- `mismatch_export.py` collects the changed UIDs that need drilldown
- `drilldown_cache.py` loads only the requested UIDs from persisted drilldown frames when available

So the backend does not reload the complete 40 GiB again for each changed row. It reopens only the spill artifacts and drilldown lookups for the partition that contains that UID.

If the job runs in the in-memory fast path, the answer is even simpler: both frames are already loaded in RAM, and the changed UID is resolved by a hash join on identity rather than a file rescan.

### 5.7 What 40 GB combined memory means in practice

The backend does not compute one exact RAM number for every dataset because the real peak depends on row width, column count, string cardinality, partition count, and whether drilldown is enabled. But it does have a clear operating mode:

- `validation_auto_in_memory_max_bytes` defaults to 256 MiB
- `TabularPipelineConfig.memory_budget_bytes` defaults to 1 GiB in the pipeline config
- `validation_memory_budget_bytes` in the service config defaults to 10 GiB

So a 40 GB combined source+target input is far above the in-memory thresholds and will go to spill/partitioned reconciliation.

For a rough partition-size estimate, the default tabular pipeline uses a `medium` partition preset of 2048 partitions. If the combined input is about 40 GiB, the average raw data per partition pair is roughly:

```text
40 GiB / 2048 ≈ 20 MiB per partition pair
```

That is only the raw split size before object overhead. The actual peak RAM is higher because each partition still needs frame metadata, hash tables, join state, and optional drilldown rows, but it is still bounded to one partition or one wave of partitions instead of the full 40 GB at once.

If you want a simple summary:

- in-memory fast path: not selected for 40 GB combined
- spill path: selected
- raw hash space: 8 bytes per row for `xxhash64`
- practical RAM: driven by a single partition, not the full dataset

### 5.8 Complexity for tabular validation

For tabular validation, let:

- $n$ = number of rows per side
- $c$ = number of compare columns
- $u$ = number of unique identity keys
- $p$ = number of partitions

The rough cost model is:

- identity canonicalization: $O(n)$
- fingerprint generation: $O(n \cdot c)$
- join and partition routing: about $O(n)$ average for hash-based matching
- drilldown for changed rows: $O(m \cdot c)$ where $m$ is the number of changed rows sampled or fully materialized

So the overall runtime is roughly:

$$
O(n \cdot c + m \cdot c)
$$

For unsorted inputs this does not become $O(n^2)$ because the backend does not scan for matching rows linearly; it uses identity hashing and joins.

The space cost is dominated by:

- partition files or in-memory frames
- hash keys and join state
- optional drilldown rows

So the space model is roughly:

$$
O(n \cdot c)
$$

for the full logical data volume, but the peak resident memory is reduced by partitioning and spill behavior.

---

## Chapter 7: CSV, TSV, PSV, DAT, and other delimited files

Delimited files use the tabular path after the adapter resolves the file layout.

### 6.1 What the adapter resolves

The delimited adapter determines:

- delimiter
- whether the file has headers
- how many rows to skip
- the effective column names
- whether synthetic names are needed for headerless data

DAT files are not a separate algorithm. If the content is recognized as delimited text, they flow through the same delimited/tabular path.

### 6.2 How mismatches are formed

For each row:

1. the identity is built from the configured identity columns
2. compare values are canonicalized
3. a row fingerprint is computed
4. the row is grouped into a partition bucket or in-memory join
5. the backend classifies the row as missing, extra, changed, or matching
6. changed rows are drilled down into individual columns

### 6.3 Missing and extra rows

Missing rows are found through identity-set comparison before any column comparison happens.

Extra rows are the same idea from the target side.

These rows do not get a `column_name` because the row itself is the mismatch, not a specific field.

### 6.4 Value mismatches

Rows that exist on both sides but differ in at least one compare column produce one `value_mismatch` record per differing column.

If the row differs in three columns, the report will contain three mismatch rows with the same UID and three different `column_name` values.

---

## Chapter 8: Fixed-width files

Fixed-width validation uses explicit field positions instead of delimiters.

### 7.1 Input shape

The fixed-width validator receives:

- two fixed-width files
- a layout that defines field names and character ranges
- a UID field
- optional compare rules for field-level normalization

### 7.2 Parsing logic

Each non-empty line is sliced by its field positions. The code then builds `source_by_uid` and `target_by_uid` maps.

### 7.2.1 How fixed-width knows column width

Fixed-width does not guess widths from the content. The width comes from the declared layout.

Each field definition provides start and end positions, so the backend knows exactly how many characters belong to the field. For example, if `username` is defined as columns 1 through 5, then the value is always read from that 5-character window.

That means if the file stores `00000` in the username slice, the validator reads the whole 5-character slice and then applies the configured comparison rule to it. If the field is shorter in the source text, the slice still exists logically in the layout and the parser will usually return padding or blank-equivalent content for that region.

The important point is:

- the field width is declared up front
- the parser does not infer it dynamically from the value text
- comparison happens on the extracted slice, not on visual spacing in the file

### 7.3 How the mismatch column is chosen

Fixed-width is simpler than tabular drilldown because each compare field is already explicit.

For each shared UID:

- the code transforms each compare field value
- the field values are compared with field-specific rules
- when a field differs, the report emits a `value_mismatch` row with `column_name = field.field_name`

So in fixed-width validation, the field name itself is the column attribution.

### 7.4 Comparison rules

The comparator can apply:

- regex replacement
- date parsing
- structured comparisons for nested content
- integer and float comparisons
- text comparisons
- sensitive-field masking

### 7.5 Fixed-width flow

```mermaid
flowchart TD
    A[Read fixed-width file] --> B[Slice fields by layout]
    B --> C[Build row maps by UID]
    C --> D{UID in both files?}
    D -->|No| E[Emit missing / extra]
    D -->|Yes| F[Compare each field]
    F --> G[Emit value_mismatch rows by field]
```

---

## Chapter 9: JSON and NDJSON files

JSON validation is recursive and path-based.

### 8.1 Two modes

The JSON comparator supports:

- a single JSON document
- NDJSON, where each line is a JSON object

### 8.2 Single-document mode

In document mode, the comparator recursively walks both trees.

It emits:

- `missing_in_target` when a key or path exists only in the source
- `extra_in_target` when a key or path exists only in the target
- `value_mismatch` when both sides exist but differ

The implementation is in [pegasus-backend/src/pegasus/validation/json_compare.py](../pegasus-backend/src/pegasus/validation/json_compare.py).

### 8.3 How the column/path is chosen

For JSON, `column_name` is usually the JSON path. The helper that appends mismatches sets `column_name` to the current path string unless an explicit override is provided.

Examples:

- `$.customer.name`
- `$.items[0].price`

### 8.4 How recursive diffing works

The comparator checks nested dictionaries and lists separately.

- for dictionaries, it walks keys on both sides and recurses into shared keys
- for lists, it can compare by index or by unordered matching depending on the mode
- for scalar values, a differing pair becomes `value_mismatch`

### 8.5 NDJSON mode

In NDJSON mode, each line is treated like a row. The backend matches records by UID, then recursively compares the JSON payload for each matched record.

This means NDJSON can behave like tabular validation at the outer level and JSON diffing at the inner level.

---

## Chapter 10: Parquet, ORC, and Avro

Columnar formats are not compared with a separate bespoke diff algorithm. They are converted into a tabular representation and sent through the same tabular pipeline used for delimited files.

### 10.1 What changes and what does not

What changes:

- the reader and adapter layer
- how rows are loaded into memory or spill files

What does not change:

- identity matching
- compare-column canonicalization
- fingerprint generation
- drilldown behavior
- mismatch report structure

That is why Parquet, ORC, and Avro behave like tabular inputs from the validation engine’s point of view.

---

## Chapter 11: Archives: ZIP and TAR

Archive validation is layered. The backend can stop early on metadata or digest differences, or continue deeper into manifest and nested-leaf validation.

### 11.1 What kinds of ZIP and TAR are handled

The archive backend treats ZIP and TAR as container families, but it also recognizes the concrete archive forms that usually appear in practice:

- ZIP: standard `.zip` archives
- TAR: plain `.tar` archives
- compressed TAR: `.tar.gz`, `.tgz`, `.tar.bz2`, and `.tar.xz`

So the backend is not just saying “zip” or “tar” in the abstract. It is reading the actual container type and, for TAR, the compression wrapper around it.

### 11.2 What is inside those archives

ZIP and TAR are only the outer container. The backend then inspects the members inside them and decides whether the archive contains a payload that can be validated more deeply.

The nested member types it knows how to recognize include:

- tabular payloads such as CSV, TSV, PSV, TXT, and DAT
- JSON and NDJSON payloads
- fixed-width payloads
- nested archives again, such as ZIP inside ZIP or TAR inside ZIP

In other words:

- a ZIP file may contain a CSV, a JSON document, a fixed-width file, or another archive
- a TAR file may contain the same kinds of payloads
- the validator then chooses the right inner validator for that leaf file

### 11.3 Archive support matrix

The archive layer supports these top-level container formats:

- `.zip`
- `.tar`
- `.tgz`
- `.tar.gz`
- `.tar.bz2`
- `.tar.xz`

The important detail is that `.tgz` and `.tar.gz` are treated as TAR containers after archive-format normalization.

Not supported as first-class top-level archive validators:

- `.7z`
- `.rar`
- a reversed name like `.gz.tar`

Those formats may still appear in nested-member detection logic or as names inside archive manifests, but the backend does not have a dedicated top-level validation path for them.

### 11.4 First checks

The archive comparator may inspect:

- compressed size
- uncompressed size
- CRC32 or CRC32C
- MD5 or content digest when available

If those checks already prove the archives differ, the backend can emit a fast mismatch.

### 11.5 Manifest comparison

If the byte-level precheck does not settle the answer, the comparator reads the archive manifest and compares entry paths and metadata.

That can produce:

- `missing_in_target` for absent entries
- `extra_in_target` for unexpected entries
- `value_mismatch` for entry metadata differences such as digest or size

### 11.6 How archive column names work

In archive comparison, `column_name` is usually a manifest or metadata field. For example, a digest mismatch may use `content_digest`.

### 11.7 Nested archives and leaf validation

The archive code can also inspect nested archive members and, if a leaf file is recognized, hand it off to the correct validator.

Possible leaf types include:

- CSV / TSV / PSV / TXT / DAT
- JSON / NDJSON
- fixed-width data

```mermaid
flowchart TD
    A[Archive pair] --> B[Inspect manifest / members]
    B --> C{Find nested leaf?}
    C -->|Yes| D[Extract leaf files]
    D --> E[Run CSV / JSON / fixed-width validator]
    C -->|No| F[Compare archive manifest only]
    E --> G[Return leaf-level mismatch report]
    F --> G
```

### 11.8 Safety limits

Nested expansion is bounded by limits such as:

- maximum nesting depth
- maximum nested member size
- maximum declared size
- maximum compression ratio

That keeps archive inspection from exploding on pathological inputs.

### 11.9 Complexity for archive validation

Let $e$ be the number of archive entries and $d$ be the nesting depth.

- metadata precheck: $O(1)$ per archive pair
- manifest comparison: $O(e)$
- nested-leaf discovery: about $O(e)$ per archive level, bounded by depth limits
- leaf validation: follows the complexity of the extracted leaf type

So archive validation is typically:

$$
O(e + \text{leaf validation cost})
$$

with safety bounds preventing unbounded recursive expansion.

---

## Chapter 12: How the final API report is assembled

After validation completes, the backend builds the API response from the mismatch report and summary counters.

The summary includes counts for:

- missing rows or paths
- extra rows or paths
- value mismatches

The API layer also computes a per-column breakdown for value mismatches when the result set is small enough.

### 12.1 Per-column aggregation in the API

The API can populate `value_mismatch_by_column`, which is a count of value mismatches grouped by `column_name`.

That aggregation is controlled by `validation_value_mismatch_column_stats_max_rows` in [pegasus-backend/src/pegasus/core/config.py](../pegasus-backend/src/pegasus/core/config.py).

If the number of value-mismatch rows is too large, the backend skips per-column aggregation to avoid extra memory use.

### 12.2 Sample groups

The API can also return mismatch sample groups so the UI has a small preview set for each category.

For value mismatches, the sample rows usually include:

- UID
- mismatch type
- column name
- source value
- target value
- row detail

### 12.3 When there are no mismatches

If the result is a full match, the backend may still emit a small match sample frame so the response shape stays consistent.

### 12.4 Complexity for API aggregation

The API-side aggregation is linear in the number of returned mismatch rows.

- summary counts: $O(r)$ where $r$ is mismatch row count
- per-column counts: $O(r)$
- sample grouping: about $O(r)$

So the response-building work is usually dominated by the size of the mismatch output, not by the original source file size.

---

## Chapter 13: Practical meaning of the mismatch types

A simple way to read the report is:

- `missing_in_target`: the record exists in source but not in target
- `extra_in_target`: the record exists in target but not in source
- `value_mismatch`: the record exists on both sides, but one field or path differs
- `value_match`: the record matched, usually used for sample or preview output

This meaning is consistent across formats, but the comparison mechanism differs:

- tabular files use identity + fingerprint + drilldown
- fixed-width files use UID + field comparison
- JSON uses recursive path diffing
- archives use entry metadata and optional leaf validation

---

## Chapter 14: End-to-end example for tabular data

If you want the shortest mental model for how the backend finds a mismatching column, it is this:

1. read the source and target rows
2. build the UID from the identity columns
3. canonicalize the compare columns
4. hash the compare payload to get a fingerprint
5. join source and target by UID
6. if the UID is on only one side, emit missing or extra
7. if the UID is on both sides but the fingerprint differs, mark the row changed
8. rehydrate the original row values for that UID
9. compare each compare column one by one
10. emit one `value_mismatch` row per differing column

That is how Pegasus knows which column changed instead of only knowing that the row changed.

---

## Chapter 15: Complexity summary

This is the short version of the scaling behavior.

### 15.1 Tabular and columnar

- runtime: roughly $O(n \cdot c)$ plus drilldown on changed rows
- space: roughly $O(n \cdot c)$ logical volume, but bounded peak memory through partitioning
- unsorted inputs: handled by hashing and joins, not by positional scanning

### 15.2 Fixed-width

- runtime: roughly $O(n \cdot c)$ because each UID row is compared field by field
- space: roughly $O(n)$ for UID maps plus mismatch output

### 15.3 JSON and NDJSON

- runtime: roughly $O(s)$ where $s$ is the size of the JSON tree or records visited, plus path recursion and list matching cost
- space: roughly $O(d)$ recursion depth for tree walk, plus the output rows

### 15.4 Archives

- runtime: roughly $O(e)$ for manifest work plus the cost of any extracted leaf validation
- space: bounded by manifest size, extracted leaf size, and safety limits

### 15.5 Practical 40 GB note

This section gives a worked estimate instead of a summary.

Assume:

- combined source + target size = 40 GiB
- total rows across both sides = 100,000,000
- total columns = 12
- fingerprint algorithm = `xxhash64`
- partition preset = `medium` = 2048 partitions

#### 15.5.1 Average raw row size

First compute the average raw bytes per row:

$$
\frac{40 \times 2^{30}}{100,000,000} = \frac{42,949,672,960}{100,000,000} = 429.4967296 \text{ bytes/row}
$$

So the average row is about 429.5 bytes across the combined source and target dataset.

If the 12 columns are evenly distributed, the average raw bytes per column are:

$$
\frac{429.4967296}{12} = 35.79139413 \text{ bytes/column/row}
$$

That is only an average. Real columns will be uneven, but it is good enough for a planning estimate.

#### 15.5.2 Hash storage

With `xxhash64`, each row fingerprint is 8 bytes.

So the raw fingerprint storage is:

$$
100,000,000 \times 8 = 800,000,000 \text{ bytes}
$$

Convert that to MiB:

$$
\frac{800,000,000}{2^{20}} = 762.939453125 \text{ MiB}
$$

So the fingerprints alone take about 763 MiB for 100 million total rows.

If you meant 100 million rows per side rather than total across both sides, double that to about 1.49 GiB of raw digest storage.

#### 15.5.3 Partition sizing

With 2048 partitions, the average rows per partition are:

$$
\frac{100,000,000}{2048} = 48,828.125 \text{ rows/partition}
$$

The average raw bytes per partition pair are:

$$
\frac{40 \times 2^{30}}{2048} = 20,971,520 \text{ bytes}
$$

$$
= 20 \text{ MiB}
$$

If the data is split evenly between source and target, that is about 10 MiB per side per partition on average.

#### 15.5.4 UID and compare payload estimate

If the 12 columns are split as 2 UID columns and 10 compare columns, then the average bytes per row are:

$$
2 \times 35.79139413 = 71.58278826 \text{ bytes}
$$

$$
10 \times 35.79139413 = 357.9139413 \text{ bytes}
$$

Per partition, that becomes approximately:

$$
71.58278826 \times 48,828.125 \approx 3,495,000 \text{ bytes}
$$

$$
357.9139413 \times 48,828.125 \approx 17,456,520 \text{ bytes}
$$

So one average partition pair carries about:

- 3.33 MiB of UID payload
- 16.65 MiB of compare payload
- 0.37 MiB of fingerprint bytes

which sums back to about 20 MiB of raw partition data.

#### 15.5.5 Peak RAM estimate

The pipeline does not need to hold the full 40 GiB in memory at once because it spills partitions and reconciles them in waves.

A rough working-set estimate for one partition pair is:

$$
\approx \text{source partition} + \text{target partition} + \text{join overhead} + \text{drilldown overhead}
$$

If we treat the raw partition pair as 20 MiB, then a conservative multiplier of 2x to 4x for join tables, frame overhead, and intermediate buffers gives:

$$
20 \text{ MiB} \times 2 = 40 \text{ MiB}
$$

$$
20 \text{ MiB} \times 4 = 80 \text{ MiB}
$$

So a practical per-partition working set is often in the rough range of 40 to 80 MiB, before any unusually large mismatch export or drilldown expansion.

#### 15.5.6 Why the job still does not fit in RAM as a whole

Even though a single partition is small, the whole job is not just one partition. The backend still has to:

- maintain partition metadata
- read and write partition files
- build joins or hashes for each partition
- keep drilldown rows for changed keys
- assemble the final mismatch output

That is why the correct conclusion for a 40 GiB combined job is:

- do not expect the in-memory fast path
- expect spill-based reconciliation
- expect the full dataset to live on disk, not in RAM

#### 15.5.7 Concrete planning answer

For a 40 GiB combined source + target dataset with 100 million total rows and 12 columns:

- raw average row size: about 429.5 bytes
- raw average column size: about 35.8 bytes
- raw fingerprint storage: about 763 MiB
- average partition pair size at 2048 partitions: 20 MiB
- rough peak RAM per partition pair: about 40 to 80 MiB
- overall job memory use: dominated by spill files and partition processing, not by holding all 40 GiB in memory

#### 15.5.8 Scaling the same math to 10 GiB and 20 GiB

If the row shape stays the same, the math scales linearly with size.

Using the 40 GiB case as the baseline:

- 10 GiB is one quarter of 40 GiB, so it has about 25,000,000 total rows
- 20 GiB is one half of 40 GiB, so it has about 50,000,000 total rows
- 40 GiB is the baseline, so it has about 100,000,000 total rows

##### 10 GiB case

- total rows: 25,000,000
- fingerprint storage: $25,000,000 \times 8 = 200,000,000$ bytes, about 190.7 MiB
- average partition pair size: $10 \text{ GiB} / 2048 \approx 5 \text{ MiB}$
- rough peak RAM per partition pair: about 10 to 20 MiB

##### 20 GiB case

- total rows: 50,000,000
- fingerprint storage: $50,000,000 \times 8 = 400,000,000$ bytes, about 381.5 MiB
- average partition pair size: $20 \text{ GiB} / 2048 \approx 10 \text{ MiB}$
- rough peak RAM per partition pair: about 20 to 40 MiB

##### 40 GiB case

- total rows: 100,000,000
- fingerprint storage: $100,000,000 \times 8 = 800,000,000$ bytes, about 762.9 MiB
- average partition pair size: $40 \text{ GiB} / 2048 \approx 20 \text{ MiB}$
- rough peak RAM per partition pair: about 40 to 80 MiB

##### Practical reading

The key pattern is:

- disk and partition volume scale linearly with file size
- fingerprint bytes scale linearly with row count
- peak RAM does not scale to the full dataset because only one partition wave is active at a time

So the overall answer is not “40 GiB in RAM.” It is “40 GiB on disk, partitioned into about 20 MiB logical chunks, with a working set sized to one chunk plus join/drilldown overhead.”

If you want the short version in one line: the row-level math is manageable, but the full 40 GiB dataset is far above the in-memory thresholds, so the backend must spill and reconcile partition by partition.

---

## Chapter 16: Short summary

Pegasus validation works by routing each input format into a specialized comparator, but every comparator ultimately feeds the same mismatch report model.

For tabular data, the important sequence is:

1. identity match
2. fingerprint compare
3. column drilldown
4. mismatch report assembly

For the other formats, the same idea applies with different mechanics:

- fixed-width uses explicit field slices
- JSON uses recursive paths
- archives use entry metadata and optional leaf validation

The architectural theme is consistent: fast coarse matching first, then precise column/path attribution only for the records that need it.

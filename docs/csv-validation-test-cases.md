 # CSV Validation — Edge-case Test Cases

 This document lists edge-case test cases that can break CSV validation logic. Each case includes a brief description, a small example (where useful), the expected validation behavior, and notes on why the case is important.

 1. Empty file
    - Description: File with zero bytes.
    - Example: (empty)
    - Expected: Validation should treat as invalid (or configurable: allow empty). Report clear error: "empty input".

 2. Only header row, no data rows
    - Description: Header exists but no records.
    - Expected: Pass or fail depending on requirements; should not crash.

 3. Missing header row when headers expected
    - Description: Data starts immediately without headers.
    - Example: `val1,val2\\n1,2` but parser expects named headers.
    - Expected: Detect missing headers and either infer or report an error.

 4. Mismatched column count (row shorter)
    - Description: A row has fewer fields than the header.
    - Example: `a,b,c\\n1,2`
    - Expected: Flag row as malformed; do not crash; include row number.

 5. Mismatched column count (row longer)
    - Description: A row has more fields than the header.
    - Example: `a,b\\n1,2,3`
    - Expected: Flag as malformed or accept trailing empty header; consistent handling required.

 6. Trailing delimiter (extra comma at line end)
    - Description: Lines end with an extra delimiter implying empty column.
    - Example: `a,b\\n1,2,` 
    - Expected: Handle as empty final field; do not miscount columns.

 7. Fields containing delimiters (commas) without quotes
    - Description: A field includes a comma but is not quoted.
    - Example: `name,address\\nJohn, "12, Main St"` (unquoted)
    - Expected: Treat as malformed unless quoting rules allow; prefer clear error.

 8. Properly quoted fields with embedded newlines
    - Description: A quoted field contains newlines.
    - Example: `"multi\\nline",value`
    - Expected: Parser must allow embedded newlines inside quoted fields (RFC4180).

 9. Unclosed quote
    - Description: A field starts with a quote but the closing quote is missing.
    - Example: `"abc,def,ghi\\n1,2,3`
    - Expected: Error with helpful message; avoid infinite read loops.

 10. Escaped quotes inside quoted field
     - Description: Quotes inside quoted fields are escaped incorrectly (single-quote vs double-quote approaches).
     - Example: `"He said ""hello""",42` (RFC-style) vs `"He said \\\"hello\\\"",42`
     - Expected: Support common escaping conventions or fail with a clear hint.

 11. Mixed delimiters across file (commas and tabs)
     - Description: Some rows use commas; others use tabs.
     - Expected: Either detect delimiter heuristically or report inconsistent delimiter error.

 12. Different newline encodings (\\r, \\n, \\r\\n)
     - Description: File uses CR-only or LF-only or CRLF inconsistently.
     - Expected: Normalize newlines without mis-parsing quoted fields.

 13. Leading/trailing whitespace in unquoted fields
     - Description: Fields have extra spaces that may be significant.
     - Example: `a,b\\n 1 ,2 `
     - Expected: Either trim per config or preserve; never crash.

 14. Fields that are only delimiters (e.g., ",,")
     - Description: Empty fields in sequence, or fields that are delimiter characters only.
     - Example: `a,b,c\\n1,,3`
     - Expected: Preserve empty fields; ensure column alignment.

 15. Non-UTF-8 / binary encodings
     - Description: File encoded in Latin-1, windows-1252, or contains invalid byte sequences.
     - Expected: Detect encoding issues and report; allow configurable fallback encodings.

 16. Byte Order Mark (BOM) present in header
     - Description: UTF-8 BOM at file start alters first header name.
     - Example: `\\uFEFFcol1,col2`
     - Expected: Strip BOM before parsing; do not treat BOM as part of header name.

 17. Very large field (size limits)
     - Description: Single field exceeds memory or configured buffer size.
     - Expected: Stream safely; enforce limits with clear error rather than OOM.

 18. Very large number of columns (wide CSV)
     - Description: Thousands of columns that stress header parsing and memory.
     - Expected: Handle or fail gracefully with resource-limit error.

 19. Very large number of rows (streaming / performance)
     - Description: Millions of rows causing timeouts or memory growth.
     - Expected: Ensure streaming parsing and bounded memory usage.

 20. Duplicate header names
     - Description: Header row contains the same name twice.
     - Expected: Detect duplicates and either namespace them (name#2) or report as error.

 21. Missing required fields (empty values in mandatory columns)
     - Description: Required columns exist but some rows have empty values.
     - Expected: Report validation errors with row/column context.

 22. Numeric fields with thousands separators or locale formats
     - Description: Numeric column contains `1,000` or `1.000,50` depending on locale.
     - Expected: Either reject non-standard numerics or parse per locale settings.

 23. Date/time fields in ambiguous formats
     - Description: `01/02/03` could mean various dates.
     - Expected: Validate against expected format(s); report ambiguous parsing.

 24. Null bytes and control characters inside fields
     - Description: Embedded NUL (`\\0`) or other non-printable controls.
     - Expected: Reject or sanitize; ensure parser doesn't treat NUL as terminator.

 25. Inconsistent quoting (mix of quoted and unquoted styles for same column)
     - Description: Some rows quote a value while others don't.
     - Expected: Accept mixed style if logically equivalent; do not miscount fields.

 26. Header-order mismatch vs expected schema
     - Description: Column names present but in different order than validator expects.
     - Expected: Either allow mapping by name or enforce strict order depending on settings.

 27. Records with additional metadata lines (comments) interleaved
     - Description: File contains comment lines (starting with `#`) or metadata between rows.
     - Expected: Configurable support to skip comments; do not treat as data.

 28. Inconsistent row terminator inside quoted field boundaries
     - Description: Newlines within quotes vs unquoted rows cause confusion if newline normalization is naive.
     - Expected: Proper quoting-aware newline handling per RFC4180.

 29. Mixed encodings within the same file
     - Description: Some rows contain bytes from different encodings (rare, but may happen in concatenated files).
     - Expected: Fail fast and report encoding inconsistencies.

 30. Incorrect header count due to escaped delimiters in header
     - Description: Header contains quoted delimiters that are not handled, changing header column count.
     - Expected: Correctly parse quoted headers; treat them like regular fields.

 Notes on usage
 - For each test case, provide a minimal input file and run the CSV validator asserting the expected result and message.
 - Focus tests on both correctness (accept/reject) and robustness (no crashes, no hangs, bounded memory).
 - Where behavior depends on configuration (e.g., trimming, encoding, delimiter), add tests for both default and configured modes.

 If you want, I can: generate small sample files for these cases under `test-data/` and add pytest tests that assert expected validator behavior.

Extremely weird additional cases (10)

51. File with only a BOM and nothing else
    - Why it breaks: Parser sees a header-like BOM but no columns; some libraries treat BOM-only files as empty, others as malformed.
    - Expected: Detect BOM-only file and report "no headers found".

52. Double-delimiter escape misuse
    - Scenario: File uses `;` delimiter but `;;` is used to indicate a literal `;` inside fields (non-standard hack).
    - Why it breaks: Standard parsers don't treat `;;` specially, splitting fields incorrectly.
    - Expected: Either reject non-standard escaping or provide configurable multi-char escape support.

53. Regex-metacharacter payload in a cell
    - Scenario: Cells contain heavy regex patterns (e.g., `(.*?){10000}`) that upstream validation attempts to compile.
    - Why it breaks: Validators that compile user content into regex can suffer ReDoS or crash.
    - Expected: Treat content as plain text; avoid compiling untrusted input.

54. Zero-width characters used to spoof column names
    - Scenario: `Name` vs `Name` (vertical tab) appear visually identical but differ logically.
    - Why it breaks: Schema matching fails silently; duplicates or wrong-field mapping occurs.
    - Expected: Normalize or strip invisible controls from headers before validation.

55. Excel-formula injection (leading `=` or `+`)
    - Scenario: A cell begins with `=CMD|'/C calc'!A0` or `=@malicious()`.
    - Why it breaks: Downstream consumers (Excel) may execute formulas when opened; validators might attempt to sanitize and strip, introducing data drift.
    - Expected: Detect formula-like values and either escape (prepend `'`) or reject per policy.

56. Split UTF-8 codepoint across record boundary
    - Scenario: A multi-byte UTF-8 character is split so half the bytes appear at end of one buffer/row and remaining at start of next.
    - Why it breaks: Incremental decoders error, producing replacement characters or exceptions.
    - Expected: Use proper UTF-8 streaming decoder that buffers incomplete sequences.

57. Nested triple-quote chaos
    - Scenario: Fields use non-standard triple-quote like `"""some "" text"""`.
    - Why it breaks: Parsers expecting single/double escapes get confused by multi-level quoting.
    - Expected: Reject ambiguous quoting or allow only standard RFC-style escaping.

58. SQL / Command injection-like header names
    - Scenario: Header is `SELECT * FROM users; --` or contains `; rm -rf /`.
    - Why it breaks: If validators attempt to dynamically build SQL or shell commands with header names, they may execute harmful commands.
    - Expected: Never execute or interpolate raw header names; sanitize before use.

59. Lone surrogate halves (invalid UTF-16 content)
    - Scenario: UTF-16 file with a high surrogate but no low surrogate, leading to invalid decoding.
    - Why it breaks: Decoding fails; some libraries raise errors while others silently replace characters.
    - Expected: Detect invalid surrogate pairs and fail with encoding error.

60. Mid-file delimiter change (half comma, half semicolon)
    - Scenario: First N rows use `,` then later rows use `;` as delimiter (e.g., concatenated from sources).
    - Why it breaks: Heuristics set the delimiter based on header or first rows and mis-parse latter rows.
    - Expected: Detect delimiter inconsistency and either auto-detect per-row or report mixed-delimiter error.

Additional user-provided problematic cases

31. The Quoted-Quote Cliffhanger
    - Raw: `ID,Description,Status\n1,"This is an escaped quote \" ,Active`
    - Why it breaks: Unclosed quoted field swallows the rest of the file; row alignment lost.
    - Expected: Error reporting unclosed quote at row 1 with no hangs.

32. Multiline Fields with Mixed Newlines
    - Raw (bytes): `ID,Bio,Role\r\n1,"Line1\nLine2\rLine3",Admin\r\n`
    - Why it breaks: Naive line-splitting before quote handling splits a single record into multiple.
    - Expected: Allow embedded mixed newlines inside quoted fields.

33. Naked Quotes Inside Quoted Fields
    - Raw: `ID,Comment,Rating\n1,"User said "Wow" directly",5`
    - Why it breaks: Unescaped interior quote prematurely ends field.
    - Expected: Either accept common escape styles or report malformed quote with location.

34. The Malformed BOM (Byte Order Mark) Illusion
    - Raw: File saved as UTF-16 BE bytes (e.g. FE FF ...) but read as UTF-8
    - Why it breaks: Header bytes decode to gibberish (e.g. ÿþID) and schema validation fails.
    - Expected: Detect incompatible BOM/encoding and fail with suggested encoding.

35. The Zero-Column Row
    - Raw: `ID,Name\n1,Alice\n\n2,Bob`
    - Why it breaks: Empty line parsed as [""] vs [] causing index errors when accessing columns.
    - Expected: Treat purely empty lines as skip or report as empty record according to config.

36. The 64KB Token Borderline
    - Scenario: Single field contains 65,535–65,536 bytes without delimiters.
    - Why it breaks: Stream buffers may split token across internal buffers causing truncated or split fields.
    - Expected: Stream-join token parts correctly; enforce max-field-size with clear error.

37. The NTFS Alternate Data Streams (ADS) Payload
    - Filename: `data.csv:secret.txt` (Windows NTFS ADS)
    - Why it breaks: OS-level alternate streams may be read instead of expected main stream.
    - Expected: Validate using safe file APIs and reject ADS paths when not allowed.

38. POSIX NUL-Truncated Filenames
    - Filename: `valid_report.csv\x00malicious_script.sh`
    - Why it breaks: Underlying OS truncates at NUL; validator opens only prefix.
    - Expected: Reject paths containing NUL bytes and report suspicious filename.

More weird / stupid cases to stress validators

39. Header contains control characters (e.g., vertical tab)
    - Why it breaks: Header lookup fails because name contains invisible controls.
    - Expected: Sanitize headers or error with exact byte position.

40. Field contains JSON blob with internal commas and braces
    - Why it breaks: If not quoted correctly the commas inside JSON split columns.
    - Expected: Support quoted JSON fields or reject unquoted blobs.

41. Embedded CSV (CSV inside a quoted field) with its own header
    - Why it breaks: Nested CSV can confuse heuristics and header-count checks.
    - Expected: Treat nested content as opaque string when quoted.

42. Emoji / surrogate pairs near buffer boundaries
    - Why it breaks: Invalid UTF-8 split yields decoding errors or replacement characters.
    - Expected: Correctly handle multi-byte UTF-8 sequences across buffers.

43. Right-to-left and Unicode directionality marks inside headers
    - Why it breaks: Visual mismatch vs logical name leads to schema mismatch.
    - Expected: Normalize or reject directional controls in headers.

44. Extremely long header names (>> 255 chars)
    - Why it breaks: Some downstream systems assume short identifiers and crash.
    - Expected: Enforce sane limits or truncate consistently with warnings.

45. Concatenated CSV files without separator newline
    - Raw: `<csv1><csv2>` appended without trailing newline between them.
    - Why it breaks: Last record of first file and first of second may merge.
    - Expected: Detect multiple header rows or repeated schemas and split appropriately.

46. File that is actually compressed (gzip) but named .csv
    - Why it breaks: Reading raw bytes yields binary gibberish and parser errors.
    - Expected: Detect compression by magic bytes and suggest decompression.

47. Rows with only delimiters (`,,`, `,,,`)
    - Why it breaks: Ambiguous whether these are empty records or many empty fields.
    - Expected: Preserve empty fields and handle row length consistently.

48. Mixed escape conventions within same file ("" vs \" escape)
    - Why it breaks: Mixed escaping confuses quote handling heuristics.
    - Expected: Either normalize to a single convention or report inconsistent escaping.

49. Malformed UTF-8 byte sequences inside fields
    - Why it breaks: Decoder errors raise exceptions if not handled.
    - Expected: Replace or reject broken sequences with clear error.

50. Non-printable high-bit bytes (binary payload) in unquoted field
    - Why it breaks: May break CSV consumers expecting text; can hide malware.
    - Expected: Detect binary content and fail validation unless allowed.

Usage notes
- I appended these user cases and 13 extra weird cases to expand coverage. Each should ideally have a small sample file and an automated pytest asserting parser behavior.
- Next step: I can scaffold sample files under `test-data/csv-edgecases/` and add pytest tests in `pegasus-backend/tests/` that exercise the validator with expected outcomes.


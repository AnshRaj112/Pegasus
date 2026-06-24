/**
 * Maps backend file-detection labels (see pegasus-backend/tests/format_detection_cases.py)
 * to consistent UI strings. Chains use the backend separator ` -> ` (shown as →).
 */

/** Tabular delimiter flavors collapse to one user-facing label in the wizard overview. */
const DELIMITED_FILE_SEGMENTS = new Set(['csv', 'tsv', 'psv', 'delimited', 'dat']);

const SEGMENT_LABELS: Readonly<Record<string, string>> = {
  // Layout
  'fixed-width': 'Fixed Width',
  fixedwidth: 'Fixed Width',
  fixed: 'Fixed Width',

  // Structured / columnar
  json: 'JSON',
  parquet: 'Parquet',
  orc: 'ORC',
  avro: 'Avro',
  excel: 'Excel',

  // Markup / plain
  xml: 'XML',
  yaml: 'YAML',
  yml: 'YAML',
  txt: 'Text',
  empty: 'Empty',

  // Images
  png: 'PNG',
  jpeg: 'JPEG',
  jpg: 'JPEG',
  gif: 'GIF',
  webp: 'WEBP',
  bmp: 'BMP',
  svg: 'SVG',

  // Documents / binary
  pdf: 'PDF',
  bin: 'Binary',
  sqlite: 'SQLite',
  unknown: 'Unknown',

  // Containers / compression
  zip: 'ZIP',
  tar: 'TAR',
  '7z': '7Z',
  rar: 'RAR',
  gzip: 'GZIP',
  bzip2: 'BZIP2',
  xz: 'XZ',
  zstd: 'ZSTD',
  lz4: 'LZ4',
};

const normalizeSegment = (segment: string): string =>
  segment.toLowerCase().trim().replace(/_/g, '-');

/** Format one detection token (e.g. csv, fixed-width, gzip). */
export const formatDetectionSegmentLabel = (segment: string): string => {
  const raw = segment.trim();
  if (!raw) return '—';

  const normalized = normalizeSegment(raw);
  if (DELIMITED_FILE_SEGMENTS.has(normalized)) {
    return 'Delimited file';
  }

  const mapped = SEGMENT_LABELS[normalized];
  if (mapped) return mapped;

  if (normalized === 'empty file') return 'Empty';

  // Short extension-like tokens: DAT, ABC, etc.
  if (/^[a-z0-9]{1,6}$/.test(normalized)) {
    return normalized.toUpperCase();
  }

  return raw
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ');
};

/**
 * Format a backend `file_format` / display label (plain or chained with ` -> `).
 * Examples: `csv` → Delimited file, `psv` → Delimited file, `zip -> csv` → ZIP → Delimited file
 */
export const formatDetectionLabel = (format: string | null | undefined): string => {
  if (!format || format === '—' || format === '…') return format ?? '—';

  const normalized = format.trim();
  if (!normalized) return '—';

  if (normalized.includes('->')) {
    return normalized
      .split('->')
      .map((part) => formatDetectionSegmentLabel(part.trim()))
      .join(' → ');
  }

  return formatDetectionSegmentLabel(normalized);
};

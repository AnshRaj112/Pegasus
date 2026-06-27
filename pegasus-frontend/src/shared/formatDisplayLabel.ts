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

export type FormatChainDisplay = {
  short: string;
  middle: string | null;
  full: string;
};

/** Collapse long chains to `TAR → … → Delimited file` with middle segments for tooltips. */
export const formatDetectionChainDisplay = (format: string | null | undefined): FormatChainDisplay => {
  if (!format || format === '—' || format === '…') {
    const fallback = format ?? '—';
    return { short: fallback, middle: null, full: fallback };
  }

  const normalized = format.trim();
  if (!normalized.includes('->')) {
    const label = formatDetectionLabel(normalized);
    return { short: label, middle: null, full: label };
  }

  const segments = normalized.split('->').map((part) => part.trim()).filter(Boolean);
  const labels = segments.map((part) => formatDetectionSegmentLabel(part));
  const full = labels.join(' → ');
  if (labels.length <= 4) {
    return { short: full, middle: null, full };
  }

  const middle = labels.slice(1, -1).join(' → ');
  return {
    short: `${labels[0]} → … → ${labels[labels.length - 1]}`,
    middle,
    full,
  };
};

const chainDepth = (label: string | null | undefined): number => {
  if (!label) return 0;
  if (!label.includes('->')) return 1;
  return label.split('->').length;
};

const kindFromContainingPiece = (token: string): string | null => {
  if (token.endsWith('tar') || token === 'tar') return 'tar';
  if (token.includes('zip')) return 'zip';
  if (['csv', 'tsv', 'psv', 'json', 'parquet', 'orc', 'avro', 'txt', 'dat'].includes(token)) return token;
  if (token.endsWith('csv') || token.endsWith('tsv') || token.endsWith('json')) {
    return token.split('_').pop() ?? token;
  }
  return null;
};

const chainFromContainingSegment = (name: string): string[] => {
  const lower = name.split('/').pop()?.toLowerCase() ?? '';
  if (!lower.includes('_containing_')) return [];
  const chain: string[] = [];
  for (const raw of lower.split('_containing_')) {
    const token = raw.replace(/_file$/, '').replace(/^_|_$/g, '');
    const kind = kindFromContainingPiece(token);
    if (kind) chain.push(kind);
  }
  return chain;
};

export const inferFormatChainFromObjectName = (
  objectName: string | null | undefined,
  outer?: string | null,
): string | null => {
  if (!objectName) return null;
  const segments = objectName.replace(/\\/g, '/').replace(/^\/|\/$/g, '').split('/');
  for (let i = segments.length - 1; i >= 0; i -= 1) {
    const chain = chainFromContainingSegment(segments[i]);
    if (chain.length < 2) continue;
    if (outer && chain[0] !== outer) {
      return [outer, ...chain].join(' -> ');
    }
    return chain.join(' -> ');
  }
  return null;
};

export const formatChainFromArchiveMemberPath = (
  memberPath: string,
  outer: string,
): string | null => {
  const parts = memberPath.replace(/\\/g, '/').split('/').filter(Boolean);
  if (parts.length < 1) return null;
  const chain: string[] = [outer];
  for (const part of parts.slice(0, -1)) {
    const low = part.toLowerCase();
    if (low.endsWith('.tar') || low.endsWith('.tgz') || low.endsWith('.tar.gz')) chain.push('tar');
    else if (low.endsWith('.zip')) chain.push('zip');
  }
  const leaf = parts[parts.length - 1].toLowerCase();
  if (leaf.endsWith('.csv') || leaf.endsWith('.tsv') || leaf.endsWith('.psv')) {
    chain.push(leaf.endsWith('.tsv') ? 'tsv' : leaf.endsWith('.psv') ? 'psv' : 'csv');
  } else if (leaf.endsWith('.json')) {
    chain.push('json');
  }
  return chain.length >= 2 ? chain.join(' -> ') : null;
};

export const resolveArchiveFormatChain = (input: {
  fileFormat?: string | null;
  suggestedFormat?: string | null;
  objectName?: string | null;
  archiveEntriesSample?: string[] | null;
  outer?: string | null;
}): string | null => {
  const candidates: Array<string | null | undefined> = [input.fileFormat];
  if (input.archiveEntriesSample?.length) {
    const deepest = input.archiveEntriesSample.reduce((a, b) =>
      (a.split('/').length >= b.split('/').length ? a : b));
    candidates.push(formatChainFromArchiveMemberPath(deepest, input.outer ?? 'tar'));
  }
  candidates.push(inferFormatChainFromObjectName(input.objectName, input.outer ?? undefined));

  let best: string | null = null;
  let bestDepth = 0;
  for (const candidate of candidates) {
    if (!candidate || !candidate.includes('->')) continue;
    const depth = chainDepth(candidate);
    if (depth > bestDepth) {
      best = candidate;
      bestDepth = depth;
    }
  }
  return best ?? input.fileFormat ?? input.suggestedFormat ?? null;
};

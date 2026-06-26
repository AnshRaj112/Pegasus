import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  RightOutlined, DatabaseOutlined, LeftOutlined,
} from '@ant-design/icons';
import { Api, MismatchSampleRow } from '../../../shared/api/Api';

type JsonIssueKind = 'value_mismatch' | 'missing_in_target' | 'extra_in_target';

type JsonIssueRow = {
  uid: string;
  kind: JsonIssueKind;
  jsonPath: string;
  parentPath: string;
  sourceValue: string | null;
  targetValue: string | null;
  sourceParent: unknown;
  targetParent: unknown;
  sourceSiblingKeys: Array<string | number>;
  targetSiblingKeys: Array<string | number>;
  sourceSiblings: unknown[];
  targetSiblings: unknown[];
};

const FETCH_BATCH = 5000;
const SKELETON_ROWS = 6;

const SkeletonBlock: React.FC<{ width?: string }> = ({ width = '100%' }) => (
  <div style={{ width, height: '14px', backgroundColor: '#e2e8f0', borderRadius: '4px', animation: 'json-snippet-pulse 1.5s ease-in-out infinite' }} />
);

const parseDetail = (raw: unknown): Record<string, unknown> | null => {
  if (!raw) return null;
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as Record<string, unknown>;
    } catch { /* ignore */ }
  }
  return null;
};

const toKind = (mismatchType: string): JsonIssueKind => {
  if (mismatchType === 'missing_in_target') return 'missing_in_target';
  if (mismatchType === 'extra_in_target') return 'extra_in_target';
  return 'value_mismatch';
};

const formatValue = (value: unknown): string => {
  if (value == null) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const parseJsonValue = (raw: string | null): unknown => {
  if (raw == null || raw === '—') return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed) as unknown;
  } catch {
    return raw;
  }
};

const formatFieldValue = (value: unknown): string => {
  if (value == null) return '—';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `[${value.length}]`;
  if (typeof value === 'object') {
    const keys = Object.keys(value as Record<string, unknown>);
    if (keys.length === 0) return '{}';
    if (keys.length <= 2) {
      return keys
        .map((k) => `${k} ${formatFieldValue((value as Record<string, unknown>)[k])}`)
        .join('  ');
    }
    return `{${keys.length}}`;
  }
  return String(value);
};

const splitPath = (path: string): string[] => {
  if (!path || path === '$') return [];
  const tokens: string[] = [];
  const re = /([^.\[\]]+)|\[(\d+)\]/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(path)) !== null) {
    tokens.push(match[1] ?? `[${match[2]}]`);
  }
  return tokens;
};

const leafKey = (jsonPath: string): string => {
  const tokens = splitPath(jsonPath);
  return tokens.length ? tokens[tokens.length - 1]! : '$';
};

type AlignedField = {
  key: string;
  source: string | null;
  target: string | null;
  highlight: boolean;
};

const IDENTITY_KEYS = ['field', 'id', 'key', 'name', 'uid'] as const;

const objectFromRaw = (raw: string | null): Record<string, unknown> | null => {
  const value = parseJsonValue(raw);
  if (value != null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
};

const findIdentityKey = (obj: Record<string, unknown>): string | null => {
  for (const key of IDENTITY_KEYS) {
    if (obj[key] != null && String(obj[key]) !== '') return key;
  }
  return null;
};

const dictParent = (parent: unknown): Record<string, unknown> | null => {
  if (parent != null && typeof parent === 'object' && !Array.isArray(parent)) {
    return parent as Record<string, unknown>;
  }
  return null;
};

const resolveSideObject = (
  row: JsonIssueRow,
  side: 'source' | 'target',
): Record<string, unknown> | null => {
  const rawValue = side === 'source' ? row.sourceValue : row.targetValue;
  const fromValue = objectFromRaw(rawValue);
  if (fromValue) return fromValue;

  const isRoot = !row.parentPath || row.parentPath === '$';
  const leaf = leafKey(row.jsonPath);
  const scalar = parseJsonValue(rawValue);
  const parent = dictParent(side === 'source' ? row.sourceParent : row.targetParent);

  if (scalar != null && (typeof scalar !== 'object' || Array.isArray(scalar))) {
    if (isRoot) return { [leaf]: scalar };
    if (parent) return parent;
    return { [leaf]: scalar };
  }

  if (parent) return parent;
  return null;
};

const findCounterpartInSiblings = (
  row: JsonIssueRow,
  fromSide: 'source' | 'target',
  selfObj: Record<string, unknown>,
): Record<string, unknown> | null => {
  const toSide = fromSide === 'source' ? 'target' : 'source';
  const siblings = toSide === 'source' ? row.sourceSiblings : row.targetSiblings;
  if (!Array.isArray(siblings)) return null;

  const idKey = findIdentityKey(selfObj);
  if (!idKey) return null;
  const idVal = String(selfObj[idKey]);
  for (const sibling of siblings) {
    if (sibling == null || typeof sibling !== 'object' || Array.isArray(sibling)) continue;
    const candidate = sibling as Record<string, unknown>;
    if (String(candidate[idKey]) === idVal) return candidate;
  }
  return null;
};

type AlignedResult = {
  fields: AlignedField[];
  hasSource: boolean;
  hasTarget: boolean;
};

const buildAlignedFieldRows = (row: JsonIssueRow): AlignedResult => {
  let srcObj = resolveSideObject(row, 'source');
  let tgtObj = resolveSideObject(row, 'target');

  if (srcObj && !tgtObj) tgtObj = findCounterpartInSiblings(row, 'source', srcObj);
  if (tgtObj && !srcObj) srcObj = findCounterpartInSiblings(row, 'target', tgtObj);

  const keys: string[] = [];
  const addKeys = (obj: Record<string, unknown> | null) => {
    if (!obj) return;
    for (const k of Object.keys(obj)) {
      if (!keys.includes(k)) keys.push(k);
    }
  };
  addKeys(srcObj);
  addKeys(tgtObj);

  if (!keys.length) return { fields: [], hasSource: false, hasTarget: false };

  const fields = keys.map((key) => {
    const source = srcObj ? formatFieldValue(srcObj[key]) : null;
    const target = tgtObj ? formatFieldValue(tgtObj[key]) : null;
    const highlight = source !== target;
    return { key, source, target, highlight };
  });

  return {
    fields,
    hasSource: srcObj != null,
    hasTarget: tgtObj != null,
  };
};

const rowIdentityKey = (row: JsonIssueRow): string | null => {
  const obj = objectFromRaw(row.sourceValue) ?? objectFromRaw(row.targetValue);
  if (!obj) return null;
  const idKey = findIdentityKey(obj);
  if (!idKey) return null;
  return `${row.uid}::${row.parentPath}::${idKey}=${String(obj[idKey])}`;
};

const mergePairedIssues = (rows: JsonIssueRow[]): JsonIssueRow[] => {
  const pending = new Map<string, JsonIssueRow>();
  const merged: JsonIssueRow[] = [];

  for (const row of rows) {
    const identity = rowIdentityKey(row);
    if (!identity || (row.kind !== 'missing_in_target' && row.kind !== 'extra_in_target')) {
      merged.push(row);
      continue;
    }

    const existing = pending.get(identity);
    if (!existing) {
      pending.set(identity, row);
      continue;
    }

    const missing = existing.kind === 'missing_in_target' ? existing : row;
    const extra = existing.kind === 'extra_in_target' ? existing : row;
    merged.push({
      uid: missing.uid,
      kind: 'value_mismatch',
      jsonPath: missing.jsonPath,
      parentPath: missing.parentPath,
      sourceValue: missing.sourceValue ?? extra.sourceValue,
      targetValue: extra.targetValue ?? missing.targetValue,
      sourceParent: missing.sourceParent ?? extra.sourceParent,
      targetParent: missing.targetParent ?? extra.targetParent,
      sourceSiblingKeys: missing.sourceSiblingKeys.length ? missing.sourceSiblingKeys : extra.sourceSiblingKeys,
      targetSiblingKeys: missing.targetSiblingKeys.length ? missing.targetSiblingKeys : extra.targetSiblingKeys,
      sourceSiblings: missing.sourceSiblings.length ? missing.sourceSiblings : extra.sourceSiblings,
      targetSiblings: missing.targetSiblings.length ? missing.targetSiblings : extra.targetSiblings,
    });
    pending.delete(identity);
  }

  merged.push(...pending.values());
  return merged;
};

const buildJsonIssues = (items: MismatchSampleRow[]): JsonIssueRow[] => {
  const rows: JsonIssueRow[] = [];
  for (const item of items) {
    if (item.mismatch_type === 'value_match') continue;
    const detail = parseDetail(item.row_detail);
    const jsonPath = String(detail?.json_path ?? item.column_name ?? item.uid ?? '—');
    const parentPath = String(detail?.parent_path ?? '$');
    rows.push({
      uid: item.uid,
      kind: toKind(item.mismatch_type),
      jsonPath,
      parentPath,
      sourceValue: item.source_value ?? (detail?.source_value != null ? formatValue(detail.source_value) : null),
      targetValue: item.target_value ?? (detail?.target_value != null ? formatValue(detail.target_value) : null),
      sourceParent: detail?.source_parent ?? null,
      targetParent: detail?.target_parent ?? null,
      sourceSiblingKeys: Array.isArray(detail?.source_sibling_keys) ? detail!.source_sibling_keys as Array<string | number> : [],
      targetSiblingKeys: Array.isArray(detail?.target_sibling_keys) ? detail!.target_sibling_keys as Array<string | number> : [],
      sourceSiblings: Array.isArray(detail?.source_siblings) ? detail!.source_siblings as unknown[] : [],
      targetSiblings: Array.isArray(detail?.target_siblings) ? detail!.target_siblings as unknown[] : [],
    });
  }
  return mergePairedIssues(rows);
};

const PathContext: React.FC<{ path: string }> = ({ path }) => {
  const tokens = splitPath(path);
  if (!tokens.length) {
    return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: '#94a3b8' }}>$</span>;
  }
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: '#94a3b8' }}>
      {tokens.join(' → ')}
    </span>
  );
};

const SiblingHint: React.FC<{
  keys: Array<string | number>;
  siblings: unknown[];
  side: 'source' | 'target';
}> = ({ keys, siblings, side }) => {
  if (siblings.length <= 1) return null;
  const tooltip = siblings
    .map((value, idx) => {
      const key = keys[idx] ?? idx;
      if (value != null && typeof value === 'object' && !Array.isArray(value)) {
        const fields = Object.entries(value as Record<string, unknown>)
          .map(([k, v]) => `${k} ${formatFieldValue(v)}`)
          .join('  ');
        return `${key}: ${fields}`;
      }
      return `${key}: ${formatFieldValue(value)}`;
    })
    .join('\n');

  return (
    <span
      title={tooltip}
      style={{
        fontSize: '11px',
        color: '#64748b',
        cursor: 'help',
        borderBottom: '1px dotted #94a3b8',
      }}
    >
      … {siblings.length} items in {side}
    </span>
  );
};

const FieldLine: React.FC<{
  fieldKey: string;
  value: string | null;
  highlight: boolean;
  absent?: boolean;
}> = ({ fieldKey, value, highlight, absent = false }) => (
  <div style={{
    display: 'grid',
    gridTemplateColumns: '72px 1fr',
    gap: '12px',
    padding: '5px 10px',
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    lineHeight: 1.5,
    backgroundColor: highlight ? '#fee2e2' : absent ? '#fff7ed' : 'transparent',
    color: highlight ? '#991b1b' : absent ? '#c2410c' : '#1b1b1c',
    fontWeight: highlight ? 600 : 400,
    borderRadius: '4px',
  }}
  >
    <span style={{ color: highlight ? '#991b1b' : '#64748b' }}>{fieldKey}</span>
    <span>{value ?? '—'}</span>
  </div>
);

const kindLabel: Record<JsonIssueKind, string> = {
  value_mismatch: 'mismatch',
  missing_in_target: 'missing in target',
  extra_in_target: 'extra in target',
};

const kindColor: Record<JsonIssueKind, string> = {
  value_mismatch: '#991b1b',
  missing_in_target: '#c2410c',
  extra_in_target: '#c2410c',
};

const JsonIssuePair: React.FC<{ row: JsonIssueRow }> = ({ row }) => {
  const { fields, hasSource, hasTarget } = buildAlignedFieldRows(row);
  const siblingKeys = row.sourceSiblingKeys.length >= row.targetSiblingKeys.length
    ? row.sourceSiblingKeys
    : row.targetSiblingKeys;
  const siblings = row.sourceSiblings.length >= row.targetSiblings.length
    ? row.sourceSiblings
    : row.targetSiblings;
  const sourceAbsent = !hasSource;
  const targetAbsent = !hasTarget;

  return (
    <div style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid #f1f5f9' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
        <span style={{ fontSize: '11px', color: '#64748b' }}>
          UID: <span style={{ fontFamily: 'var(--font-mono)', color: '#1b1b1c' }}>{row.uid}</span>
        </span>
        <span style={{ color: '#cbd5e1' }}>|</span>
        <PathContext path={row.jsonPath} />
        <span style={{
          fontSize: '10px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: kindColor[row.kind],
          backgroundColor: row.kind === 'value_mismatch' ? '#fee2e2' : '#fff7ed',
          padding: '2px 6px',
          borderRadius: '4px',
        }}
        >
          {kindLabel[row.kind]}
        </span>
        <SiblingHint keys={siblingKeys} siblings={siblings} side="source" />
      </div>

      {fields.length === 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div style={{
            padding: '10px 12px',
            borderRadius: '6px',
            border: '1px solid #fed7aa',
            backgroundColor: sourceAbsent ? '#fff7ed' : '#f8fafc',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            color: '#94a3b8',
            fontStyle: 'italic',
          }}
          >
            {sourceAbsent ? 'not present' : formatValue(row.sourceValue)}
          </div>
          <div style={{
            padding: '10px 12px',
            borderRadius: '6px',
            border: '1px solid #fed7aa',
            backgroundColor: targetAbsent ? '#fff7ed' : '#f8fafc',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            color: '#94a3b8',
            fontStyle: 'italic',
          }}
          >
            {targetAbsent ? 'not present' : formatValue(row.targetValue)}
          </div>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
          backgroundColor: '#f8fafc',
          borderRadius: '6px',
          border: '1px solid #e2e8f0',
          padding: '6px 4px',
        }}
        >
          <div>
            {fields.map(({ key, source, highlight }) => (
              <FieldLine
                key={`src-${key}`}
                fieldKey={key}
                value={sourceAbsent ? null : source}
                highlight={highlight}
                absent={sourceAbsent}
              />
            ))}
          </div>
          <div>
            {fields.map(({ key, target, highlight }) => (
              <FieldLine
                key={`tgt-${key}`}
                fieldKey={key}
                value={targetAbsent ? null : target}
                highlight={highlight}
                absent={targetAbsent}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const JsonSnippetComparison: React.FC = () => {
  const navigate = useNavigate();
  const { mappingId, runId } = useParams<{ mappingId: string; runId: string }>();
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [rowsLoading, setRowsLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [allItems, setAllItems] = useState<MismatchSampleRow[]>([]);
  const [sourceLabel, setSourceLabel] = useState('Source');
  const [targetLabel, setTargetLabel] = useState('Target');
  const [rowPage, setRowPage] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    (async () => {
      setSummaryLoading(true);
      setRowsLoading(true);
      setError(null);
      try {
        const { data: detail } = await Api.getValidationHistoryRun(runId);
        if (cancelled) return;
        setSourceLabel(detail.source_path ?? detail.source_filename ?? 'Source');
        setTargetLabel(detail.target_path ?? detail.target_filename ?? 'Target');
        setSummaryLoading(false);
        setLoadProgress('Loading JSON mismatch paths…');

        let offset = 0;
        const collected: MismatchSampleRow[] = [];
        for (;;) {
          const { data: page } = await Api.getValidationMismatches(runId, { limit: FETCH_BATCH, offset });
          if (cancelled) return;
          collected.push(...page.items);
          setAllItems([...collected]);
          if (collected.length >= page.total || page.items.length < FETCH_BATCH) break;
          offset += FETCH_BATCH;
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load JSON snippet');
      } finally {
        if (!cancelled) {
          setSummaryLoading(false);
          setRowsLoading(false);
          setLoadProgress('');
        }
      }
    })();
    return () => { cancelled = true; };
  }, [runId]);

  const issues = useMemo(() => buildJsonIssues(allItems), [allItems]);
  const totalPages = Math.max(1, Math.ceil(issues.length / itemsPerPage));
  const pageRows = issues.slice(rowPage * itemsPerPage, (rowPage + 1) * itemsPerPage);
  const pairLabel = mappingId ?? sourceLabel.split('/').pop() ?? 'Report';
  const isLoading = summaryLoading || rowsLoading;

  useEffect(() => {
    if (rowPage >= totalPages) setRowPage(Math.max(0, totalPages - 1));
  }, [rowPage, totalPages]);

  if (error) return <div style={{ padding: '24px', color: '#ba1a1a' }}>{error}</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <style>{`@keyframes json-snippet-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }`}</style>
      {loadProgress && (
        <p style={{ margin: '0 0 12px 0', fontSize: '12px', color: '#64748b' }}>{loadProgress}</p>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '13px' }}>
          <span style={{ cursor: 'pointer' }} onClick={() => navigate('/reports')}>Reports</span>
          <RightOutlined style={{ fontSize: '10px' }} />
          <span style={{ backgroundColor: '#f0eded', padding: '2px 6px', borderRadius: '4px', fontFamily: 'var(--font-mono)' }}>{pairLabel}</span>
          <RightOutlined style={{ fontSize: '10px' }} />
          <span style={{ backgroundColor: '#f0eded', padding: '2px 6px', borderRadius: '4px', fontFamily: 'var(--font-mono)' }}>{runId}</span>
          <RightOutlined style={{ fontSize: '10px' }} />
          <span style={{ color: '#1b1b1c', fontWeight: 600 }}>JSON Snippet</span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '16px', marginBottom: '12px', fontSize: '11px', color: '#64748b', flexWrap: 'wrap' }}>
        <span><span style={{ color: '#991b1b', fontWeight: 600 }}>Red row</span> = field value differs</span>
        <span><span style={{ color: '#c2410c', fontWeight: 600 }}>Orange</span> = missing / extra node</span>
        <span>Each field is shown on its own line, source aligned with target</span>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', minHeight: '400px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
          <div style={{ backgroundColor: '#1e293b', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#fff' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Source &gt; {sourceLabel}</span>
          </div>
          <div style={{ backgroundColor: '#e2e8f0', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#1b1b1c' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Target &gt; {targetLabel}</span>
          </div>
        </div>
        <div style={{ overflow: 'auto', flex: 1, padding: '12px 16px' }}>
          {isLoading ? (
            Array.from({ length: SKELETON_ROWS }, (_, i) => <div key={i} style={{ marginBottom: '12px' }}><SkeletonBlock /></div>)
          ) : pageRows.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>No JSON mismatches for this run.</div>
          ) : pageRows.map((row) => (
            <JsonIssuePair key={`${row.uid}-${row.jsonPath}`} row={row} />
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 0', borderTop: '1px solid #e2e8f0', marginTop: '16px' }}>
        <span style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic' }}>
          Each field on its own row — source on the left, target on the right, aligned one-to-one.
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#64748b' }}>
            Rows per page:
            <select value={itemsPerPage} onChange={(e) => setItemsPerPage(Number(e.target.value))} style={{ border: 'none', fontWeight: 600, outline: 'none', backgroundColor: 'transparent' }}>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', backgroundColor: '#f0eded', padding: '4px 8px', borderRadius: '6px' }}>
            <LeftOutlined style={{ fontSize: '12px', color: rowPage <= 0 ? '#a0aabf' : '#414755', cursor: rowPage <= 0 ? 'not-allowed' : 'pointer' }} onClick={() => rowPage > 0 && setRowPage((p) => p - 1)} />
            <span style={{ fontSize: '13px', fontWeight: 600 }}>
              {isLoading ? '—' : (issues.length ? rowPage + 1 : 0)}
              <span style={{ color: '#a0aabf', margin: '0 4px', fontWeight: 400 }}>/</span>
              {isLoading ? '—' : totalPages}
            </span>
            <RightOutlined style={{ fontSize: '12px', color: rowPage >= totalPages - 1 ? '#a0aabf' : '#414755', cursor: rowPage >= totalPages - 1 ? 'not-allowed' : 'pointer' }} onClick={() => rowPage < totalPages - 1 && setRowPage((p) => p + 1)} />
          </div>
        </div>
      </div>
    </div>
  );
};

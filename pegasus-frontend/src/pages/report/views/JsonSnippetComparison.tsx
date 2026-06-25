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
  return rows;
};

const SiblingEllipsis: React.FC<{
  keys: Array<string | number>;
  siblings: unknown[];
  side: 'source' | 'target';
}> = ({ keys, siblings, side }) => {
  if (!siblings.length) return null;
  const tooltip = siblings
    .map((value, idx) => {
      const key = keys[idx] ?? idx;
      return `${key}: ${formatValue(value)}`;
    })
    .join('\n');

  return (
    <span
      title={tooltip}
      style={{
        color: '#64748b',
        cursor: 'help',
        borderBottom: '1px dotted #94a3b8',
        fontFamily: 'var(--font-mono)',
        fontSize: '12px',
        padding: '0 2px',
      }}
    >
      … ({siblings.length} in {side})
    </span>
  );
};

const PathBreadcrumb: React.FC<{
  path: string;
  highlightLeaf?: boolean;
  kind?: JsonIssueKind;
}> = ({ path, highlightLeaf = false, kind }) => {
  const tokens = splitPath(path);
  if (!tokens.length) {
    return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#64748b' }}>$</span>;
  }

  const leafStyle: React.CSSProperties = highlightLeaf
    ? {
      color: kind === 'value_mismatch' ? '#991b1b' : '#c2410c',
      fontWeight: 700,
      backgroundColor: kind === 'value_mismatch' ? '#fee2e2' : '#fff7ed',
      padding: '1px 4px',
      borderRadius: '4px',
    }
    : { color: '#1b1b1c', fontWeight: 600 };

  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', display: 'inline-flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
      {tokens.map((token, idx) => (
        <React.Fragment key={`${token}-${idx}`}>
          {idx > 0 && <span style={{ color: '#94a3b8' }}>→</span>}
          <span style={idx === tokens.length - 1 && highlightLeaf ? leafStyle : { color: '#414755' }}>
            {token}
          </span>
        </React.Fragment>
      ))}
    </span>
  );
};

const ParentContextLine: React.FC<{
  row: JsonIssueRow;
  side: 'source' | 'target';
}> = ({ row, side }) => {
  const parent = side === 'source' ? row.sourceParent : row.targetParent;
  const siblingKeys = side === 'source' ? row.sourceSiblingKeys : row.targetSiblingKeys;
  const siblings = side === 'source' ? row.sourceSiblings : row.targetSiblings;
  const hasParent = parent != null;
  const parentLabel = row.parentPath && row.parentPath !== '$' ? row.parentPath : '$';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <PathBreadcrumb path={parentLabel} />
        {siblings.length > 1 && (
          <>
            <span style={{ color: '#94a3b8' }}>→</span>
            <SiblingEllipsis keys={siblingKeys} siblings={siblings} side={side} />
          </>
        )}
        <span style={{ color: '#94a3b8' }}>→</span>
        <PathBreadcrumb path={row.jsonPath} highlightLeaf kind={row.kind} />
      </div>
      {hasParent && (
        <pre style={{
          margin: 0,
          padding: '10px 12px',
          backgroundColor: '#f8fafc',
          borderRadius: '6px',
          border: '1px solid #e2e8f0',
          fontSize: '12px',
          fontFamily: 'var(--font-mono)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: '160px',
          overflow: 'auto',
        }}
        >
          {JSON.stringify(parent, null, 2)}
        </pre>
      )}
      <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
        <span style={{ color: '#64748b' }}>At path: </span>
        <strong style={{ color: side === 'source' ? '#1e293b' : '#414755' }}>
          {side === 'source' ? (row.sourceValue ?? '—') : (row.targetValue ?? '—')}
        </strong>
      </div>
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
        <span><span style={{ color: '#991b1b', fontWeight: 600 }}>Red path</span> = value mismatch</span>
        <span><span style={{ color: '#c2410c', fontWeight: 600 }}>Orange path</span> = missing / extra node</span>
        <span>Hover <span style={{ fontFamily: 'var(--font-mono)' }}>…</span> to see sibling keys/items under the parent</span>
      </div>

      <div style={{ display: 'flex', gap: '24px', flex: 1, minHeight: '400px', overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', minWidth: 0 }}>
          <div style={{ backgroundColor: '#1e293b', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#fff' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Source &gt; {sourceLabel}</span>
          </div>
          <div style={{ overflow: 'auto', flex: 1, padding: '12px' }}>
            {isLoading ? (
              Array.from({ length: SKELETON_ROWS }, (_, i) => <div key={i} style={{ marginBottom: '12px' }}><SkeletonBlock /></div>)
            ) : pageRows.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>No JSON mismatches for this run.</div>
            ) : pageRows.map((row) => (
              <div key={`src-${row.uid}-${row.jsonPath}`} style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid #f1f5f9' }}>
                <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>UID: <span style={{ fontFamily: 'var(--font-mono)', color: '#1b1b1c' }}>{row.uid}</span></div>
                <ParentContextLine row={row} side="source" />
              </div>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', minWidth: 0 }}>
          <div style={{ backgroundColor: '#e2e8f0', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#1b1b1c' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Target &gt; {targetLabel}</span>
          </div>
          <div style={{ overflow: 'auto', flex: 1, padding: '12px' }}>
            {isLoading ? (
              Array.from({ length: SKELETON_ROWS }, (_, i) => <div key={i} style={{ marginBottom: '12px' }}><SkeletonBlock /></div>)
            ) : pageRows.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>No JSON mismatches for this run.</div>
            ) : pageRows.map((row) => (
              <div key={`tgt-${row.uid}-${row.jsonPath}`} style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid #f1f5f9' }}>
                <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>UID: <span style={{ fontFamily: 'var(--font-mono)', color: '#1b1b1c' }}>{row.uid}</span></div>
                <ParentContextLine row={row} side="target" />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 0', borderTop: '1px solid #e2e8f0', marginTop: '16px' }}>
        <span style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic' }}>
          Parent path → … (hover) → mismatch path. Siblings under the parent are collapsed until hovered.
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

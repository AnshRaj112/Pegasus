import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DownloadOutlined, RightOutlined, DatabaseOutlined, LeftOutlined } from '@ant-design/icons';
import { Api, type MismatchSampleRow } from '../../../shared/api/Api';
import { downloadSnippetCsv, downloadSnippetPdf, downloadSnippetXlsx } from '../snippetExport';

type RowStatus = 'match' | 'mismatch' | 'extra_source' | 'missing_target';

type SnippetRow = {
  uid: string;
  status: RowStatus;
  source: Record<string, string>;
  target: Record<string, string>;
  mismatchColumns: Set<string>;
};

const COLS_PER_PAGE = 10;
const EMPTY = '—';
const FETCH_BATCH = 5000;
const SKELETON_ROWS = 8;

const SkeletonCell: React.FC<{ width?: string }> = ({ width = '100%' }) => (
  <div style={{ width, height: '14px', backgroundColor: '#e2e8f0', borderRadius: '4px', animation: 'snippet-skeleton-pulse 1.5s ease-in-out infinite' }} />
);

const SnippetSkeletonRows: React.FC<{ colCount: number; rows?: number }> = ({ colCount, rows = SKELETON_ROWS }) => (
  <>
    {Array.from({ length: rows }, (_, i) => (
      <tr key={`skeleton-${i}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
        {Array.from({ length: colCount }, (_, j) => (
          <td key={j} style={{ padding: '12px 16px' }}>
            <SkeletonCell width={j === 0 ? '72px' : `${50 + ((i + j) % 4) * 10}%`} />
          </td>
        ))}
      </tr>
    ))}
  </>
);

const parseDetail = (raw: unknown): Record<string, unknown> | null => {
  if (!raw) return null;
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      if (typeof parsed === 'string') return parseDetail(parsed);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as Record<string, unknown>;
    } catch { /* ignore */ }
  }
  return null;
};

const pickCell = (val: string | null | undefined, existing: string): string => {
  if (val != null && val !== '' && val !== '__NULL__') return val;
  return existing;
};

const mergeRecord = (
  cells: Record<string, string>,
  rec: unknown,
  columns: string[],
) => {
  if (!rec || typeof rec !== 'object' || Array.isArray(rec)) return;
  const obj = rec as Record<string, unknown>;
  for (const col of columns) {
    const v = obj[col];
    if (v != null && String(v) !== '' && String(v) !== '__NULL__') cells[col] = String(v);
  }
};

const emptyCells = (columns: string[]): Record<string, string> =>
  Object.fromEntries(columns.map((c) => [c, EMPTY]));

const buildSnippetRows = (items: MismatchSampleRow[], columns: string[]): SnippetRow[] => {
  const byUid = new Map<string, SnippetRow>();

  for (const item of items) {
    let row = byUid.get(item.uid);
    if (!row) {
      let status: RowStatus = 'mismatch';
      if (item.mismatch_type === 'missing_in_target') status = 'extra_source';
      else if (item.mismatch_type === 'extra_in_target') status = 'missing_target';
      row = {
        uid: item.uid,
        status,
        source: emptyCells(columns),
        target: emptyCells(columns),
        mismatchColumns: new Set(),
      };
      byUid.set(item.uid, row);
    }

    const detail = parseDetail(item.row_detail);
    mergeRecord(row.source, detail?.source_record, columns);
    mergeRecord(row.target, detail?.target_record, columns);

    if (item.mismatch_type === 'value_mismatch' && item.column_name) {
      row.mismatchColumns.add(item.column_name);
      row.source[item.column_name] = pickCell(item.source_value, row.source[item.column_name] ?? EMPTY);
      row.target[item.column_name] = pickCell(item.target_value, row.target[item.column_name] ?? EMPTY);
      row.status = 'mismatch';
    } else if (item.mismatch_type === 'missing_in_target') {
      row.status = 'extra_source';
    } else if (item.mismatch_type === 'extra_in_target') {
      row.status = 'missing_target';
    }
  }

  return [...byUid.values()];
};

/** UID has any row-level or value-level issue (not scoped to visible columns). */
const rowHasAnyIssue = (row: SnippetRow): boolean => {
  if (row.status === 'extra_source' || row.status === 'missing_target') return true;
  return row.mismatchColumns.size > 0;
};

export const SnippetComparison: React.FC = () => {
  const navigate = useNavigate();
  const { mappingId, runId } = useParams<{ mappingId: string; runId: string }>();
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [rowsLoading, setRowsLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [expectedMismatchTotal, setExpectedMismatchTotal] = useState(0);
  const [columns, setColumns] = useState<string[]>([]);
  const [allItems, setAllItems] = useState<MismatchSampleRow[]>([]);
  const [sourceLabel, setSourceLabel] = useState('Source');
  const [targetLabel, setTargetLabel] = useState('Target');
  const [colPage, setColPage] = useState(0);
  const [rowPage, setRowPage] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const sourceRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    (async () => {
      setSummaryLoading(true);
      setRowsLoading(true);
      setError(null);
      setLoadProgress('Loading run summary…');
      try {
        const { data: detail } = await Api.getValidationHistoryRun(runId);
        if (cancelled) return;
        const cols = detail.compared_columns?.length ? detail.compared_columns : [];
        setColumns(cols);
        setSourceLabel(detail.source_path ?? detail.source_filename ?? 'Source');
        setTargetLabel(detail.target_path ?? detail.target_filename ?? 'Target');
        const mc = detail.mismatch_counts;
        const expected = mc.missing_in_target + mc.extra_in_target + mc.value_mismatch;
        setExpectedMismatchTotal(expected);
        setColPage(0);
        setRowPage(0);
        setSummaryLoading(false);
        setLoadProgress('Loading mismatch rows…');

        let offset = 0;
        const collected: MismatchSampleRow[] = [];
        let pageTotal = 0;
        for (let attempt = 0; attempt < 30; attempt += 1) {
          offset = 0;
          collected.length = 0;
          for (;;) {
            const { data: page } = await Api.getValidationMismatches(runId, { limit: FETCH_BATCH, offset });
            if (cancelled) return;
            pageTotal = page.total;
            collected.push(...page.items);
            setAllItems([...collected]);
            setLoadProgress(
              page.total > collected.length
                ? `Loaded ${collected.length.toLocaleString()} / ${page.total.toLocaleString()} mismatch rows…`
                : '',
            );
            if (collected.length >= page.total || page.items.length < FETCH_BATCH) break;
            offset += FETCH_BATCH;
          }
          if (collected.length > 0 || expected === 0 || pageTotal > 0) break;
          setLoadProgress('Waiting for mismatch rows to finish saving…');
          await new Promise((r) => setTimeout(r, 2000));
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load snippet');
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

  const allRows = useMemo(() => buildSnippetRows(allItems, columns), [allItems, columns]);

  const issueRows = useMemo(() => allRows.filter(rowHasAnyIssue), [allRows]);

  const totalColPages = Math.max(1, Math.ceil(columns.length / COLS_PER_PAGE));
  const visibleCols = columns.slice(colPage * COLS_PER_PAGE, (colPage + 1) * COLS_PER_PAGE);
  const displayCols = ['uid', ...visibleCols];

  const totalRowPages = Math.max(1, Math.ceil(issueRows.length / itemsPerPage));
  const pageRows = issueRows.slice(rowPage * itemsPerPage, (rowPage + 1) * itemsPerPage);

  useEffect(() => {
    setRowPage(0);
  }, [colPage, itemsPerPage]);

  useEffect(() => {
    if (rowPage >= totalRowPages) setRowPage(Math.max(0, totalRowPages - 1));
  }, [rowPage, totalRowPages]);

  const pairLabel = mappingId ?? sourceLabel.split('/').pop() ?? 'Report';

  const handleSourceScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (targetRef.current) {
      targetRef.current.scrollTop = e.currentTarget.scrollTop;
      targetRef.current.scrollLeft = e.currentTarget.scrollLeft;
    }
  };

  const handleTargetScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (sourceRef.current) {
      sourceRef.current.scrollTop = e.currentTarget.scrollTop;
      sourceRef.current.scrollLeft = e.currentTarget.scrollLeft;
    }
  };

  const exportRows = () => pageRows.map((row) => ({
    uid: row.uid,
    status: row.status,
    columns: visibleCols,
    source: visibleCols.map((c) => row.source[c] ?? EMPTY),
    target: visibleCols.map((c) => row.target[c] ?? EMPTY),
  }));

  const cellStyle = (row: SnippetRow, side: 'source' | 'target', col: string): React.CSSProperties => {
    if (col === 'uid') return { fontWeight: 600 };
    const src = row.source[col] ?? EMPTY;
    const tgt = row.target[col] ?? EMPTY;
    const isMismatch = row.mismatchColumns.has(col) && visibleCols.includes(col);
    const isRowIssue = row.status === 'extra_source' || row.status === 'missing_target';

    if (isMismatch) {
      return { backgroundColor: '#fee2e2', color: '#991b1b', fontWeight: 600 };
    }
    if (isRowIssue) {
      const hasValue = side === 'source' ? src !== EMPTY : tgt !== EMPTY;
      return {
        backgroundColor: '#fff7ed',
        color: hasValue ? '#c2410c' : '#94a3b8',
      };
    }
    if (src !== EMPTY && tgt !== EMPTY && src === tgt) {
      return { color: '#166534' };
    }
    return { color: '#1b1b1c' };
  };

  const rowBg = (row: SnippetRow) =>
    (row.status === 'extra_source' || row.status === 'missing_target' ? '#fff7ed' : '#fff');

  const renderCells = (row: SnippetRow, side: 'source' | 'target') => displayCols.map((col) => {
    const cell = col === 'uid' ? row.uid : (row[side][col] ?? EMPTY);
    return (
      <td key={`${side}-${col}`} style={{
        padding: '12px 16px',
        fontSize: '13px',
        fontFamily: 'var(--font-mono)',
        ...cellStyle(row, side, col),
      }}>
        {cell}
      </td>
    );
  });

  const isDataLoading = summaryLoading || rowsLoading;
  const skeletonColCount = displayCols.length || COLS_PER_PAGE + 1;

  if (error) return <div style={{ padding: '24px', color: '#ba1a1a' }}>{error}</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <style>{`@keyframes snippet-skeleton-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }`}</style>
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
          <span style={{ color: '#1b1b1c', fontWeight: 600 }}>Snippet</span>
        </div>
        <div style={{ position: 'relative' }}>
          <button type="button" onClick={() => setDownloadOpen((o) => !o)} style={{ backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '8px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer' }}>
            <DownloadOutlined /> Download Snippet
          </button>
          {downloadOpen && (
            <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: '4px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', zIndex: 20, minWidth: '140px' }}>
              {(['CSV', 'XLSX', 'PDF'] as const).map((fmt) => (
                <button key={fmt} type="button" onClick={() => {
                  setDownloadOpen(false);
                  const base = `snippet-${runId}-cols${colPage + 1}`;
                  const data = exportRows();
                  if (fmt === 'CSV') downloadSnippetCsv(data, visibleCols, `${base}.csv`);
                  else if (fmt === 'XLSX') downloadSnippetXlsx(data, visibleCols, `${base}.xlsx`);
                  else downloadSnippetPdf(data, visibleCols, `Snippet ${runId}`);
                }} style={{ display: 'block', width: '100%', textAlign: 'left', padding: '10px 14px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '13px' }}>
                  {fmt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '12px', color: '#64748b' }}>
          Columns {columns.length ? colPage * COLS_PER_PAGE + 1 : 0}–{Math.min((colPage + 1) * COLS_PER_PAGE, columns.length)} of {columns.length}
        </span>
        <button type="button" disabled={colPage <= 0} onClick={() => setColPage((p) => p - 1)} style={{ padding: '4px 10px', fontSize: '12px', cursor: colPage <= 0 ? 'not-allowed' : 'pointer' }}>← Prev cols</button>
        <button type="button" disabled={colPage >= totalColPages - 1} onClick={() => setColPage((p) => p + 1)} style={{ padding: '4px 10px', fontSize: '12px', cursor: colPage >= totalColPages - 1 ? 'not-allowed' : 'pointer' }}>Next cols →</button>
        <span style={{ fontSize: '12px', color: '#64748b' }}>
          {isDataLoading ? 'Loading…' : `${issueRows.length.toLocaleString()} UID(s) with issues · red cells are mismatches in the visible column window`}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', fontSize: '11px', color: '#64748b' }}>
        <span><span style={{ color: '#166534', fontWeight: 600 }}>Green</span> = matching</span>
        <span><span style={{ color: '#991b1b', fontWeight: 600 }}>Red</span> = mismatch</span>
        <span><span style={{ color: '#c2410c', fontWeight: 600 }}>Orange</span> = missing / extra row</span>
      </div>

      <div style={{ display: 'flex', gap: '24px', flex: 1, minHeight: '400px', overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', minWidth: 0 }}>
          <div style={{ backgroundColor: '#1e293b', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#fff' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Source &gt; {sourceLabel}</span>
          </div>
          <div ref={sourceRef} onScroll={handleSourceScroll} style={{ overflow: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', whiteSpace: 'nowrap' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', zIndex: 10 }}>
                <tr>
                  {isDataLoading && displayCols.length === 0
                    ? Array.from({ length: skeletonColCount }, (_, i) => (
                      <th key={i} style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#414755' }}>
                        {i === 0 ? 'UID' : <SkeletonCell width={`${40 + (i % 3) * 15}%`} />}
                      </th>
                    ))
                    : displayCols.map((col) => <th key={col} style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#414755' }}>{col === 'uid' ? 'UID' : col}</th>)}
                </tr>
              </thead>
              <tbody>
                {isDataLoading ? (
                  <SnippetSkeletonRows colCount={skeletonColCount} />
                ) : pageRows.length === 0 ? (
                  <tr><td colSpan={displayCols.length || 1} style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
                    {expectedMismatchTotal > 0
                      ? 'Mismatch rows are still being saved or could not be loaded. Refresh in a few seconds.'
                      : 'No mismatches for this validation run.'}
                  </td></tr>
                ) : pageRows.map((row) => (
                  <tr key={`src-${row.uid}`} style={{ backgroundColor: rowBg(row), borderBottom: '1px solid #f1f5f9' }}>
                    {renderCells(row, 'source')}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', minWidth: 0 }}>
          <div style={{ backgroundColor: '#e2e8f0', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#1b1b1c' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Target &gt; {targetLabel}</span>
          </div>
          <div ref={targetRef} onScroll={handleTargetScroll} style={{ overflow: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', whiteSpace: 'nowrap' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', zIndex: 10 }}>
                <tr>
                  {isDataLoading && displayCols.length === 0
                    ? Array.from({ length: skeletonColCount }, (_, i) => (
                      <th key={i} style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#414755' }}>
                        {i === 0 ? 'UID' : <SkeletonCell width={`${40 + (i % 3) * 15}%`} />}
                      </th>
                    ))
                    : displayCols.map((col) => <th key={col} style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#414755' }}>{col === 'uid' ? 'UID' : col}</th>)}
                </tr>
              </thead>
              <tbody>
                {isDataLoading ? (
                  <SnippetSkeletonRows colCount={skeletonColCount} />
                ) : pageRows.length === 0 ? (
                  <tr><td colSpan={displayCols.length || 1} style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
                    {expectedMismatchTotal > 0
                      ? 'Mismatch rows are still being saved or could not be loaded. Refresh in a few seconds.'
                      : 'No mismatches for this validation run.'}
                  </td></tr>
                ) : pageRows.map((row) => (
                  <tr key={`tgt-${row.uid}`} style={{ backgroundColor: rowBg(row), borderBottom: '1px solid #f1f5f9' }}>
                    {renderCells(row, 'target')}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 0', borderTop: '1px solid #e2e8f0', marginTop: '16px' }}>
        <span style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic' }}>
          Use “Next cols” to inspect mismatches in other columns. Row pages list every UID with a missing, extra, or value mismatch.
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
              {isDataLoading ? '—' : (issueRows.length ? rowPage + 1 : 0)}
              <span style={{ color: '#a0aabf', margin: '0 4px', fontWeight: 400 }}>/</span>
              {isDataLoading ? '—' : totalRowPages}
            </span>
            <RightOutlined style={{ fontSize: '12px', color: rowPage >= totalRowPages - 1 ? '#a0aabf' : '#414755', cursor: rowPage >= totalRowPages - 1 ? 'not-allowed' : 'pointer' }} onClick={() => rowPage < totalRowPages - 1 && setRowPage((p) => p + 1)} />
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DownloadOutlined, RightOutlined, DatabaseOutlined, LeftOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { MismatchSampleRow } from '../../../shared/api/Api';
import { useAppSelector } from '../../../redux/store';
import { downloadSnippetCsv, downloadSnippetPdf, downloadSnippetXlsx } from '../snippetExport';
import styles from './SnippetComparison.module.scss';

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
const SKELETON_ROWS = 8;

const SKELETON_WIDTH_CLASSES = [
  styles.skeletonW55,
  styles.skeletonW70,
  styles.skeletonW40,
  styles.skeletonW55,
];

const skeletonWidthClass = (colIdx: number, rowIdx: number): string => {
  if (colIdx === 0) return styles.skeletonW72;
  return SKELETON_WIDTH_CLASSES[(rowIdx + colIdx) % SKELETON_WIDTH_CLASSES.length];
};

const SkeletonCell: React.FC<{ colIdx: number; rowIdx?: number }> = ({ colIdx, rowIdx = 0 }) => (
  <div className={`${styles.skeleton} ${skeletonWidthClass(colIdx, rowIdx)}`} />
);

const SnippetSkeletonRows: React.FC<{ colCount: number; rows?: number }> = ({ colCount, rows = SKELETON_ROWS }) => (
  <>
    {Array.from({ length: rows }, (_, i) => (
      <tr key={`skeleton-${i}`} className={styles.skeletonRow}>
        {Array.from({ length: colCount }, (_, j) => (
          <td key={j} className={styles.td}>
            <SkeletonCell colIdx={j} rowIdx={i} />
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
    } else if (item.mismatch_type === 'value_match' && item.column_name) {
      row.source[item.column_name] = pickCell(item.source_value, row.source[item.column_name] ?? EMPTY);
      row.target[item.column_name] = pickCell(item.target_value, row.target[item.column_name] ?? EMPTY);
      row.status = 'match';
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
  if (row.status === 'match') return false;
  if (row.status === 'extra_source' || row.status === 'missing_target') return true;
  if (row.mismatchColumns.size > 0) return true;
  return row.status === 'mismatch';
};

/** Column values agree on both sides and are not flagged as a mismatch. */
const isMatchedCell = (row: SnippetRow, col: string): boolean => {
  if (row.mismatchColumns.has(col)) return false;
  if (row.status === 'extra_source' || row.status === 'missing_target') return false;
  const src = row.source[col] ?? EMPTY;
  const tgt = row.target[col] ?? EMPTY;
  return src === tgt;
};

export const SnippetComparison: React.FC = () => {
  const navigate = useNavigate();
  const { mappingId, runId } = useParams<{ mappingId: string; runId: string }>();
  const historyRunState = useAppSelector((state) => state.report.historyRunState);
  const mismatchesState = useAppSelector((state) => state.report.mismatchesState);

  const [expectedMismatchTotal, setExpectedMismatchTotal] = useState(0);
  const [columns, setColumns] = useState<string[]>([]);
  const [sourceLabel, setSourceLabel] = useState('Source');
  const [targetLabel, setTargetLabel] = useState('Target');
  const [colPage, setColPage] = useState(0);
  const [rowPage, setRowPage] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [showMatchedOnly, setShowMatchedOnly] = useState(false);
  const [cleanRun, setCleanRun] = useState(false);
  const sourceRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef<HTMLDivElement>(null);

  const runReady = Boolean(runId && historyRunState.runId === runId);
  const mismatchesReady = Boolean(runId && mismatchesState.runId === runId);
  const summaryLoading = !runReady || historyRunState.isFetching;
  const rowsLoading = !mismatchesReady || mismatchesState.isFetching || !mismatchesState.isComplete;
  const loadProgress = mismatchesReady ? mismatchesState.progressMessage : 'Loading run summary…';
  const error = (runReady && historyRunState.error)
    || (mismatchesReady && mismatchesState.error)
    || null;
  const allItems = mismatchesReady ? mismatchesState.items : [];

  useEffect(() => {
    if (!runReady || !historyRunState.data) return;

    const detail = historyRunState.data;
    const cols = detail.compared_columns?.length ? detail.compared_columns : [];
    setColumns(cols);
    setSourceLabel(detail.source_path ?? detail.source_filename ?? 'Source');
    setTargetLabel(detail.target_path ?? detail.target_filename ?? 'Target');
    const mc = detail.mismatch_counts;
    const expected = mc.missing_in_target + mc.extra_in_target + (
      mc.value_mismatch_rows ?? mc.value_mismatch
    );
    setExpectedMismatchTotal(expected);
    setCleanRun(expected === 0);
    setShowMatchedOnly(expected === 0);
    setColPage(0);
    setRowPage(0);
  }, [runReady, historyRunState.data]);

  const allRows = useMemo(() => buildSnippetRows(allItems, columns), [allItems, columns]);

  const issueRows = useMemo(() => allRows.filter(rowHasAnyIssue), [allRows]);
  const matchRows = useMemo(() => allRows.filter((row) => row.status === 'match'), [allRows]);

  const displayColumns = useMemo(() => {
    if (cleanRun) return columns;
    if (!showMatchedOnly) return columns;
    return columns.filter((col) => !issueRows.some((row) => row.mismatchColumns.has(col)));
  }, [columns, issueRows, showMatchedOnly, cleanRun]);

  const displayIssueRows = useMemo(() => {
    if (cleanRun && matchRows.length > 0) return matchRows;
    if (!showMatchedOnly) return issueRows;
    return issueRows.filter(
      (row) =>
        row.status !== 'extra_source'
        && row.status !== 'missing_target'
        && columns.some((col) => isMatchedCell(row, col)),
    );
  }, [issueRows, matchRows, columns, showMatchedOnly, cleanRun]);

  const totalColPages = Math.max(1, Math.ceil(displayColumns.length / COLS_PER_PAGE));
  const visibleCols = displayColumns.slice(colPage * COLS_PER_PAGE, (colPage + 1) * COLS_PER_PAGE);
  const displayCols = ['uid', ...visibleCols];

  const totalRowPages = Math.max(1, Math.ceil(displayIssueRows.length / itemsPerPage));
  const pageRows = displayIssueRows.slice(rowPage * itemsPerPage, (rowPage + 1) * itemsPerPage);

  useEffect(() => {
    setRowPage(0);
  }, [colPage, itemsPerPage, showMatchedOnly]);

  useEffect(() => {
    setColPage(0);
  }, [showMatchedOnly]);

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

  const cellClassName = (row: SnippetRow, side: 'source' | 'target', col: string): string => {
    if (col === 'uid') return styles.cellUid;
    const src = row.source[col] ?? EMPTY;
    const tgt = row.target[col] ?? EMPTY;
    const isMismatch = row.mismatchColumns.has(col) && visibleCols.includes(col);
    const isRowIssue = row.status === 'extra_source' || row.status === 'missing_target';

    if (isMismatch) return styles.cellMismatch;
    if (isRowIssue) {
      const hasValue = side === 'source' ? src !== EMPTY : tgt !== EMPTY;
      return hasValue ? styles.cellRowIssue : styles.cellRowIssueEmpty;
    }
    if (src !== EMPTY && tgt !== EMPTY && src === tgt) return styles.cellMatch;
    return styles.cellDefault;
  };

  const rowClassName = (row: SnippetRow): string => {
    if (showMatchedOnly) return styles.rowDefault;
    return (row.status === 'extra_source' || row.status === 'missing_target')
      ? styles.rowIssue
      : styles.rowDefault;
  };

  const renderCells = (row: SnippetRow, side: 'source' | 'target') => displayCols.map((col) => {
    const cell = col === 'uid' ? row.uid : (row[side][col] ?? EMPTY);
    return (
      <td key={`${side}-${col}`} className={`${styles.td} ${cellClassName(row, side, col)}`}>
        {cell}
      </td>
    );
  });

  const emptyMessage = allItems.length === 0 && expectedMismatchTotal > 0
    ? 'Mismatch rows were not saved for this run. Re-run validation to regenerate the snippet, or check that the database is reachable.'
    : issueRows.length === 0 && matchRows.length === 0
      ? cleanRun
        ? 'No matching row samples were saved for this run. Re-run validation to regenerate the snippet.'
        : 'No mismatches for this validation run.'
      : showMatchedOnly
        ? displayColumns.length === 0
          ? 'No matched columns in this validation run.'
          : 'No matched values in the current column window. Use “Next cols” to inspect other columns.'
        : 'No issues in the current column window. Use “Next cols” to inspect other columns.';

  const isDataLoading = summaryLoading || rowsLoading;
  const skeletonColCount = displayCols.length || COLS_PER_PAGE + 1;

  if (error) return <div className={styles.error}>{error}</div>;

  return (
    <div className={styles.page}>
      {loadProgress && (
        <p className={styles.loadProgress}>{loadProgress}</p>
      )}
      <div className={styles.header}>
        <div className={styles.breadcrumb}>
          <span className={styles.breadcrumbLink} onClick={() => navigate('/reports')}>Reports</span>
          <RightOutlined className={styles.breadcrumbIcon} />
          <span className={styles.breadcrumbChip}>{pairLabel}</span>
          <RightOutlined className={styles.breadcrumbIcon} />
          <span className={styles.breadcrumbChip}>{runId}</span>
          <RightOutlined className={styles.breadcrumbIcon} />
          <span className={styles.breadcrumbCurrent}>Snippet</span>
        </div>
        <div className={styles.downloadWrap}>
          <button type="button" onClick={() => setDownloadOpen((o) => !o)} className={styles.downloadBtn}>
            <DownloadOutlined /> Download Snippet
          </button>
          {downloadOpen && (
            <div className={styles.downloadMenu}>
              {(['CSV', 'XLSX', 'PDF'] as const).map((fmt) => (
                <button key={fmt} type="button" onClick={() => {
                  setDownloadOpen(false);
                  const base = `snippet-${runId}-cols${colPage + 1}`;
                  const data = exportRows();
                  if (fmt === 'CSV') downloadSnippetCsv(data, visibleCols, `${base}.csv`);
                  else if (fmt === 'XLSX') downloadSnippetXlsx(data, visibleCols, `${base}.xlsx`);
                  else downloadSnippetPdf(data, visibleCols, `Snippet ${runId}`);
                }} className={styles.downloadMenuItem}>
                  {fmt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className={styles.controls}>
        <span className={styles.controlText}>
          Columns {displayColumns.length ? colPage * COLS_PER_PAGE + 1 : 0}–{Math.min((colPage + 1) * COLS_PER_PAGE, displayColumns.length)} of {displayColumns.length}
          {showMatchedOnly && columns.length !== displayColumns.length ? ` (${columns.length} total)` : ''}
        </span>
        <button type="button" disabled={colPage <= 0} onClick={() => setColPage((p) => p - 1)} className={styles.navBtn}>← Prev cols</button>
        <button type="button" disabled={colPage >= totalColPages - 1} onClick={() => setColPage((p) => p + 1)} className={styles.navBtn}>Next cols →</button>
        <button
          type="button"
          onClick={() => setShowMatchedOnly((v) => !v)}
          className={`${styles.matchToggle} ${showMatchedOnly ? styles.matchToggleActive : ''}`}
        >
          <CheckCircleOutlined />
          {showMatchedOnly ? 'Showing matched only' : 'Show matched only'}
        </button>
        <span className={styles.controlText}>
          {isDataLoading
            ? 'Loading…'
            : showMatchedOnly || cleanRun
              ? `${displayIssueRows.length.toLocaleString()} UID(s) with matched values · ${displayColumns.length} matched column(s)`
              : `${issueRows.length.toLocaleString()} UID(s) with issues · red cells are mismatches in the visible column window`}
        </span>
      </div>

      <div className={styles.legend}>
        <span><span className={styles.legendGreen}>Green</span> = matching</span>
        <span><span className={styles.legendRed}>Red</span> = mismatch</span>
        <span><span className={styles.legendOrange}>Orange</span> = missing / extra row</span>
      </div>

      <div className={styles.panels}>
        <div className={styles.panel}>
          <div className={styles.panelHeaderSource}>
            <DatabaseOutlined /> <span className={styles.panelHeaderTitle}>Source &gt; {sourceLabel}</span>
          </div>
          <div ref={sourceRef} onScroll={handleSourceScroll} className={styles.panelScroll}>
            <table className={styles.table}>
              <thead className={styles.thead}>
                <tr>
                  {isDataLoading && displayCols.length === 0
                    ? Array.from({ length: skeletonColCount }, (_, i) => (
                      <th key={i} className={styles.th}>
                        {i === 0 ? 'UID' : <SkeletonCell colIdx={i} />}
                      </th>
                    ))
                    : displayCols.map((col) => <th key={col} className={styles.th}>{col === 'uid' ? 'UID' : col}</th>)}
                </tr>
              </thead>
              <tbody>
                {isDataLoading ? (
                  <SnippetSkeletonRows colCount={skeletonColCount} />
                ) : pageRows.length === 0 ? (
                  <tr><td colSpan={displayCols.length || 1} className={styles.emptyCell}>{emptyMessage}</td></tr>
                ) : pageRows.map((row) => (
                  <tr key={`src-${row.uid}`} className={rowClassName(row)}>
                    {renderCells(row, 'source')}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className={styles.panel}>
          <div className={styles.panelHeaderTarget}>
            <DatabaseOutlined /> <span className={styles.panelHeaderTitle}>Target &gt; {targetLabel}</span>
          </div>
          <div ref={targetRef} onScroll={handleTargetScroll} className={styles.panelScroll}>
            <table className={styles.table}>
              <thead className={styles.thead}>
                <tr>
                  {isDataLoading && displayCols.length === 0
                    ? Array.from({ length: skeletonColCount }, (_, i) => (
                      <th key={i} className={styles.th}>
                        {i === 0 ? 'UID' : <SkeletonCell colIdx={i} />}
                      </th>
                    ))
                    : displayCols.map((col) => <th key={col} className={styles.th}>{col === 'uid' ? 'UID' : col}</th>)}
                </tr>
              </thead>
              <tbody>
                {isDataLoading ? (
                  <SnippetSkeletonRows colCount={skeletonColCount} />
                ) : pageRows.length === 0 ? (
                  <tr><td colSpan={displayCols.length || 1} className={styles.emptyCell}>{emptyMessage}</td></tr>
                ) : pageRows.map((row) => (
                  <tr key={`tgt-${row.uid}`} className={rowClassName(row)}>
                    {renderCells(row, 'target')}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className={styles.footer}>
        <span className={styles.footerNote}>
          {cleanRun
            ? 'Showing up to 10 matching rows per column. Use “Next cols” to inspect other columns.'
            : 'Use “Next cols” to inspect mismatches in other columns. Row pages list every UID with a missing, extra, or value mismatch.'}
        </span>
        <div className={styles.footerControls}>
          <div className={styles.rowsPerPage}>
            Rows per page:
            <select value={itemsPerPage} onChange={(e) => setItemsPerPage(Number(e.target.value))} className={styles.rowsPerPageSelect}>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div className={styles.pagination}>
            <button
              type="button"
              disabled={rowPage <= 0}
              onClick={() => rowPage > 0 && setRowPage((p) => p - 1)}
              className={`${styles.paginationIcon} ${rowPage <= 0 ? styles.paginationIconDisabled : styles.paginationIconEnabled}`}
            >
              <LeftOutlined />
            </button>
            <span className={styles.paginationLabel}>
              {isDataLoading ? '—' : (displayIssueRows.length ? rowPage + 1 : 0)}
              <span className={styles.paginationDivider}>/</span>
              {isDataLoading ? '—' : totalRowPages}
            </span>
            <button
              type="button"
              disabled={rowPage >= totalRowPages - 1}
              onClick={() => rowPage < totalRowPages - 1 && setRowPage((p) => p + 1)}
              className={`${styles.paginationIcon} ${rowPage >= totalRowPages - 1 ? styles.paginationIconDisabled : styles.paginationIconEnabled}`}
            >
              <RightOutlined />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

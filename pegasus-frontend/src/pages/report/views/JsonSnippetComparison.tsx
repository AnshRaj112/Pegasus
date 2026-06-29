import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  RightOutlined, DatabaseOutlined, LeftOutlined,
} from '@ant-design/icons';
import { MismatchSampleRow } from '../../../shared/api/Api';
import { useAppSelector } from '../../../redux/store';
import styles from './JsonSnippetComparison.module.scss';

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

const SKELETON_ROWS = 6;

const SkeletonBlock: React.FC = () => (
  <div className={`${styles.skeleton} ${styles.skeletonFull}`} />
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
    return <span className={styles.pathContext}>$</span>;
  }
  return (
    <span className={styles.pathContext}>
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
    <span title={tooltip} className={styles.siblingHint}>
      … {siblings.length} items in {side}
    </span>
  );
};

const fieldLineClassName = (highlight: boolean, absent: boolean): string => {
  if (highlight) return `${styles.fieldLine} ${styles.fieldLineHighlight}`;
  if (absent) return `${styles.fieldLine} ${styles.fieldLineAbsent}`;
  return styles.fieldLine;
};

const FieldLine: React.FC<{
  fieldKey: string;
  value: string | null;
  highlight: boolean;
  absent?: boolean;
}> = ({ fieldKey, value, highlight, absent = false }) => (
  <div className={fieldLineClassName(highlight, absent)}>
    <span className={highlight ? styles.fieldKeyHighlight : styles.fieldKey}>{fieldKey}</span>
    <span>{value ?? '—'}</span>
  </div>
);

const kindLabel: Record<JsonIssueKind, string> = {
  value_mismatch: 'mismatch',
  missing_in_target: 'missing in target',
  extra_in_target: 'extra in target',
};

const kindBadgeClass = (kind: JsonIssueKind): string => (
  kind === 'value_mismatch'
    ? `${styles.kindBadge} ${styles.kindBadgeMismatch}`
    : `${styles.kindBadge} ${styles.kindBadgeMissing}`
);

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
    <div className={styles.issuePair}>
      <div className={styles.issueMeta}>
        <span className={styles.issueUid}>
          UID: <span className={styles.issueUidValue}>{row.uid}</span>
        </span>
        <span className={styles.issueDivider}>|</span>
        <PathContext path={row.jsonPath} />
        <span className={kindBadgeClass(row.kind)}>
          {kindLabel[row.kind]}
        </span>
        <SiblingHint keys={siblingKeys} siblings={siblings} side="source" />
      </div>

      {fields.length === 0 ? (
        <div className={styles.fallbackGrid}>
          <div className={`${styles.fallbackCell} ${sourceAbsent ? styles.fallbackCellAbsent : ''}`}>
            {sourceAbsent ? 'not present' : formatValue(row.sourceValue)}
          </div>
          <div className={`${styles.fallbackCell} ${targetAbsent ? styles.fallbackCellAbsent : ''}`}>
            {targetAbsent ? 'not present' : formatValue(row.targetValue)}
          </div>
        </div>
      ) : (
        <div className={styles.fieldsGrid}>
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
  const historyRunState = useAppSelector((state) => state.report.historyRunState);
  const mismatchesState = useAppSelector((state) => state.report.mismatchesState);

  const [sourceLabel, setSourceLabel] = useState('Source');
  const [targetLabel, setTargetLabel] = useState('Target');
  const [rowPage, setRowPage] = useState(0);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  const runReady = Boolean(runId && historyRunState.runId === runId);
  const mismatchesReady = Boolean(runId && mismatchesState.runId === runId);
  const summaryLoading = !runReady || historyRunState.isFetching;
  const rowsLoading = !mismatchesReady || mismatchesState.isFetching || !mismatchesState.isComplete;
  const loadProgress = mismatchesReady ? mismatchesState.progressMessage : 'Loading JSON mismatch paths…';
  const error = (runReady && historyRunState.error)
    || (mismatchesReady && mismatchesState.error)
    || null;
  const allItems = mismatchesReady ? mismatchesState.items : [];

  useEffect(() => {
    if (!runReady || !historyRunState.data) return;
    const detail = historyRunState.data;
    setSourceLabel(detail.source_path ?? detail.source_filename ?? 'Source');
    setTargetLabel(detail.target_path ?? detail.target_filename ?? 'Target');
  }, [runReady, historyRunState.data]);

  const issues = useMemo(() => buildJsonIssues(allItems), [allItems]);
  const totalPages = Math.max(1, Math.ceil(issues.length / itemsPerPage));
  const pageRows = issues.slice(rowPage * itemsPerPage, (rowPage + 1) * itemsPerPage);
  const pairLabel = mappingId ?? sourceLabel.split('/').pop() ?? 'Report';
  const isLoading = summaryLoading || rowsLoading;

  useEffect(() => {
    if (rowPage >= totalPages) setRowPage(Math.max(0, totalPages - 1));
  }, [rowPage, totalPages]);

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
          <span className={styles.breadcrumbCurrent}>JSON Snippet</span>
        </div>
      </div>

      <div className={styles.legend}>
        <span><span className={styles.legendRed}>Red row</span> = field value differs</span>
        <span><span className={styles.legendOrange}>Orange</span> = missing / extra node</span>
        <span>Each field is shown on its own line, source aligned with target</span>
      </div>

      <div className={styles.panel}>
        <div className={styles.panelHeaders}>
          <div className={styles.panelHeaderSource}>
            <DatabaseOutlined /> <span className={styles.panelHeaderTitle}>Source &gt; {sourceLabel}</span>
          </div>
          <div className={styles.panelHeaderTarget}>
            <DatabaseOutlined /> <span className={styles.panelHeaderTitle}>Target &gt; {targetLabel}</span>
          </div>
        </div>
        <div className={styles.panelScroll}>
          {isLoading ? (
            Array.from({ length: SKELETON_ROWS }, (_, i) => (
              <div key={i} className={styles.skeletonWrap}><SkeletonBlock /></div>
            ))
          ) : pageRows.length === 0 ? (
            <div className={styles.emptyCell}>No JSON mismatches for this run.</div>
          ) : pageRows.map((row) => (
            <JsonIssuePair key={`${row.uid}-${row.jsonPath}`} row={row} />
          ))}
        </div>
      </div>

      <div className={styles.footer}>
        <span className={styles.footerNote}>
          Each field on its own row — source on the left, target on the right, aligned one-to-one.
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
              {isLoading ? '—' : (issues.length ? rowPage + 1 : 0)}
              <span className={styles.paginationDivider}>/</span>
              {isLoading ? '—' : totalPages}
            </span>
            <button
              type="button"
              disabled={rowPage >= totalPages - 1}
              onClick={() => rowPage < totalPages - 1 && setRowPage((p) => p + 1)}
              className={`${styles.paginationIcon} ${rowPage >= totalPages - 1 ? styles.paginationIconDisabled : styles.paginationIconEnabled}`}
            >
              <RightOutlined />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

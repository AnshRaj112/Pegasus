import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CloseCircleFilled,
  CheckCircleOutlined,
  SyncOutlined,
  HolderOutlined,
  SearchOutlined,
  FilterOutlined,
  ThunderboltOutlined,
  LeftOutlined,
  RightOutlined,
} from '@ant-design/icons';

import { Api, type ColumnMapping } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { ValidationReport } from '../components/ValidationReport';

const PAGE_SIZE = 10;

interface MappingItem {
  id: string;
  sourceColumn: string;
  targetMappings: string[];
  previewValue: string;
}

const looksStructured = (value: string): boolean => {
  const s = value.trim();
  return s.length > 0 && /^[\[{]/.test(s);
};

const inferType = (value: string, isComplex: boolean): string => {
  if (isComplex || looksStructured(value)) return 'Structured';
  if (/^(true|false)$/i.test(value)) return 'Bool';
  if (/^-?\d+$/.test(value)) return 'Int';
  if (/^-?\d+\.\d+$/.test(value)) return 'Float';
  return 'String';
};

const TYPE_BADGE: Record<string, { bg: string; color: string }> = {
  String: { bg: '#e8f0fe', color: '#1a56db' },
  Float: { bg: '#f3e8ff', color: '#7c3aed' },
  Int: { bg: '#fff7ed', color: '#c2410c' },
  Bool: { bg: '#ecfdf5', color: '#047857' },
  Structured: { bg: '#ede9fe', color: '#5b21b6' },
};

const matrixToColumnMappings = (
  matrix: MappingItem[],
  complexColumns: string[],
  structuredOrderSensitive: boolean,
  uidColumn: string,
): ColumnMapping[] =>
  matrix
    .filter((row) => row.sourceColumn !== uidColumn && row.targetMappings.length > 0)
    .map((row) => {
      const [primary, ...extra] = row.targetMappings;
      const base: ColumnMapping = {
        source_column: row.sourceColumn,
        target_column: primary,
        ...(extra.length > 0 ? { target_columns: extra } : {}),
      };
      if (complexColumns.includes(row.sourceColumn)) {
        return {
          ...base,
          compare_mode: 'structured',
          structured_order_sensitive: structuredOrderSensitive,
        };
      }
      return base;
    });

const buildMatrixFromPreview = (
  sourceColumns: string[],
  targetColumns: string[],
  autoMappings: Array<{ source_column: string; target_column: string }>,
  sourceSamples: Record<string, string[]>,
  uid: string,
): MappingItem[] =>
  sourceColumns.map((col) => {
    const auto = autoMappings.find((m) => m.source_column === col);
    const uidTarget = col === uid && targetColumns.includes(col) ? col : null;
    const targets = auto ? [auto.target_column] : uidTarget ? [uidTarget] : [];
    const sample = sourceSamples[col]?.[0] ?? '';
    return { id: col, sourceColumn: col, targetMappings: targets, previewValue: sample };
  });

const TargetMappingField: React.FC<{
  targets: string[];
  available: string[];
  disabled?: boolean;
  onChange: (next: string[]) => void;
}> = ({ targets, available, disabled, onChange }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const addable = available.filter((col) => !targets.includes(col));

  if (disabled) {
    return (
      <span style={{ fontSize: '13px', color: '#64748b' }}>
        {targets.join(', ') || '—'}
      </span>
    );
  }

  return (
    <div ref={ref} style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center', minHeight: '32px' }}>
      {targets.map((target) => (
        <span
          key={target}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            borderRadius: '6px',
            backgroundColor: '#f1f5f9',
            border: '1px solid #e2e8f0',
            fontSize: '12px',
            fontWeight: 500,
            color: '#334155',
          }}
        >
          {target}
          <button
            type="button"
            onClick={() => onChange(targets.filter((t) => t !== target))}
            style={{
              border: 'none',
              background: 'none',
              padding: 0,
              cursor: 'pointer',
              color: '#94a3b8',
              fontSize: '14px',
              lineHeight: 1,
            }}
            aria-label={`Remove ${target}`}
          >
            ×
          </button>
        </span>
      ))}
      {targets.length === 0 && (
        <span style={{ fontSize: '13px', color: '#94a3b8', fontStyle: 'italic' }}>
          Unmapped column field...
        </span>
      )}
      {addable.length > 0 && (
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            style={{
              border: 'none',
              background: 'none',
              color: '#6366f1',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              padding: '4px 0',
            }}
          >
            + Add...
          </button>
          {open && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                zIndex: 20,
                marginTop: '4px',
                minWidth: '160px',
                backgroundColor: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                boxShadow: '0 8px 24px rgba(15, 23, 42, 0.12)',
                padding: '4px 0',
              }}
            >
              {addable.map((col) => (
                <button
                  key={col}
                  type="button"
                  onClick={() => {
                    onChange([...targets, col]);
                    setOpen(false);
                  }}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    border: 'none',
                    background: 'none',
                    padding: '8px 12px',
                    fontSize: '13px',
                    cursor: 'pointer',
                    color: '#334155',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#f8fafc'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                >
                  {col}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const ConfigureMappingStep: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const validationForm = useAppSelector((s) => s.validation.validationForm);
  const { data: validationResult, isFetching, error } = useAppSelector((s) => s.validation.validationDataState);

  const [searchQuery, setSearchQuery] = useState('');
  const [showUnmappedOnly, setShowUnmappedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [sourceColumns, setSourceColumns] = useState<string[]>([]);
  const [targetColumns, setTargetColumns] = useState<string[]>([]);
  const [autoMappings, setAutoMappings] = useState<Array<{ source_column: string; target_column: string }>>([]);
  const [columnsMatrix, setColumnsMatrix] = useState<MappingItem[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [complexColumns, setComplexColumns] = useState<string[]>([]);
  const [needsOrderPreference, setNeedsOrderPreference] = useState(false);
  const [viewDetailedReport, setViewDetailedReport] = useState(false);

  const loadingPreview = Boolean(
    validationForm.sourceCloud && validationForm.targetCloud && columnsMatrix.length === 0 && !previewError,
  );

  const selectedUidColumn = validationForm.uidColumn;
  const compareTargets = targetColumns.filter((col) => col !== selectedUidColumn);

  const syncMappings = (
    matrix: MappingItem[],
    structuredOrderSensitive = validationForm.structuredOrderSensitive,
  ) => {
    dispatch(validationActions.setValidationForm({
      columnMappings: matrixToColumnMappings(
        matrix,
        complexColumns,
        structuredOrderSensitive,
        selectedUidColumn,
      ),
    }));
  };

  useEffect(() => {
    if (!validationForm.sourceCloud || !validationForm.targetCloud) return;
    let cancelled = false;
    Api.previewValidationColumns({
      source_cloud: validationForm.sourceCloud,
      target_cloud: validationForm.targetCloud,
      uid_column: validationForm.uidColumn,
      delimiter: validationForm.delimiter,
      has_header: validationForm.hasHeader,
    })
      .then((res) => {
        if (cancelled) return;
        const preview = res.data;
        if (preview.inferred_has_header === false && validationForm.hasHeader) {
          dispatch(validationActions.setValidationForm({ hasHeader: false }));
          return;
        }
        const defaultUid = preview.source_columns.includes('column_1')
          ? 'column_1'
          : preview.source_columns[0] ?? 'id';
        const uid = preview.source_columns.includes(validationForm.uidColumn)
          ? validationForm.uidColumn
          : defaultUid;
        const auto = preview.auto_mappings ?? [];
        const mappings = buildMatrixFromPreview(
          preview.source_columns,
          preview.target_columns,
          auto,
          preview.source_samples ?? {},
          uid,
        );
        const complex = preview.complex_columns ?? [];
        setAutoMappings(auto);
        setComplexColumns(complex);
        setNeedsOrderPreference(Boolean(preview.needs_order_preference ?? complex.length > 0));
        setSourceColumns(preview.source_columns);
        setTargetColumns(preview.target_columns);
        setColumnsMatrix(mappings);
        setPage(1);
        dispatch(validationActions.setValidationForm({
          uidColumn: uid,
          delimiter: preview.delimiter,
          hasHeader: preview.has_header ?? validationForm.hasHeader,
          columnMappings: matrixToColumnMappings(
            mappings,
            complex,
            validationForm.structuredOrderSensitive,
            uid,
          ),
        }));
      })
      .catch((err: { response?: { data?: { detail?: unknown } } }) => {
        if (cancelled) return;
        const detail = err.response?.data?.detail;
        const message =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
              ? detail.map((item) => (typeof item === 'object' && item && 'msg' in item ? String(item.msg) : String(item))).join('; ')
              : null;
        setPreviewError(message ?? 'Could not load column preview from server');
      });
    return () => { cancelled = true; };
  }, [validationForm.sourceCloud, validationForm.targetCloud, validationForm.uidColumn, validationForm.delimiter, validationForm.hasHeader, dispatch]);

  const usedTargetsByOthers = (sourceColumn: string) => {
    const used = new Set<string>();
    columnsMatrix.forEach((row) => {
      if (row.sourceColumn !== sourceColumn) {
        row.targetMappings.forEach((t) => used.add(t));
      }
    });
    return used;
  };

  const availableForRow = (sourceColumn: string) => {
    const used = usedTargetsByOthers(sourceColumn);
    return compareTargets.filter((col) => !used.has(col));
  };

  const handleAutoMap = () => {
    const next = buildMatrixFromPreview(
      sourceColumns,
      targetColumns,
      autoMappings,
      Object.fromEntries(columnsMatrix.map((r) => [r.sourceColumn, [r.previewValue]])),
      selectedUidColumn,
    );
    setColumnsMatrix(next);
    syncMappings(next);
  };

  const handleTargetChange = (sourceColumn: string, targets: string[]) => {
    const next = columnsMatrix.map((row) =>
      row.sourceColumn === sourceColumn ? { ...row, targetMappings: targets } : row,
    );
    setColumnsMatrix(next);
    syncMappings(next);
  };

  const handleUidChange = (uid: string) => {
    dispatch(validationActions.setValidationForm({ uidColumn: uid }));
  };

  const handleStructuredOrderChange = (structuredOrderSensitive: boolean) => {
    dispatch(validationActions.setValidationForm({ structuredOrderSensitive }));
    syncMappings(columnsMatrix, structuredOrderSensitive);
  };

  const filteredColumns = useMemo(() => {
    let rows = columnsMatrix;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      rows = rows.filter((col) => col.sourceColumn.toLowerCase().includes(q));
    }
    if (showUnmappedOnly) {
      rows = rows.filter(
        (col) => col.sourceColumn !== selectedUidColumn && col.targetMappings.length === 0,
      );
    }
    return rows;
  }, [columnsMatrix, searchQuery, showUnmappedOnly, selectedUidColumn]);

  const totalPages = Math.max(1, Math.ceil(filteredColumns.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * PAGE_SIZE;
  const pageRows = filteredColumns.slice(pageStart, pageStart + PAGE_SIZE);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const results = validationResult?.results;

  if (viewDetailedReport) {
    return (
      <ValidationReport
        jobId={validationResult?.jobId ?? undefined}
        runId={validationResult?.runId ?? undefined}
        initialResult={results ?? null}
        onBack={() => setViewDetailedReport(false)}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
      {/* Compact file options */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '16px',
          alignItems: 'center',
          fontSize: '13px',
          color: '#64748b',
        }}
      >
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          Delimiter
          <input
            type="text"
            value={validationForm.delimiter}
            onChange={(e) => dispatch(validationActions.setValidationForm({ delimiter: e.target.value || 'auto' }))}
            style={{ width: '56px', height: '28px', textAlign: 'center', borderRadius: '6px', border: '1px solid #e2e8f0' }}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <input
            type="checkbox"
            checked={validationForm.hasHeader}
            onChange={(e) => dispatch(validationActions.setValidationForm({ hasHeader: e.target.checked }))}
          />
          Header row
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          UID column
          <select
            value={selectedUidColumn}
            onChange={(e) => handleUidChange(e.target.value)}
            style={{ height: '28px', padding: '0 8px', borderRadius: '6px', border: '1px solid #e2e8f0' }}
          >
            {sourceColumns.map((col) => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>
        </label>
        {loadingPreview && <span>Loading columns…</span>}
      </div>

      {previewError && (
        <p style={{ color: '#ba1a1a', margin: 0, fontSize: '13px' }}>{previewError}</p>
      )}

      {needsOrderPreference && (
        <div style={{ backgroundColor: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: '8px', padding: '12px 16px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <input
              type="checkbox"
              checked={validationForm.structuredOrderSensitive}
              onChange={(e) => handleStructuredOrderChange(e.target.checked)}
            />
            Require list/dict element order to match for structured columns ({complexColumns.join(', ')})
          </label>
        </div>
      )}

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 280px', maxWidth: '420px' }}>
          <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input
            type="text"
            placeholder="Filter attributes by label names..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
            style={{
              width: '100%',
              padding: '10px 12px 10px 36px',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              fontSize: '14px',
              boxSizing: 'border-box',
            }}
          />
        </div>
        <button
          type="button"
          onClick={() => { setShowUnmappedOnly((v) => !v); setPage(1); }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            borderRadius: '8px',
            border: `1px solid ${showUnmappedOnly ? '#6366f1' : '#e2e8f0'}`,
            backgroundColor: showUnmappedOnly ? '#eef2ff' : '#fff',
            color: showUnmappedOnly ? '#4f46e5' : '#475569',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          <FilterOutlined /> Filters
        </button>
        <button
          type="button"
          onClick={handleAutoMap}
          disabled={loadingPreview || autoMappings.length === 0}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
            backgroundColor: '#fff',
            color: '#475569',
            fontSize: '14px',
            fontWeight: 500,
            cursor: loadingPreview ? 'not-allowed' : 'pointer',
            opacity: loadingPreview ? 0.6 : 1,
          }}
        >
          <ThunderboltOutlined /> Auto-Map
        </button>
      </div>

      {/* Mapping table */}
      <div
        style={{
          backgroundColor: '#fff',
          borderRadius: '12px',
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '720px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                {['Source Column', 'Data Type', 'Target Mapping Fields', 'Preview Value'].map((label) => (
                  <th
                    key={label}
                    style={{
                      padding: '14px 16px',
                      textAlign: 'left',
                      fontSize: '11px',
                      fontWeight: 700,
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                      color: '#64748b',
                    }}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '14px' }}>
                    {loadingPreview ? 'Loading…' : 'No columns match your filter.'}
                  </td>
                </tr>
              ) : (
                pageRows.map((row) => {
                  const isUid = row.sourceColumn === selectedUidColumn;
                  const typeName = inferType(row.previewValue, complexColumns.includes(row.sourceColumn));
                  const badge = TYPE_BADGE[typeName] ?? TYPE_BADGE.String;
                  return (
                    <tr
                      key={row.id}
                      style={{
                        borderBottom: '1px solid #f1f5f9',
                        backgroundColor: isUid ? '#fffbeb' : '#fff',
                      }}
                    >
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <HolderOutlined style={{ color: '#cbd5e1', fontSize: '14px' }} />
                          <span style={{ fontSize: '14px', fontWeight: 500, color: '#1e293b' }}>
                            {row.sourceColumn}
                          </span>
                          {isUid && (
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                padding: '2px 8px',
                                borderRadius: '4px',
                                backgroundColor: '#ffedd5',
                                color: '#c2410c',
                                letterSpacing: '0.04em',
                              }}
                            >
                              UID
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 600,
                            backgroundColor: badge.bg,
                            color: badge.color,
                          }}
                        >
                          {typeName}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle', minWidth: '220px' }}>
                        <TargetMappingField
                          targets={row.targetMappings}
                          available={availableForRow(row.sourceColumn)}
                          disabled={isUid}
                          onChange={(next) => handleTargetChange(row.sourceColumn, next)}
                        />
                      </td>
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        <code
                          style={{
                            fontSize: '13px',
                            color: '#475569',
                            backgroundColor: '#f8fafc',
                            padding: '2px 6px',
                            borderRadius: '4px',
                          }}
                        >
                          {row.previewValue || '—'}
                        </code>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination footer */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 16px',
            borderTop: '1px solid #e2e8f0',
            backgroundColor: '#fafafa',
            fontSize: '13px',
            color: '#64748b',
          }}
        >
          <span>
            {filteredColumns.length === 0
              ? 'Showing 0 attributes'
              : `Showing ${pageStart + 1}-${Math.min(pageStart + PAGE_SIZE, filteredColumns.length)} of ${filteredColumns.length} attributes`}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              disabled={safePage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              style={paginationBtnStyle}
              aria-label="Previous page"
            >
              <LeftOutlined />
            </button>
            <span style={{ minWidth: '88px', textAlign: 'center' }}>
              Page {safePage} of {totalPages}
            </span>
            <button
              type="button"
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              style={paginationBtnStyle}
              aria-label="Next page"
            >
              <RightOutlined />
            </button>
          </div>
        </div>
      </div>

      {isFetching && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6366f1', fontSize: '14px' }}>
          <SyncOutlined spin /> Running validation on server…
        </div>
      )}

      {error && (
        <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', padding: '16px', borderRadius: '8px' }}>
          <CloseCircleFilled style={{ color: '#dc2626', marginRight: '8px' }} />
          {error}
        </div>
      )}

      {validationResult?.status === 'Complete' && results && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h3 style={{ margin: 0, fontSize: '16px' }}>Validation Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
            <Stat label="Match" value={results.summary.is_match ? 'YES' : 'NO'} color={results.summary.is_match ? '#16a34a' : '#dc2626'} />
            <Stat label="Source Rows" value={results.summary.source_row_count.toLocaleString()} />
            <Stat label="Target Rows" value={results.summary.target_row_count.toLocaleString()} />
            <Stat label="Mismatches" value={results.summary.total_mismatch_records.toLocaleString()} color="#dc2626" />
            <Stat label="Run Time" value={`${(results.durations?.validation_seconds ?? results.durations?.total_seconds ?? 0).toFixed(2)}s`} color="#6366f1" />
          </div>
          <button
            type="button"
            onClick={() => (validationResult.jobId ? navigate(`/validation/report/${validationResult.jobId}`) : setViewDetailedReport(true))}
            style={{
              alignSelf: 'center',
              padding: '10px 24px',
              backgroundColor: '#fff',
              color: '#6366f1',
              border: '1px solid #6366f1',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontWeight: 600,
            }}
          >
            <CheckCircleOutlined /> View Detailed Report
          </button>
        </div>
      )}
    </div>
  );
};

const paginationBtnStyle: React.CSSProperties = {
  width: '32px',
  height: '32px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  border: '1px solid #e2e8f0',
  borderRadius: '6px',
  backgroundColor: '#fff',
  cursor: 'pointer',
  color: '#475569',
};

const Stat: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color = '#1e293b' }) => (
  <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
    <p style={{ margin: 0, fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>{label}</p>
    <p style={{ margin: '8px 0 0', fontSize: '18px', fontWeight: 700, color }}>{value}</p>
  </div>
);

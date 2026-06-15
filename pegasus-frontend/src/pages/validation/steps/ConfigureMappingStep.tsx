import React, { useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CloseCircleFilled,
  CheckCircleOutlined,
  SyncOutlined,
  SearchOutlined,
  FilterOutlined,
  LeftOutlined,
  RightOutlined,
  KeyOutlined,
  StopOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  CodeOutlined,
  ArrowRightOutlined,
  CloseOutlined
} from '@ant-design/icons';

import { Api, type ColumnMapping, type GoogleCloudStorageConfig } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { ValidationReport } from '../components/ValidationReport';

const PAGE_SIZE = 10;

interface ComplexMappingRow {
  id: string;
  sourceCol: string;
  sourceType: string;
  targetCols: { name: string; type: string; sample: string }[];
  isPk: boolean;
  isIgnored: boolean;
  isSensitive: boolean;
  isExpanded: boolean;
  sourceExpr: string;
  targetExpr: string;
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

const getCloudLabel = (cloud: string | GoogleCloudStorageConfig | null | undefined): string => {
  if (!cloud) return 'Pending';
  if (typeof cloud === 'string') return cloud;
  if (cloud.bucket && cloud.object_name) return `gs://${cloud.bucket}/${cloud.object_name}`;
  return cloud.object_name || 'GCS Source Configured';
};

const matrixToColumnMappings = (
  matrix: ComplexMappingRow[],
  complexColumns: string[],
  structuredOrderSensitive: boolean
): ColumnMapping[] =>
  matrix
    .filter((row) => !row.isIgnored && row.targetCols.length > 0)
    .map((row) => {
      const [primary, ...extra] = row.targetCols.map(t => t.name);
      const base: ColumnMapping = {
        source_column: row.sourceCol,
        target_column: primary,
        ...(extra.length > 0 ? { target_columns: extra } : {}),
      };

      if (complexColumns.includes(row.sourceCol)) {
        return {
          ...base,
          compare_mode: 'structured',
          structured_order_sensitive: structuredOrderSensitive,
        };
      }
      return base;
    });

const TargetMappingField: React.FC<{
  targets: { name: string; type: string; sample: string }[];
  availableColumns: string[];
  onAdd: (colName: string) => void;
  onRemove: (colIndex: number) => void;
}> = ({ targets, availableColumns, onAdd, onRemove }) => {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'flex-start' }}>
      {targets.map((tc, idx) => (
        <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span style={{ 
            backgroundColor: '#f6f3f2', border: '1px solid #c1c6d7', color: '#1b1b1c', 
            padding: '4px 8px', borderRadius: '4px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' 
          }}>
            {tc.name} 
            <CloseOutlined onClick={() => onRemove(idx)} style={{ fontSize: '10px', cursor: 'pointer', color: '#727786' }} />
          </span>
          <span style={{ backgroundColor: '#f0eded', border: '1px solid #c1c6d7', padding: '2px 4px', borderRadius: '4px', fontSize: '10px', fontWeight: 700, color: '#727786', alignSelf: 'flex-start' }}>
            {tc.type}
          </span>
        </div>
      ))}

      <div style={{ position: 'relative', marginTop: '6px' }} ref={dropdownRef}>
        {availableColumns.length > 0 && (
          <button 
            onClick={() => setOpen(!open)}
            style={{ background: 'none', border: 'none', color: '#0057c2', fontSize: '12px', fontWeight: 500, cursor: 'pointer', padding: 0 }}
          >
            + Add target
          </button>
        )}
        
        {open && availableColumns.length > 0 && (
          <div style={{ 
            position: 'absolute', top: '100%', left: 0, marginTop: '4px', zIndex: 50,
            backgroundColor: '#fff', border: '1px solid #c1c6d7', borderRadius: '4px', 
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)', maxHeight: '200px', overflowY: 'auto', minWidth: '160px'
          }}>
            {availableColumns.map(col => (
              <div 
                key={col} 
                onClick={() => { onAdd(col); setOpen(false); }}
                style={{ padding: '8px 12px', fontSize: '12px', cursor: 'pointer', borderBottom: '1px solid #f0eded' }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f6f3f2')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                {col}
              </div>
            ))}
          </div>
        )}
      </div>
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
  const [columnsMatrix, setColumnsMatrix] = useState<ComplexMappingRow[]>([]);
  const [targetColumnsList, setTargetColumnsList] = useState<string[]>([]); 
  const [targetSamplesRecord, setTargetSamplesRecord] = useState<Record<string, string>>({});
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [complexColumns, setComplexColumns] = useState<string[]>([]);
  const [needsOrderPreference, setNeedsOrderPreference] = useState(false);
  const [viewDetailedReport, setViewDetailedReport] = useState(false);

  const [itemsPerPage, setItemsPerPage] = useState(PAGE_SIZE);

  const loadingPreview = Boolean(
    validationForm.sourceCloud && validationForm.targetCloud && columnsMatrix.length === 0 && !previewError,
  );

  const syncMappings = (
    matrix: ComplexMappingRow[],
    structuredOrderSensitive = validationForm.structuredOrderSensitive,
  ) => {
    const activePks = matrix.filter(m => m.isPk).map(m => m.sourceCol);
    const activePkString = activePks.length > 0 ? activePks.join(',') : validationForm.uidColumn;
    
    dispatch(validationActions.setValidationForm({
      uidColumn: activePkString,
      columnMappings: matrixToColumnMappings(matrix, complexColumns, structuredOrderSensitive),
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

        const savedUids = validationForm.uidColumn?.split(',') || [];
        const defaultUid = preview.source_columns.includes('column_1') ? 'column_1' : preview.source_columns[0] ?? 'id';
        const isUidMatch = (col: string) => savedUids.includes(col) || (savedUids.length === 0 && col === defaultUid);
        
        const autoMappings = preview.auto_mappings ?? [];
        const complex = preview.complex_columns ?? [];
        
        const tSamples: Record<string, string> = {};
        Object.entries(preview.target_samples ?? {}).forEach(([k, v]) => {
           tSamples[k] = (v as string[])[0] ?? '';
        });

        const mappings: ComplexMappingRow[] = preview.source_columns.map((col) => {
          const auto = autoMappings.find((m) => m.source_column === col);
          const isUid = isUidMatch(col);
          const uidTarget = isUid && preview.target_columns.includes(col) ? col : null;
          const targets = auto ? [auto.target_column] : uidTarget ? [uidTarget] : [];
          
          const sample = preview.source_samples?.[col]?.[0] ?? '';
          const inferredType = inferType(sample, complex.includes(col));

          return {
            id: col,
            sourceCol: col,
            sourceType: inferredType,
            targetCols: targets.map(t => {
              const targetSample = tSamples[t] ?? '';
              return { name: t, type: inferType(targetSample, false), sample: targetSample };
            }),
            isPk: isUid,
            isIgnored: false,
            isSensitive: false,
            isExpanded: false,
            sourceExpr: '',
            targetExpr: '',
            previewValue: sample
          };
        });

        setTargetSamplesRecord(tSamples);
        setTargetColumnsList(preview.target_columns || []);
        setComplexColumns(complex);
        setNeedsOrderPreference(Boolean(preview.needs_order_preference ?? complex.length > 0));
        setColumnsMatrix(mappings);
        setPage(1);
        
        const initialPks = mappings.filter(m => m.isPk).map(m => m.sourceCol).join(',');
        dispatch(validationActions.setValidationForm({
          uidColumn: initialPks || defaultUid,
          delimiter: preview.delimiter,
          hasHeader: preview.has_header ?? validationForm.hasHeader,
          columnMappings: matrixToColumnMappings(mappings, complex, validationForm.structuredOrderSensitive),
        }));
      })
      .catch((err: { response?: { data?: { detail?: unknown } } }) => {
        if (cancelled) return;
        const detail = err.response?.data?.detail;
        const message = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((item) => (typeof item === 'object' && item && 'msg' in item ? String(item.msg) : String(item))).join('; ')
            : null;
        setPreviewError(message ?? 'Could not load column preview from server');
        console.error('[Column Preview Failed]:', err);
      });

    return () => { cancelled = true; };
  }, [validationForm.sourceCloud, validationForm.targetCloud, validationForm.uidColumn, validationForm.delimiter, validationForm.hasHeader, dispatch]);

  const toggleProperty = (id: string, prop: keyof ComplexMappingRow) => {
    const next = columnsMatrix.map(row => row.id === id ? { ...row, [prop]: !row[prop] } : row);
    setColumnsMatrix(next);
    syncMappings(next);
  };

  const removeTargetCol = (rowId: string, colIndex: number) => {
    const next = columnsMatrix.map(row => {
      if (row.id === rowId) {
        const newTargets = [...row.targetCols];
        newTargets.splice(colIndex, 1);
        return { ...row, targetCols: newTargets };
      }
      return row;
    });
    setColumnsMatrix(next);
    syncMappings(next);
  };

  const addTargetCol = (rowId: string, targetColName: string) => {
    const targetSample = targetSamplesRecord[targetColName] ?? '';
    const next = columnsMatrix.map(row => {
      if (row.id === rowId) {
        return { ...row, targetCols: [...row.targetCols, { name: targetColName, type: inferType(targetSample, false), sample: targetSample }] };
      }
      return row;
    });
    setColumnsMatrix(next);
    syncMappings(next);
  };

  const handleStructuredOrderChange = (structuredOrderSensitive: boolean) => {
    dispatch(validationActions.setValidationForm({ structuredOrderSensitive }));
    syncMappings(columnsMatrix, structuredOrderSensitive);
  };

  const globalAvailableTargets = useMemo(() => {
    const usedTargets = new Set<string>();
    columnsMatrix.forEach(row => {
      row.targetCols.forEach(tc => usedTargets.add(tc.name));
    });
    return targetColumnsList.filter(col => !usedTargets.has(col));
  }, [columnsMatrix, targetColumnsList]);

  const filteredColumns = useMemo(() => {
    let rows = columnsMatrix;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      rows = rows.filter((col) => col.sourceCol.toLowerCase().includes(q));
    }
    if (showUnmappedOnly) {
      rows = rows.filter((col) => col.targetCols.length === 0 && !col.isIgnored);
    }
    return rows;
  }, [columnsMatrix, searchQuery, showUnmappedOnly]);

  const totalPages = Math.max(1, Math.ceil(filteredColumns.length / itemsPerPage));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * itemsPerPage;
  const pageRows = filteredColumns.slice(pageStart, pageStart + itemsPerPage);

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1440px', margin: '0 auto', width: '100%', height: '100%' }}>
      
      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', fontSize: '13px', color: '#64748b' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          Delimiter
          <input
            type="text"
            value={validationForm.delimiter || ''}
            onChange={(e) => dispatch(validationActions.setValidationForm({ delimiter: e.target.value || 'auto' }))}
            style={{ width: '56px', height: '28px', textAlign: 'center', borderRadius: '6px', border: '1px solid #e2e8f0' }}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <input
            type="checkbox"
            checked={validationForm.hasHeader || false}
            onChange={(e) => dispatch(validationActions.setValidationForm({ hasHeader: e.target.checked }))}
          />
          Header row
        </label>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 8px 0', fontFamily: 'var(--font-mono)' }}>
            Pegasus_Data_Mapping
          </h2>
          <div style={{ display: 'flex', gap: '16px', fontSize: '14px', color: '#414755' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <strong>Source:</strong> <code style={{ backgroundColor: '#f6f3f2', padding: '2px 6px', borderRadius: '4px' }}>{getCloudLabel(validationForm.sourceCloud)}</code>
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <strong>Target:</strong> <code style={{ backgroundColor: '#f6f3f2', padding: '2px 6px', borderRadius: '4px' }}>{getCloudLabel(validationForm.targetCloud)}</code>
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ backgroundColor: '#eef2ff', color: '#4f46e5', padding: '6px 12px', borderRadius: '999px', fontSize: '14px', fontWeight: 500 }}>
            {loadingPreview ? 'Loading...' : `Configured (${columnsMatrix.filter(m => m.targetCols.length > 0 && !m.isIgnored).length})`}
          </span>
        </div>
      </div>

      {previewError && <div style={{ padding: '12px', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '8px' }}>{previewError}</div>}

      {needsOrderPreference && (
        <div style={{ backgroundColor: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: '8px', padding: '12px 16px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <input
              type="checkbox"
              checked={validationForm.structuredOrderSensitive || false}
              onChange={(e) => handleStructuredOrderChange(e.target.checked)}
            />
            Require list/dict element order to match for structured columns ({complexColumns.join(', ')})
          </label>
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 280px', maxWidth: '420px' }}>
          <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input
            type="text"
            placeholder="Filter attributes by names..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
            style={{ width: '100%', padding: '10px 12px 10px 36px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '14px', boxSizing: 'border-box' }}
          />
        </div>
        <button
          type="button"
          onClick={() => { setShowUnmappedOnly((v) => !v); setPage(1); }}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', borderRadius: '8px', border: `1px solid ${showUnmappedOnly ? '#6366f1' : '#e2e8f0'}`, backgroundColor: showUnmappedOnly ? '#eef2ff' : '#fff', color: showUnmappedOnly ? '#4f46e5' : '#475569', fontSize: '14px', fontWeight: 500, cursor: 'pointer' }}
        >
          <FilterOutlined /> Unmapped Only
        </button>
      </div>

      <div style={{ backgroundColor: '#fff', border: '1px solid #c1c6d7', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: '300px' }}>
        <div style={{ overflowX: 'auto', overflowY: 'auto', flexGrow: 1 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', zIndex: 10, borderBottom: '1px solid #c1c6d7' }}>
              <tr>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755', borderRight: '1px solid #c1c6d7', width: '160px' }}>ACTIONS</th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>SOURCE COLUMN</th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>SOURCE SAMPLE</th>
                <th style={{ padding: '12px 8px', fontSize: '12px', fontWeight: 600, color: '#414755', textAlign: 'center', width: '48px' }}></th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>TARGET COLUMN</th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>TARGET SAMPLE</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map(row => (
                <React.Fragment key={row.id}>
                  <tr style={{ borderBottom: '1px solid #e5e2e1', backgroundColor: row.isExpanded ? '#fcf9f8' : row.isIgnored ? '#fcf9f8' : row.isPk ? '#eef2ff' : 'transparent', opacity: row.isIgnored ? 0.6 : 1, transition: 'background-color 0.2s' }}>
                    <td style={{ padding: '12px 16px', borderRight: '1px solid #c1c6d7', verticalAlign: 'top' }}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button onClick={() => toggleProperty(row.id, 'isPk')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isPk ? '#4f46e5' : 'transparent', color: row.isPk ? '#fff' : '#727786', cursor: 'pointer' }} title="Primary Key"><KeyOutlined /></button>
                        <button onClick={() => toggleProperty(row.id, 'isIgnored')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isIgnored ? '#414755' : 'transparent', color: row.isIgnored ? '#fff' : '#727786', cursor: 'pointer' }} title="Ignore"><StopOutlined /></button>
                        <button onClick={() => toggleProperty(row.id, 'isSensitive')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isSensitive ? 'rgba(186, 26, 26, 0.1)' : 'transparent', color: row.isSensitive ? '#ba1a1a' : '#727786', cursor: 'pointer' }} title="Sensitive">{row.isSensitive ? <EyeInvisibleOutlined /> : <EyeOutlined />}</button>
                        <button onClick={() => toggleProperty(row.id, 'isExpanded')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isExpanded ? '#0057c2' : 'transparent', color: row.isExpanded ? '#fff' : '#727786', cursor: 'pointer' }} title="Expression"><CodeOutlined /></button>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top', textDecoration: row.isIgnored ? 'line-through' : 'none' }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 500, color: '#1b1b1c', marginBottom: '4px' }}>{row.sourceCol}</div>
                      <span style={{ backgroundColor: '#f0eded', border: '1px solid #c1c6d7', padding: '2px 4px', borderRadius: '4px', fontSize: '10px', fontWeight: 700, color: '#727786' }}>{row.sourceType}</span>
                    </td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                        <code style={{ fontSize: '12px', color: '#475569', backgroundColor: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>{row.previewValue || '—'}</code>
                      </div>
                    </td>
                    <td style={{ padding: '12px 8px', textAlign: 'center', color: '#c1c6d7', verticalAlign: 'top' }}><ArrowRightOutlined /></td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                      {row.isIgnored ? <span style={{ fontStyle: 'italic', color: '#727786' }}>Dropped</span> : (
                        <TargetMappingField 
                          targets={row.targetCols} 
                          availableColumns={globalAvailableTargets} 
                          onAdd={(col) => addTargetCol(row.id, col)} 
                          onRemove={(idx) => removeTargetCol(row.id, idx)} 
                        />
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                      {!row.isIgnored && row.targetCols.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-start' }}>
                          {row.targetCols.map((tc, idx) => (
                            <code key={idx} style={{ fontSize: '12px', color: '#475569', backgroundColor: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>{tc.sample || '—'}</code>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: '#c1c6d7' }}>—</span>
                      )}
                    </td>
                  </tr>
                  
                  {row.isExpanded && !row.isIgnored && (
                    <tr style={{ backgroundColor: '#fcf9f8', borderBottom: '1px solid #c1c6d7' }}>
                      <td colSpan={6} style={{ padding: '16px 24px 24px 176px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <div style={{ display: 'flex', borderBottom: '1px solid #c1c6d7', gap: '16px' }}>
                              <span style={{ borderBottom: '2px solid #0057c2', color: '#0057c2', paddingBottom: '4px', fontSize: '12px', fontWeight: 600 }}>Source Expression</span>
                            </div>
                            <textarea style={{ width: '100%', minHeight: '80px', border: '1px solid #c1c6d7', borderRadius: '8px', padding: '8px', outline: 'none', fontFamily: 'var(--font-mono)', fontSize: '12px', resize: 'vertical' }} placeholder="e.g. CAST(src.value AS STRING)" defaultValue={row.sourceExpr} />
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <div style={{ display: 'flex', borderBottom: '1px solid #c1c6d7', gap: '16px' }}>
                              <span style={{ borderBottom: '2px solid #0057c2', color: '#0057c2', paddingBottom: '4px', fontSize: '12px', fontWeight: 600 }}>Target Expression</span>
                            </div>
                            <textarea style={{ width: '100%', minHeight: '80px', border: '1px solid #c1c6d7', borderRadius: '8px', padding: '8px', outline: 'none', fontFamily: 'var(--font-mono)', fontSize: '12px', resize: 'vertical' }} placeholder="e.g. DATE_TRUNC('day', val)" defaultValue={row.targetExpr} />
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderTop: '1px solid #e2e8f0', backgroundColor: '#fafafa', fontSize: '13px', color: '#64748b', flexShrink: 0 }}>
          <span>
            {filteredColumns.length === 0
              ? 'Showing 0 attributes'
              : `Showing ${pageStart + 1}-${Math.min(pageStart + itemsPerPage, filteredColumns.length)} of ${filteredColumns.length} attributes`}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button disabled={safePage <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #e2e8f0', borderRadius: '6px', backgroundColor: '#fff', cursor: 'pointer', color: '#475569' }}><LeftOutlined /></button>
              <span style={{ minWidth: '88px', textAlign: 'center' }}>Page {safePage} of {totalPages}</span>
              <button disabled={safePage >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #e2e8f0', borderRadius: '6px', backgroundColor: '#fff', cursor: 'pointer', color: '#475569' }}><RightOutlined /></button>
            </div>
            <select value={itemsPerPage} onChange={(e) => { setItemsPerPage(Number(e.target.value)); setPage(1); }} style={{ padding: '4px', borderRadius: '4px', border: '1px solid #e2e8f0', backgroundColor: '#fff', color: '#475569' }}>
              <option value={10}>10/page</option>
              <option value={25}>25/page</option>
              <option value={50}>50/page</option>
            </select>
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
            style={{ alignSelf: 'center', padding: '10px 24px', backgroundColor: '#fff', color: '#6366f1', border: '1px solid #6366f1', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}
          >
            <CheckCircleOutlined /> View Detailed Report
          </button>
        </div>
      )}
    </div>
  );
};

const Stat: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color = '#1e293b' }) => (
  <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
    <p style={{ margin: 0, fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>{label}</p>
    <p style={{ margin: '8px 0 0', fontSize: '18px', fontWeight: 700, color }}>{value}</p>
  </div>
);
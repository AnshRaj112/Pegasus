import React, { useEffect, useMemo, useState, useRef } from 'react';
import {
  CheckCircleOutlined,
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
  CloseOutlined,
  OrderedListOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';

import { Api, ColumnMapping, FixedWidthColumnPreview, GoogleCloudStorageConfig } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { isFixedWidthFormat } from '../fixedWidthFormat';
import { resolveWizardJsonMode } from '../jsonFormat';
import { resolveWizardArchiveMode, archiveUsesTabularValidation } from '../archiveFormat';
import { FixedWidthLayoutPanel } from './FixedWidthLayoutPanel';
import { ArchiveValidationStep } from './ArchiveValidationStep';
import { JsonParentMappingStep } from './JsonParentMappingStep';

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
  isOrderSensitive: boolean;
  sourceExpr: string;
  targetExpr: string;
  previewValue: string;
}

const looksStructured = (value: string): boolean => {
  const s = value.trim();
  return s.length > 0 && /^[\[{]/.test(s);
};

const isComplexColumn = (row: ComplexMappingRow, complexColumns: string[]): boolean =>
  complexColumns.includes(row.sourceCol)
  || row.sourceType === 'Structured'
  || looksStructured(row.previewValue);

const mergeComplexColumns = (apiComplex: string[], rows: ComplexMappingRow[]): string[] => {
  const found = new Set(apiComplex);
  rows.forEach((row) => {
    if (isComplexColumn(row, apiComplex)) found.add(row.sourceCol);
  });
  return Array.from(found);
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
): ColumnMapping[] =>
  matrix
    .filter((row) => !row.isIgnored && row.targetCols.length > 0)
    .map((row) => {
      const [primary, ...extra] = row.targetCols.map(t => t.name);
      const base: ColumnMapping = {
        source_column: row.sourceCol,
        target_column: primary,
        ...(extra.length > 0 ? { target_columns: extra } : {}),
        ...(row.isSensitive ? { is_sensitive: true } : {}),
        ...(row.sourceExpr.trim() ? { source_regex_pattern: row.sourceExpr.trim() } : {}),
        ...(row.targetExpr.trim() ? { target_regex_pattern: row.targetExpr.trim() } : {}),
      };

      if (isComplexColumn(row, complexColumns)) {
        return {
          ...base,
          compare_mode: 'structured',
          structured_order_sensitive: row.isOrderSensitive,
        };
      }
      return base;
    });

const matrixFromColumnMappings = (
  mappings: ColumnMapping[],
  uidColumn: string,
): ComplexMappingRow[] => {
  const uidSet = new Set(uidColumn.split(',').map((s) => s.trim()).filter(Boolean));
  const sourceColumns = new Set<string>();
  mappings.forEach((mapping) => {
    sourceColumns.add(mapping.source_column);
    (mapping.source_columns ?? []).forEach((col) => sourceColumns.add(col));
  });

  return Array.from(sourceColumns).map((col) => {
    const mapping = mappings.find(
      (m) => m.source_column === col || (m.source_columns ?? []).includes(col),
    );
    const targets = mapping
      ? [mapping.target_column, ...(mapping.target_columns ?? [])].filter(Boolean)
      : [];
    const isStructured = mapping?.compare_mode === 'structured';

    return {
      id: col,
      sourceCol: col,
      sourceType: isStructured ? 'Structured' : 'String',
      targetCols: targets.map((name) => ({ name, type: 'String', sample: '' })),
      isPk: uidSet.has(col),
      isIgnored: !mapping,
      isSensitive: Boolean(mapping?.is_sensitive),
      isExpanded: false,
      isOrderSensitive: mapping?.structured_order_sensitive ?? false,
      sourceExpr: '',
      targetExpr: '',
      previewValue: '',
    };
  });
};

const OrderSensitivityButton: React.FC<{
  strict: boolean;
  onToggle: () => void;
}> = ({ strict, onToggle }) => (
  <button
    type="button"
    onClick={onToggle}
    title={
      strict
        ? 'Strict order: list elements and dict key order must match. Click to ignore order.'
        : 'Ignore order: reordered lists, dict keys, and nested JSON still match. Click to require strict order.'
    }
    style={{
      padding: '4px 6px',
      borderRadius: '4px',
      border: `1px solid ${strict ? '#0057c2' : '#d9d9d9'}`,
      background: strict ? 'rgba(0, 87, 194, 0.1)' : '#fff',
      color: strict ? '#0057c2' : '#727786',
      cursor: 'pointer',
      fontSize: '10px',
      fontWeight: 700,
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      whiteSpace: 'nowrap',
    }}
  >
    {strict ? <OrderedListOutlined style={{ fontSize: '13px' }} /> : <UnorderedListOutlined style={{ fontSize: '13px' }} />}
    <span>{strict ? 'Order on' : 'Order off'}</span>
  </button>
);

const SkeletonBlock: React.FC<{ width?: string; height?: string; borderRadius?: string }> = ({ width = '100%', height = '16px', borderRadius = '4px' }) => (
  <div style={{ width, height, backgroundColor: '#e2e8f0', borderRadius, animation: 'skeleton-pulse 1.5s ease-in-out infinite' }} />
);

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
  const validationForm = useAppSelector((s) => s.validation.validationForm);
  const overviewCache = useAppSelector((s) => s.validation.overviewProfileCache);
  const isFixedWidth = isFixedWidthFormat(validationForm.detectedFileFormat);
  const isJson = resolveWizardJsonMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  });
  const isArchive = Boolean(resolveWizardArchiveMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  }));
  const isArchiveTabular = archiveUsesTabularValidation({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  });
  const isArchiveMetadataOnly = isArchive && !isArchiveTabular;

  const [searchQuery, setSearchQuery] = useState('');

  const [showUnmappedOnly, setShowUnmappedOnly] = useState(false);
  const [showConfiguredOnly, setShowConfiguredOnly] = useState(false);

  const [actionFilters, setActionFilters] = useState({
    pk: false,
    ignored: false,
    sensitive: false,
    expanded: false,
    orderStrict: false,
  });

  const [page, setPage] = useState(1);
  const [columnsMatrix, setColumnsMatrix] = useState<ComplexMappingRow[]>([]);
  const [targetColumnsList, setTargetColumnsList] = useState<string[]>([]);
  const [targetSamplesRecord, setTargetSamplesRecord] = useState<Record<string, string>>({});
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [complexColumns, setComplexColumns] = useState<string[]>([]);
  const hydratedMappingsRef = useRef(false);

  const [itemsPerPage, setItemsPerPage] = useState(PAGE_SIZE);

  const [fixedWidthLoading, setFixedWidthLoading] = useState(false);
  const [fixedWidthError, setFixedWidthError] = useState<string | null>(null);

  const loadingPreview = !isFixedWidth && !isJson && !isArchiveMetadataOnly && Boolean(
    validationForm.sourceCloud && validationForm.targetCloud && columnsMatrix.length === 0 && !previewError,
  );

  const configuredCount = columnsMatrix.filter(m => m.targetCols.length > 0 && !m.isIgnored).length;
  const pkCount = columnsMatrix.filter(m => m.isPk).length;
  const ignoredCount = columnsMatrix.filter(m => m.isIgnored).length;
  const sensitiveCount = columnsMatrix.filter(m => m.isSensitive).length;
  const expandedCount = columnsMatrix.filter(m => m.isExpanded).length;

  const orderStrictCount = columnsMatrix.filter((m) => m.isOrderSensitive && isComplexColumn(m, complexColumns)).length;
  const complexCount = columnsMatrix.filter((m) => isComplexColumn(m, complexColumns)).length;

  const syncMappings = (matrix: ComplexMappingRow[]) => {
    const activePks = matrix.filter(m => m.isPk).map(m => m.sourceCol);
    const activePkString = activePks.length > 0 ? activePks.join(',') : validationForm.uidColumn;

    dispatch(validationActions.setValidationForm({
      uidColumn: activePkString,
      columnMappings: matrixToColumnMappings(matrix, complexColumns),
    }));
  };

  useEffect(() => {
    hydratedMappingsRef.current = false;
  }, [validationForm.sourceCloud, validationForm.targetCloud]);

  useEffect(() => {
    if (!isFixedWidth || !validationForm.sourceCloud || !validationForm.targetCloud) return;
    if (validationForm.fixedWidthColumns.length > 0) return;

    let cancelled = false;
    setFixedWidthLoading(true);
    setFixedWidthError(null);

    Api.previewFixedWidthLayout({
      source_cloud: validationForm.sourceCloud,
      target_cloud: validationForm.targetCloud,
      uid_column: validationForm.uidColumn,
      delimiter: validationForm.delimiter,
      has_header: validationForm.hasHeader,
    })
      .then((res) => {
        if (cancelled) return;
        dispatch(validationActions.setValidationForm({
          fixedWidthColumns: res.data.columns,
          fixedWidthLineWidth: res.data.line_width,
          uidColumn: validationForm.uidColumn || res.data.suggested_join_column,
          detectedFileFormat: 'fixed-width',
        }));
      })
      .catch((err: { response?: { data?: { detail?: unknown } } }) => {
        if (cancelled) return;
        const detail = err.response?.data?.detail;
        setFixedWidthError(typeof detail === 'string' ? detail : 'Could not infer fixed-width layout');
      })
      .finally(() => {
        if (!cancelled) setFixedWidthLoading(false);
      });

    return () => { cancelled = true; };
  }, [
    isFixedWidth,
    validationForm.sourceCloud,
    validationForm.targetCloud,
    validationForm.uidColumn,
    validationForm.delimiter,
    validationForm.hasHeader,
    validationForm.fixedWidthColumns.length,
    dispatch,
  ]);

  useEffect(() => {
    if (!validationForm.sourceCloud || !validationForm.targetCloud || isFixedWidth || isJson || isArchiveMetadataOnly) return;
    if (hydratedMappingsRef.current) return;

    if (validationForm.columnMappings.length > 0) {
      const restored = matrixFromColumnMappings(
        validationForm.columnMappings,
        validationForm.uidColumn,
      );
      const targetNames = new Set<string>();
      validationForm.columnMappings.forEach((mapping) => {
        targetNames.add(mapping.target_column);
        (mapping.target_columns ?? []).forEach((col) => targetNames.add(col));
      });
      setTargetColumnsList(Array.from(targetNames));
      setComplexColumns(
        mergeComplexColumns(
          validationForm.columnMappings
            .filter((m) => m.compare_mode === 'structured')
            .map((m) => m.source_column),
          restored,
        ),
      );
      setColumnsMatrix(restored);
      setPreviewError(null);
      setPage(1);
      hydratedMappingsRef.current = true;
      return;
    }

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
            isOrderSensitive: false,
            sourceExpr: '',
            targetExpr: '',
            previewValue: sample
          };
        });

        setTargetSamplesRecord(tSamples);
        setTargetColumnsList(preview.target_columns || []);
        const mergedComplex = mergeComplexColumns(complex, mappings);
        setComplexColumns(mergedComplex);
        setColumnsMatrix(mappings);
        setPage(1);

        const initialPks = mappings.filter(m => m.isPk).map(m => m.sourceCol).join(',');
        dispatch(validationActions.setValidationForm({
          uidColumn: initialPks || defaultUid,
          delimiter: preview.delimiter,
          hasHeader: preview.has_header ?? validationForm.hasHeader,
          columnMappings: matrixToColumnMappings(mappings, mergedComplex),
        }));
        hydratedMappingsRef.current = true;
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
  }, [validationForm.sourceCloud, validationForm.targetCloud, validationForm.uidColumn, validationForm.delimiter, validationForm.hasHeader, validationForm.columnMappings.length, dispatch, isFixedWidth, isJson, isArchiveMetadataOnly]);

  const handleFixedWidthChange = (columns: FixedWidthColumnPreview[]) => {
    dispatch(validationActions.setValidationForm({ fixedWidthColumns: columns }));
  };

  const handleJoinColumnChange = (joinColumn: string) => {
    dispatch(validationActions.setValidationForm({ uidColumn: joinColumn }));
  };

  if (isJson) {
    return <JsonParentMappingStep />;
  }

  if (isArchiveMetadataOnly) {
    return <ArchiveValidationStep />;
  }

  if (isFixedWidth) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 8px 0', fontFamily: 'var(--font-mono)' }}>
            Pegasus_Fixed_Width_Layout
          </h2>
          <div style={{ display: 'flex', gap: '16px', fontSize: '14px', color: '#414755' }}>
            <span><strong>Source:</strong> <code style={{ backgroundColor: '#f6f3f2', padding: '2px 6px', borderRadius: '4px' }}>{getCloudLabel(validationForm.sourceCloud)}</code></span>
            <span><strong>Target:</strong> <code style={{ backgroundColor: '#f6f3f2', padding: '2px 6px', borderRadius: '4px' }}>{getCloudLabel(validationForm.targetCloud)}</code></span>
          </div>
        </div>
        <FixedWidthLayoutPanel
          columns={validationForm.fixedWidthColumns}
          loading={fixedWidthLoading}
          error={fixedWidthError}
          joinColumn={validationForm.uidColumn}
          lineWidth={validationForm.fixedWidthLineWidth ?? undefined}
          onChange={handleFixedWidthChange}
          onJoinColumnChange={handleJoinColumnChange}
        />
      </div>
    );
  }

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

  const toggleActionFilter = (key: keyof typeof actionFilters) => {
    setActionFilters(prev => ({ ...prev, [key]: !prev[key] }));
    setPage(1);
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
    if (showConfiguredOnly) {
      rows = rows.filter((col) => col.targetCols.length > 0 && !col.isIgnored);
    }

    if (actionFilters.pk) rows = rows.filter(col => col.isPk);
    if (actionFilters.ignored) rows = rows.filter(col => col.isIgnored);
    if (actionFilters.sensitive) rows = rows.filter(col => col.isSensitive);
    if (actionFilters.expanded) rows = rows.filter(col => col.isExpanded);
    if (actionFilters.orderStrict) {
      rows = rows.filter((col) => col.isOrderSensitive && isComplexColumn(col, complexColumns));
    }

    return rows;
  }, [columnsMatrix, searchQuery, showUnmappedOnly, showConfiguredOnly, actionFilters, complexColumns]);

  const totalPages = Math.max(1, Math.ceil(filteredColumns.length / itemsPerPage));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * itemsPerPage;
  const pageRows = filteredColumns.slice(pageStart, pageStart + itemsPerPage);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1440px', margin: '0 auto', width: '100%', height: '100%', position: 'relative' }}>

      <style>{`
        @keyframes skeleton-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>

      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', fontSize: '13px', color: '#234B5F' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          Delimiter
          <input
            type="text"
            value={validationForm.delimiter || ''}
            onChange={(e) => dispatch(validationActions.setValidationForm({ delimiter: e.target.value || 'auto' }))}
            style={{ width: '56px', height: '28px', textAlign: 'center', borderRadius: '6px', border: '1px solid #e2e8f0', opacity: loadingPreview ? 0.6 : 1 }}
            disabled={loadingPreview}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <input
            type="checkbox"
            checked={validationForm.hasHeader || false}
            onChange={(e) => dispatch(validationActions.setValidationForm({ hasHeader: e.target.checked }))}
            disabled={loadingPreview}
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
      </div>

      {previewError && <div style={{ padding: '12px', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '8px' }}>{previewError}</div>}

      {!loadingPreview && complexCount > 0 && (
        <div style={{ padding: '12px 16px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', fontSize: '13px', color: '#1e40af' }}>
          <strong>{complexCount} column{complexCount === 1 ? '' : 's'}</strong> contain JSON, lists, or other structured values.
          Use the <strong>Order on / Order off</strong> control on those rows to choose whether element and key order must match between source and target.
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
            style={{ width: '100%', padding: '10px 12px 10px 36px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '14px', boxSizing: 'border-box', opacity: loadingPreview ? 0.6 : 1 }}
            disabled={loadingPreview}
          />
        </div>

        <button
          type="button"
          onClick={() => { setShowUnmappedOnly(!showUnmappedOnly); setShowConfiguredOnly(false); setPage(1); }}
          disabled={loadingPreview}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', borderRadius: '8px', border: `1px solid ${showUnmappedOnly ? '#6366f1' : '#e2e8f0'}`, backgroundColor: showUnmappedOnly ? '#eef2ff' : '#fff', color: showUnmappedOnly ? '#4f46e5' : '#475569', fontSize: '14px', fontWeight: 500, cursor: loadingPreview ? 'not-allowed' : 'pointer', opacity: loadingPreview ? 0.6 : 1 }}
        >
          <FilterOutlined /> Unmapped Only
        </button>

        <button
          type="button"
          onClick={() => { setShowConfiguredOnly(!showConfiguredOnly); setShowUnmappedOnly(false); setPage(1); }}
          disabled={loadingPreview}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', borderRadius: '8px', border: `1px solid ${showConfiguredOnly ? '#16a34a' : '#e2e8f0'}`, backgroundColor: showConfiguredOnly ? '#f0fdf4' : '#fff', color: showConfiguredOnly ? '#16a34a' : '#475569', fontSize: '14px', fontWeight: 500, cursor: loadingPreview ? 'not-allowed' : 'pointer', opacity: loadingPreview ? 0.6 : 1 }}
        >
          <CheckCircleOutlined /> Configured ({configuredCount})
        </button>
      </div>

      <div style={{ backgroundColor: '#fff', border: '1px solid #c1c6d7', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: '300px' }}>
        <div style={{ overflowX: 'auto', overflowY: 'auto', flexGrow: 1 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', zIndex: 10, borderBottom: '1px solid #c1c6d7' }}>
              <tr>
                <th style={{ padding: '8px 16px', borderRight: '1px solid #c1c6d7', width: '200px' }}>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div onClick={() => toggleActionFilter('pk')} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: actionFilters.pk ? '#4f46e5' : '#727786' }} title="Filter by Primary Key">
                        <KeyOutlined style={{ fontSize: '14px' }} />
                        <FilterOutlined style={{ fontSize: '10px', opacity: actionFilters.pk ? 1 : 0.5 }} />
                      </div>
                      <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>({pkCount})</span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div onClick={() => toggleActionFilter('ignored')} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: actionFilters.ignored ? '#4f46e5' : '#727786' }} title="Filter by Ignored">
                        <StopOutlined style={{ fontSize: '14px' }} />
                        <FilterOutlined style={{ fontSize: '10px', opacity: actionFilters.ignored ? 1 : 0.5 }} />
                      </div>
                      <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>({ignoredCount})</span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div onClick={() => toggleActionFilter('sensitive')} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: actionFilters.sensitive ? '#4f46e5' : '#727786' }} title="Filter by Sensitive">
                        <EyeInvisibleOutlined style={{ fontSize: '14px' }} />
                        <FilterOutlined style={{ fontSize: '10px', opacity: actionFilters.sensitive ? 1 : 0.5 }} />
                      </div>
                      <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>({sensitiveCount})</span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div onClick={() => toggleActionFilter('expanded')} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: actionFilters.expanded ? '#4f46e5' : '#727786' }} title="Filter by Expressions">
                        <CodeOutlined style={{ fontSize: '14px' }} />
                        <FilterOutlined style={{ fontSize: '10px', opacity: actionFilters.expanded ? 1 : 0.5 }} />
                      </div>
                      <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>({expandedCount})</span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div onClick={() => toggleActionFilter('orderStrict')} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', color: actionFilters.orderStrict ? '#4f46e5' : '#727786' }} title="Filter by strict order (structured columns)">
                        <OrderedListOutlined style={{ fontSize: '14px' }} />
                        <FilterOutlined style={{ fontSize: '10px', opacity: actionFilters.orderStrict ? 1 : 0.5 }} />
                      </div>
                      <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>({orderStrictCount})</span>
                    </div>

                  </div>
                </th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>SOURCE COLUMN</th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>SOURCE SAMPLE</th>
                <th style={{ padding: '12px 8px', fontSize: '12px', fontWeight: 600, color: '#414755', textAlign: 'center', width: '48px' }}></th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>TARGET COLUMN</th>
                <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: '#414755' }}>TARGET SAMPLE</th>
              </tr>
            </thead>
            <tbody>
              {loadingPreview ? (
                Array.from({ length: 4 }).map((_, idx) => (
                  <tr key={`skeleton-${idx}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px 16px', borderRight: '1px solid #c1c6d7', verticalAlign: 'top' }}>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <SkeletonBlock width="24px" height="24px" borderRadius="4px" />
                        <SkeletonBlock width="24px" height="24px" borderRadius="4px" />
                        <SkeletonBlock width="24px" height="24px" borderRadius="4px" />
                        <SkeletonBlock width="24px" height="24px" borderRadius="4px" />
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                      <SkeletonBlock width="120px" height="16px" />
                      <div style={{ marginTop: '8px' }}><SkeletonBlock width="60px" height="14px" /></div>
                    </td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                      <SkeletonBlock width="80px" height="22px" />
                    </td>
                    <td style={{ padding: '12px 8px', textAlign: 'center', verticalAlign: 'top' }}>
                      <ArrowRightOutlined style={{ color: '#e2e8f0' }} />
                    </td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                      <SkeletonBlock width="100px" height="24px" />
                    </td>
                    <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                      <SkeletonBlock width="80px" height="22px" />
                    </td>
                  </tr>
                ))
              ) : (
                pageRows.map(row => (
                  <React.Fragment key={row.id}>
                    <tr style={{ borderBottom: '1px solid #e5e2e1', backgroundColor: row.isExpanded ? '#fcf9f8' : row.isIgnored ? '#fcf9f8' : row.isPk ? '#eef2ff' : 'transparent', opacity: row.isIgnored ? 0.6 : 1, transition: 'background-color 0.2s' }}>
                      <td style={{ padding: '12px 16px', borderRight: '1px solid #c1c6d7', verticalAlign: 'top' }}>
                        <div style={{ display: 'flex', gap: '4px' }}>
                          <button onClick={() => toggleProperty(row.id, 'isPk')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isPk ? '#4f46e5' : 'transparent', color: row.isPk ? '#fff' : '#727786', cursor: 'pointer' }} title="Primary Key"><KeyOutlined /></button>
                          <button onClick={() => toggleProperty(row.id, 'isIgnored')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isIgnored ? '#414755' : 'transparent', color: row.isIgnored ? '#fff' : '#727786', cursor: 'pointer' }} title="Ignore"><StopOutlined /></button>
                          <button onClick={() => toggleProperty(row.id, 'isSensitive')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isSensitive ? 'rgba(186, 26, 26, 0.1)' : 'transparent', color: row.isSensitive ? '#ba1a1a' : '#727786', cursor: 'pointer' }} title="Sensitive">{row.isSensitive ? <EyeInvisibleOutlined /> : <EyeOutlined />}</button>
                          <button onClick={() => toggleProperty(row.id, 'isExpanded')} style={{ padding: '4px', borderRadius: '4px', border: 'none', background: row.isExpanded ? '#0057c2' : 'transparent', color: row.isExpanded ? '#fff' : '#727786', cursor: 'pointer' }} title="Expression"><CodeOutlined /></button>

                          {isComplexColumn(row, complexColumns) && (
                            <OrderSensitivityButton
                              strict={row.isOrderSensitive}
                              onToggle={() => toggleProperty(row.id, 'isOrderSensitive')}
                            />
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', verticalAlign: 'top', textDecoration: row.isIgnored ? 'line-through' : 'none' }}>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 500, color: '#1b1b1c', marginBottom: '4px' }}>{row.sourceCol}</div>
                        <span style={{
                          backgroundColor: isComplexColumn(row, complexColumns) ? '#eff6ff' : '#f0eded',
                          border: `1px solid ${isComplexColumn(row, complexColumns) ? '#93c5fd' : '#c1c6d7'}`,
                          padding: '2px 4px',
                          borderRadius: '4px',
                          fontSize: '10px',
                          fontWeight: 700,
                          color: isComplexColumn(row, complexColumns) ? '#1d4ed8' : '#727786',
                        }}>
                          {isComplexColumn(row, complexColumns) ? 'Structured' : row.sourceType}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', verticalAlign: 'top' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                          <code style={{ fontSize: '12px', color: '#475569', backgroundColor: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>{row.previewValue ? (row.isSensitive ? '*'.repeat(row.previewValue.length) : row.previewValue) : '—'}</code>
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
                              <code key={idx} style={{ fontSize: '12px', color: '#475569', backgroundColor: '#f8fafc', padding: '4px 6px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>{tc.sample ? (row.isSensitive ? '*'.repeat(tc.sample.length) : tc.sample) : '—'}</code>
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
                ))
              )}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderTop: '1px solid #e2e8f0', backgroundColor: '#fafafa', fontSize: '13px', color: '#64748b', flexShrink: 0 }}>
          <span>
            {filteredColumns.length === 0 && !loadingPreview
              ? 'Showing 0 attributes'
              : loadingPreview ? 'Loading...' : `Showing ${pageStart + 1}-${Math.min(pageStart + itemsPerPage, filteredColumns.length)} of ${filteredColumns.length} attributes`}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button disabled={safePage <= 1 || loadingPreview} onClick={() => setPage((p) => Math.max(1, p - 1))} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #e2e8f0', borderRadius: '6px', backgroundColor: '#fff', cursor: loadingPreview ? 'not-allowed' : 'pointer', color: '#475569', opacity: loadingPreview ? 0.5 : 1 }}><LeftOutlined /></button>
              <span style={{ minWidth: '88px', textAlign: 'center' }}>Page {safePage} of {totalPages}</span>
              <button disabled={safePage >= totalPages || loadingPreview} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #e2e8f0', borderRadius: '6px', backgroundColor: '#fff', cursor: loadingPreview ? 'not-allowed' : 'pointer', color: '#475569', opacity: loadingPreview ? 0.5 : 1 }}><RightOutlined /></button>
            </div>
            <select disabled={loadingPreview} value={itemsPerPage} onChange={(e) => { setItemsPerPage(Number(e.target.value)); setPage(1); }} style={{ padding: '4px', borderRadius: '4px', border: '1px solid #e2e8f0', backgroundColor: '#fff', color: '#475569', cursor: loadingPreview ? 'not-allowed' : 'pointer', opacity: loadingPreview ? 0.5 : 1 }}>
              <option value={10}>10/page</option>
              <option value={25}>25/page</option>
              <option value={50}>50/page</option>
            </select>
          </div>
        </div>
      </div>

    </div>
  );
};
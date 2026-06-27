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

import { ColumnMapping, FixedWidthColumnPreview, GoogleCloudStorageConfig } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { isFixedWidthFormat } from '../fixedWidthFormat';
import { resolveWizardJsonMode } from '../jsonFormat';
import { resolveWizardArchiveMode, archiveUsesTabularValidation } from '../archiveFormat';
import { FixedWidthLayoutPanel } from './FixedWidthLayoutPanel';
import { ArchiveValidationStep } from './ArchiveValidationStep';
import { JsonParentMappingStep } from './JsonParentMappingStep';
import styles from './ConfigureMappingStep.module.scss';

const PAGE_SIZE = 10;

const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string =>
  cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

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
    className={`${styles.orderBtn} ${strict ? styles.orderBtnStrict : ''}`}
  >
    {strict ? <OrderedListOutlined className={styles.iconSm} /> : <UnorderedListOutlined className={styles.iconSm} />}
    <span>{strict ? 'Order on' : 'Order off'}</span>
  </button>
);

const SkeletonBlock: React.FC<{ className?: string }> = ({ className }) => (
  <div className={`${styles.skeleton} ${className ?? ''}`} />
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
    <div className={styles.targetMappingWrap}>
      {targets.map((tc, idx) => (
        <div key={idx} className={styles.targetChipCol}>
          <span className={styles.targetChip}>
            {tc.name}
            <CloseOutlined onClick={() => onRemove(idx)} className={styles.targetChipClose} />
          </span>
          <span className={styles.targetTypeBadge}>
            {tc.type}
          </span>
        </div>
      ))}

      <div className={styles.addTargetWrap} ref={dropdownRef}>
        {availableColumns.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className={styles.addTargetBtn}
          >
            + Add target
          </button>
        )}

        {open && availableColumns.length > 0 && (
          <div className={styles.dropdownMenu}>
            {availableColumns.map(col => (
              <div
                key={col}
                onClick={() => { onAdd(col); setOpen(false); }}
                className={styles.dropdownItem}
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
  const previewColumnsState = useAppSelector((s) => s.validation.previewColumnsState);
  const previewFixedWidthState = useAppSelector((s) => s.validation.previewFixedWidthState);
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
  const [complexColumns, setComplexColumns] = useState<string[]>([]);
  const hydratedMappingsRef = useRef(false);

  const [itemsPerPage, setItemsPerPage] = useState(PAGE_SIZE);

  const sourceKey = cloudObjectKey(validationForm.sourceCloud);
  const targetKey = cloudObjectKey(validationForm.targetCloud);
  const previewPairKey = `${sourceKey}|${targetKey}|${validationForm.uidColumn}|${validationForm.delimiter}|${validationForm.hasHeader}`;
  const fixedWidthPairKey = previewPairKey;
  const previewError = previewColumnsState.pairKey === previewPairKey ? previewColumnsState.error : null;
  const fixedWidthLoading = previewFixedWidthState.pairKey === fixedWidthPairKey && previewFixedWidthState.isFetching;
  const fixedWidthError = previewFixedWidthState.pairKey === fixedWidthPairKey ? previewFixedWidthState.error : null;

  const loadingPreview = !isFixedWidth && !isJson && !isArchiveMetadataOnly && Boolean(
    validationForm.sourceCloud && validationForm.targetCloud && columnsMatrix.length === 0 && !previewError,
  ) && (previewColumnsState.pairKey !== previewPairKey || previewColumnsState.isFetching);

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

    dispatch(validationActions.previewFixedWidthLayoutRequest(fixedWidthPairKey));
  }, [
    isFixedWidth,
    validationForm.sourceCloud,
    validationForm.targetCloud,
    validationForm.uidColumn,
    validationForm.delimiter,
    validationForm.hasHeader,
    validationForm.fixedWidthColumns.length,
    fixedWidthPairKey,
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
      setPage(1);
      hydratedMappingsRef.current = true;
      return;
    }

    dispatch(validationActions.previewValidationColumnsRequest(previewPairKey));
  }, [
    validationForm.sourceCloud,
    validationForm.targetCloud,
    validationForm.uidColumn,
    validationForm.delimiter,
    validationForm.hasHeader,
    validationForm.columnMappings,
    previewPairKey,
    dispatch,
    isFixedWidth,
    isJson,
    isArchive,
  ]);

  useEffect(() => {
    if (hydratedMappingsRef.current) return;
    if (previewColumnsState.pairKey !== previewPairKey || !previewColumnsState.data) return;

    const preview = previewColumnsState.data;

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
        targetCols: targets.map((t) => {
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
        previewValue: sample,
      };
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
      <div className={styles.page}>
        <div>
          <h2 className={styles.heading}>
            Pegasus_Fixed_Width_Layout
          </h2>
          <div className={styles.pathRow}>
            <span><strong>Source:</strong> <code className={styles.codeChip}>{getCloudLabel(validationForm.sourceCloud)}</code></span>
            <span><strong>Target:</strong> <code className={styles.codeChip}>{getCloudLabel(validationForm.targetCloud)}</code></span>
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
  const loadingClass = loadingPreview ? styles.isLoading : '';

  const rowClassName = (row: ComplexMappingRow) => [
    styles.dataRow,
    row.isExpanded ? styles.rowExpanded : '',
    row.isIgnored ? styles.rowIgnored : '',
    row.isPk ? styles.rowPk : '',
  ].filter(Boolean).join(' ');

  const renderActionFilter = (
    key: keyof typeof actionFilters,
    title: string,
    icon: React.ReactNode,
    count: number,
  ) => (
    <div className={styles.actionFilterCol}>
      <div
        onClick={() => toggleActionFilter(key)}
        className={`${styles.actionFilterBtn} ${actionFilters[key] ? styles.actionFilterBtnActive : ''}`}
        title={title}
      >
        {icon}
        <FilterOutlined className={actionFilters[key] ? styles.filterIconActive : styles.filterIconMuted} />
      </div>
      <span className={styles.actionFilterCount}>({count})</span>
    </div>
  );

  return (
    <div className={styles.page}>

      <div className={styles.delimiterBar}>
        <label className={styles.delimiterLabel}>
          Delimiter
          <input
            type="text"
            value={validationForm.delimiter || ''}
            onChange={(e) => dispatch(validationActions.setValidationForm({ delimiter: e.target.value || 'auto' }))}
            className={`${styles.delimiterInput} ${loadingClass}`}
            disabled={loadingPreview}
          />
        </label>
        <label className={styles.delimiterLabel}>
          <input
            type="checkbox"
            checked={validationForm.hasHeader || false}
            onChange={(e) => dispatch(validationActions.setValidationForm({ hasHeader: e.target.checked }))}
            disabled={loadingPreview}
          />
          Header row
        </label>
      </div>

      <div className={styles.headerRow}>
        <div>
          <h2 className={styles.heading}>
            Pegasus_Data_Mapping
          </h2>
          <div className={styles.pathRow}>
            <span className={styles.pathItem}>
              <strong>Source:</strong> <code className={styles.codeChip}>{getCloudLabel(validationForm.sourceCloud)}</code>
            </span>
            <span className={styles.pathItem}>
              <strong>Target:</strong> <code className={styles.codeChip}>{getCloudLabel(validationForm.targetCloud)}</code>
            </span>
          </div>
        </div>
      </div>

      {previewError && <div className={styles.errorBanner}>{previewError}</div>}

      {!loadingPreview && complexCount > 0 && (
        <div className={styles.infoBanner}>
          <strong>{complexCount} column{complexCount === 1 ? '' : 's'}</strong> contain JSON, lists, or other structured values.
          Use the <strong>Order on / Order off</strong> control on those rows to choose whether element and key order must match between source and target.
        </div>
      )}

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <SearchOutlined className={styles.searchIcon} />
          <input
            type="text"
            placeholder="Filter attributes by names..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
            className={`${styles.searchInput} ${loadingClass}`}
            disabled={loadingPreview}
          />
        </div>

        <button
          type="button"
          onClick={() => { setShowUnmappedOnly(!showUnmappedOnly); setShowConfiguredOnly(false); setPage(1); }}
          disabled={loadingPreview}
          className={`${styles.filterBtn} ${showUnmappedOnly ? styles.filterBtnUnmappedActive : ''} ${loadingClass}`}
        >
          <FilterOutlined /> Unmapped Only
        </button>

        <button
          type="button"
          onClick={() => { setShowConfiguredOnly(!showConfiguredOnly); setShowUnmappedOnly(false); setPage(1); }}
          disabled={loadingPreview}
          className={`${styles.filterBtn} ${showConfiguredOnly ? styles.filterBtnConfiguredActive : ''} ${loadingClass}`}
        >
          <CheckCircleOutlined /> Configured ({configuredCount})
        </button>
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <thead className={styles.thead}>
              <tr>
                <th className={styles.thActions}>
                  <div className={styles.actionFiltersRow}>
                    {renderActionFilter('pk', 'Filter by Primary Key', <KeyOutlined className={styles.iconSm} />, pkCount)}
                    {renderActionFilter('ignored', 'Filter by Ignored', <StopOutlined className={styles.iconSm} />, ignoredCount)}
                    {renderActionFilter('sensitive', 'Filter by Sensitive', <EyeInvisibleOutlined className={styles.iconSm} />, sensitiveCount)}
                    {renderActionFilter('expanded', 'Filter by Expressions', <CodeOutlined className={styles.iconSm} />, expandedCount)}
                    {renderActionFilter('orderStrict', 'Filter by strict order (structured columns)', <OrderedListOutlined className={styles.iconSm} />, orderStrictCount)}
                  </div>
                </th>
                <th className={styles.thCell}>SOURCE COLUMN</th>
                <th className={styles.thCell}>SOURCE SAMPLE</th>
                <th className={styles.thCellCenter} />
                <th className={styles.thCell}>TARGET COLUMN</th>
                <th className={styles.thCell}>TARGET SAMPLE</th>
              </tr>
            </thead>
            <tbody>
              {loadingPreview ? (
                Array.from({ length: 4 }).map((_, idx) => (
                  <tr key={`skeleton-${idx}`} className={styles.skeletonRow}>
                    <td className={styles.tdActions}>
                      <div className={styles.skeletonActions}>
                        <SkeletonBlock className={styles.skeletonW24} />
                        <SkeletonBlock className={styles.skeletonW24} />
                        <SkeletonBlock className={styles.skeletonW24} />
                        <SkeletonBlock className={styles.skeletonW24} />
                      </div>
                    </td>
                    <td className={styles.td}>
                      <SkeletonBlock className={styles.skeletonW120} />
                      <div className={styles.skeletonMt8}><SkeletonBlock className={`${styles.skeletonW60} ${styles.skeletonH14}`} /></div>
                    </td>
                    <td className={styles.td}>
                      <SkeletonBlock className={`${styles.skeletonW80} ${styles.skeletonH22}`} />
                    </td>
                    <td className={styles.tdCenter}>
                      <ArrowRightOutlined className={styles.arrowSkeleton} />
                    </td>
                    <td className={styles.td}>
                      <SkeletonBlock className={`${styles.skeletonW100} ${styles.skeletonW24}`} />
                    </td>
                    <td className={styles.td}>
                      <SkeletonBlock className={`${styles.skeletonW80} ${styles.skeletonH22}`} />
                    </td>
                  </tr>
                ))
              ) : (
                pageRows.map(row => (
                  <React.Fragment key={row.id}>
                    <tr className={rowClassName(row)}>
                      <td className={styles.tdActions}>
                        <div className={styles.actionBtnGroup}>
                          <button type="button" onClick={() => toggleProperty(row.id, 'isPk')} className={`${styles.iconBtn} ${row.isPk ? styles.iconBtnPkActive : ''}`} title="Primary Key"><KeyOutlined /></button>
                          <button type="button" onClick={() => toggleProperty(row.id, 'isIgnored')} className={`${styles.iconBtn} ${row.isIgnored ? styles.iconBtnIgnoredActive : ''}`} title="Ignore"><StopOutlined /></button>
                          <button type="button" onClick={() => toggleProperty(row.id, 'isSensitive')} className={`${styles.iconBtn} ${row.isSensitive ? styles.iconBtnSensitiveActive : ''}`} title="Sensitive">{row.isSensitive ? <EyeInvisibleOutlined /> : <EyeOutlined />}</button>
                          <button type="button" onClick={() => toggleProperty(row.id, 'isExpanded')} className={`${styles.iconBtn} ${row.isExpanded ? styles.iconBtnExpandedActive : ''}`} title="Expression"><CodeOutlined /></button>

                          {isComplexColumn(row, complexColumns) && (
                            <OrderSensitivityButton
                              strict={row.isOrderSensitive}
                              onToggle={() => toggleProperty(row.id, 'isOrderSensitive')}
                            />
                          )}
                        </div>
                      </td>
                      <td className={`${styles.td} ${row.isIgnored ? styles.sourceColStrikethrough : ''}`}>
                        <div className={styles.sourceColName}>{row.sourceCol}</div>
                        <span className={`${styles.typeBadge} ${isComplexColumn(row, complexColumns) ? styles.typeBadgeStructured : ''}`}>
                          {isComplexColumn(row, complexColumns) ? 'Structured' : row.sourceType}
                        </span>
                      </td>
                      <td className={styles.td}>
                        <div className={styles.sampleCol}>
                          <code className={styles.sampleCode}>{row.previewValue ? (row.isSensitive ? '*'.repeat(row.previewValue.length) : row.previewValue) : '—'}</code>
                        </div>
                      </td>
                      <td className={`${styles.tdCenter} ${styles.arrowMuted}`}><ArrowRightOutlined /></td>
                      <td className={styles.td}>
                        {row.isIgnored ? <span className={styles.droppedText}>Dropped</span> : (
                          <TargetMappingField
                            targets={row.targetCols}
                            availableColumns={globalAvailableTargets}
                            onAdd={(col) => addTargetCol(row.id, col)}
                            onRemove={(idx) => removeTargetCol(row.id, idx)}
                          />
                        )}
                      </td>
                      <td className={styles.td}>
                        {!row.isIgnored && row.targetCols.length > 0 ? (
                          <div className={styles.targetSamplesCol}>
                            {row.targetCols.map((tc, idx) => (
                              <code key={idx} className={styles.sampleCode}>{tc.sample ? (row.isSensitive ? '*'.repeat(tc.sample.length) : tc.sample) : '—'}</code>
                            ))}
                          </div>
                        ) : (
                          <span className={styles.emptyDash}>—</span>
                        )}
                      </td>
                    </tr>

                    {row.isExpanded && !row.isIgnored && (
                      <tr className={styles.expressionRow}>
                        <td colSpan={6} className={styles.expressionCell}>
                          <div className={styles.expressionGrid}>
                            <div className={styles.expressionPanel}>
                              <div className={styles.expressionTabBar}>
                                <span className={styles.expressionTab}>Source Expression</span>
                              </div>
                              <textarea className={styles.expressionTextarea} placeholder="e.g. CAST(src.value AS STRING)" defaultValue={row.sourceExpr} />
                            </div>
                            <div className={styles.expressionPanel}>
                              <div className={styles.expressionTabBar}>
                                <span className={styles.expressionTab}>Target Expression</span>
                              </div>
                              <textarea className={styles.expressionTextarea} placeholder="e.g. DATE_TRUNC('day', val)" defaultValue={row.targetExpr} />
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

        <div className={styles.footer}>
          <span>
            {filteredColumns.length === 0 && !loadingPreview
              ? 'Showing 0 attributes'
              : loadingPreview ? 'Loading...' : `Showing ${pageStart + 1}-${Math.min(pageStart + itemsPerPage, filteredColumns.length)} of ${filteredColumns.length} attributes`}
          </span>
          <div className={styles.footerControls}>
            <div className={styles.pagination}>
              <button type="button" disabled={safePage <= 1 || loadingPreview} onClick={() => setPage((p) => Math.max(1, p - 1))} className={styles.pageBtn}><LeftOutlined /></button>
              <span className={styles.pageLabel}>Page {safePage} of {totalPages}</span>
              <button type="button" disabled={safePage >= totalPages || loadingPreview} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className={styles.pageBtn}><RightOutlined /></button>
            </div>
            <select disabled={loadingPreview} value={itemsPerPage} onChange={(e) => { setItemsPerPage(Number(e.target.value)); setPage(1); }} className={styles.pageSelect}>
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
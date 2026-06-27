import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowRightOutlined,
  OrderedListOutlined,
  UnorderedListOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { Api, ColumnMapping, GoogleCloudStorageConfig, JsonParentMappingRow } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import styles from './JsonParentMappingStep.module.scss';

const getCloudLabel = (cloud: string | GoogleCloudStorageConfig | null | undefined): string => {
  if (!cloud) return 'Pending';
  if (typeof cloud === 'string') return cloud;
  if (cloud.bucket && cloud.object_name) return `gs://${cloud.bucket}/${cloud.object_name}`;
  return cloud.object_name || 'GCS Source Configured';
};

type ParentRow = JsonParentMappingRow & { id: string };

const mappingsToRows = (mappings: JsonParentMappingRow[]): ParentRow[] =>
  mappings.map((row, index) => ({
    ...row,
    id: `${row.source_parent ?? 'extra'}-${row.target_parent ?? 'none'}-${index}`,
  }));

const rowsToColumnMappings = (rows: ParentRow[]): ColumnMapping[] =>
  rows
    .filter((row) => row.source_parent && row.target_parent && !row.ignored)
    .map((row) => ({
      source_column: row.source_parent as string,
      target_column: row.target_parent as string,
    }));

const OrderSensitivityButton: React.FC<{
  strict: boolean;
  onToggle: () => void;
}> = ({ strict, onToggle }) => (
  <button
    type="button"
    onClick={onToggle}
    title={
      strict
        ? 'Strict order: list element order and dict key order must match.'
        : 'Ignore order: reordered lists and dict keys still match.'
    }
    className={`${styles.orderBtn} ${strict ? styles.orderBtnStrict : ''}`}
  >
    {strict ? <OrderedListOutlined /> : <UnorderedListOutlined />}
    {strict ? 'Order matters' : 'Order ignored'}
  </button>
);

const TypeBadge: React.FC<{ value?: string | null }> = ({ value }) => (
  <span className={styles.typeBadge}>
    {value || 'unknown'}
  </span>
);

export const JsonParentMappingStep: React.FC = () => {
  const dispatch = useAppDispatch();
  const validationForm = useAppSelector((s) => s.validation.validationForm);

  const [rows, setRows] = useState<ParentRow[]>([]);
  const [targetParents, setTargetParents] = useState<string[]>([]);
  const [documentMode, setDocumentMode] = useState<string>('document');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dispatch(validationActions.setValidationForm({
      detectedFileFormat: 'json',
      delimiter: 'json',
      uidColumn: validationForm.uidColumn || 'document',
    }));
  }, [dispatch, validationForm.uidColumn]);

  useEffect(() => {
    if (!validationForm.sourceCloud || !validationForm.targetCloud) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    Api.previewJsonParentMapping({
      source_cloud: validationForm.sourceCloud,
      target_cloud: validationForm.targetCloud,
      uid_column: validationForm.uidColumn || 'document',
      file_format: 'json',
      delimiter: 'json',
      has_header: validationForm.hasHeader,
      column_mappings: [],
      test_mode: 'full',
    })
      .then((res) => {
        if (cancelled) return;
        const preview = res.data;
        setDocumentMode(preview.document_mode);
        setTargetParents(preview.target_parents.map((field) => field.key));
        let nextRows = mappingsToRows(preview.suggested_mappings);
        if (validationForm.columnMappings.length > 0) {
          const savedBySource = new Map(
            validationForm.columnMappings.map((mapping) => [mapping.source_column, mapping.target_column]),
          );
          nextRows = nextRows.map((row) => {
            if (!row.source_parent) return row;
            const savedTarget = savedBySource.get(row.source_parent);
            if (savedTarget) {
              return { ...row, target_parent: savedTarget, ignored: false };
            }
            if (savedBySource.has(row.source_parent)) {
              return { ...row, target_parent: null, ignored: true };
            }
            return row;
          });
        }
        setRows(nextRows);

        const uid = preview.document_mode === 'ndjson'
          ? (validationForm.uidColumn || preview.suggested_uid_field || 'id')
          : 'document';

        dispatch(validationActions.setValidationForm({
          detectedFileFormat: 'json',
          delimiter: 'json',
          uidColumn: uid,
          columnMappings: rowsToColumnMappings(nextRows),
        }));
      })
      .catch((err: { response?: { data?: { detail?: unknown } } }) => {
        if (cancelled) return;
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Could not load JSON parent mapping');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [validationForm.sourceCloud, validationForm.targetCloud]);

  const syncRows = (nextRows: ParentRow[]) => {
    setRows(nextRows);
    dispatch(validationActions.setValidationForm({
      columnMappings: rowsToColumnMappings(nextRows),
    }));
  };

  const mappedCount = useMemo(
    () => rows.filter((row) => row.source_parent && row.target_parent && !row.ignored).length,
    [rows],
  );

  const updateRow = (id: string, patch: Partial<ParentRow>) => {
    syncRows(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  return (
    <div className={styles.root}>
      <div>
        <h2 className={styles.title}>
          Pegasus_JSON_Mapping
        </h2>
        <div className={styles.metaRow}>
          <span><strong>Source:</strong> <code className={styles.codeChip}>{getCloudLabel(validationForm.sourceCloud)}</code></span>
          <span><strong>Target:</strong> <code className={styles.codeChip}>{getCloudLabel(validationForm.targetCloud)}</code></span>
        </div>
      </div>

      <div className={styles.infoBox}>
        Match top-level JSON parents between source and target. Nested fields under each matched parent are compared automatically.
        Use <strong>Order matters</strong> when list positions or dict key order must match exactly.
      </div>

      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <span className={styles.toolbarLabel}>Comparison order</span>
          <OrderSensitivityButton
            strict={validationForm.structuredOrderSensitive}
            onToggle={() => dispatch(validationActions.setValidationForm({
              structuredOrderSensitive: !validationForm.structuredOrderSensitive,
            }))}
          />
        </div>
        <span className={styles.mappedCount}>
          {mappedCount} parent{mappedCount === 1 ? '' : 's'} mapped
        </span>
      </div>

      {documentMode === 'ndjson' && (
        <label className={styles.uidLabel}>
          <span className={styles.toolbarLabel}>Record UID field</span>
          <input
            type="text"
            value={validationForm.uidColumn}
            onChange={(e) => dispatch(validationActions.setValidationForm({ uidColumn: e.target.value || 'id' }))}
            className={styles.uidInput}
          />
        </label>
      )}

      {error && (
        <div className={styles.errorBanner}>
          {error}
        </div>
      )}

      <div className={styles.table}>
        <div className={styles.tableHeader}>
          <span>Source parent</span>
          <span>Type</span>
          <span />
          <span>Target parent</span>
          <span>Type</span>
          <span>Ignore</span>
        </div>

        {loading ? (
          <div className={styles.tableMessage}>Loading JSON parents…</div>
        ) : rows.length === 0 ? (
          <div className={styles.tableMessage}>No top-level parents found.</div>
        ) : rows.map((row) => (
          <div
            key={row.id}
            className={`${styles.tableRow} ${row.ignored ? styles.tableRowIgnored : ''}`}
          >
            <code className={styles.rowCode}>
              {row.source_parent || <span className={styles.rowCodeMuted}>—</span>}
            </code>
            <TypeBadge value={row.source_type} />
            <ArrowRightOutlined className={styles.rowArrow} />
            {row.source_parent ? (
              <select
                value={row.target_parent ?? ''}
                onChange={(e) => updateRow(row.id, {
                  target_parent: e.target.value || null,
                  ignored: !e.target.value,
                })}
                className={styles.targetSelect}
              >
                <option value="">Unmapped</option>
                {targetParents.map((parent) => (
                  <option key={parent} value={parent}>{parent}</option>
                ))}
              </select>
            ) : (
              <code className={`${styles.rowCode} ${styles.rowCodeMuted}`}>
                {row.target_parent || '—'}
              </code>
            )}
            <TypeBadge value={row.target_type} />
            <button
              type="button"
              disabled={!row.source_parent}
              onClick={() => updateRow(row.id, { ignored: !row.ignored })}
              title={row.ignored ? 'Include in comparison' : 'Ignore this parent'}
              className={`${styles.ignoreBtn} ${row.ignored ? styles.ignoreBtnActive : ''} ${!row.source_parent ? styles.ignoreBtnDisabled : ''}`}
            >
              <StopOutlined />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

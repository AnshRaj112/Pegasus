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
    style={{
      padding: '8px 12px',
      borderRadius: '6px',
      border: `1px solid ${strict ? '#0057c2' : '#d9d9d9'}`,
      background: strict ? 'rgba(0, 87, 194, 0.1)' : '#fff',
      color: strict ? '#0057c2' : '#414755',
      cursor: 'pointer',
      fontSize: '12px',
      fontWeight: 600,
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
    }}
  >
    {strict ? <OrderedListOutlined /> : <UnorderedListOutlined />}
    {strict ? 'Order matters' : 'Order ignored'}
  </button>
);

const TypeBadge: React.FC<{ value?: string | null }> = ({ value }) => (
  <span style={{
    backgroundColor: '#f0eded',
    border: '1px solid #d9d9d9',
    padding: '2px 8px',
    borderRadius: '999px',
    fontSize: '11px',
    fontWeight: 700,
    color: '#727786',
    textTransform: 'uppercase',
  }}
  >
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1080px', margin: '0 auto', width: '100%' }}>
      <div>
        <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 8px 0', fontFamily: 'var(--font-mono)' }}>
          Pegasus_JSON_Mapping
        </h2>
        <div style={{ display: 'flex', gap: '16px', fontSize: '14px', color: '#414755', flexWrap: 'wrap' }}>
          <span><strong>Source:</strong> <code style={{ backgroundColor: '#f6f3f2', padding: '2px 6px', borderRadius: '4px' }}>{getCloudLabel(validationForm.sourceCloud)}</code></span>
          <span><strong>Target:</strong> <code style={{ backgroundColor: '#f6f3f2', padding: '2px 6px', borderRadius: '4px' }}>{getCloudLabel(validationForm.targetCloud)}</code></span>
        </div>
      </div>

      <div style={{ padding: '16px 20px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '14px', color: '#414755', lineHeight: 1.6 }}>
        Match top-level JSON parents between source and target. Nested fields under each matched parent are compared automatically.
        Use <strong>Order matters</strong> when list positions or dict key order must match exactly.
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#414755' }}>Comparison order</span>
          <OrderSensitivityButton
            strict={validationForm.structuredOrderSensitive}
            onToggle={() => dispatch(validationActions.setValidationForm({
              structuredOrderSensitive: !validationForm.structuredOrderSensitive,
            }))}
          />
        </div>
        <span style={{ fontSize: '13px', color: '#727786' }}>
          {mappedCount} parent{mappedCount === 1 ? '' : 's'} mapped
        </span>
      </div>

      {documentMode === 'ndjson' && (
        <label style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '320px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#414755' }}>Record UID field</span>
          <input
            type="text"
            value={validationForm.uidColumn}
            onChange={(e) => dispatch(validationActions.setValidationForm({ uidColumn: e.target.value || 'id' }))}
            style={{ height: '36px', borderRadius: '6px', border: '1px solid #e2e8f0', padding: '0 12px', fontFamily: 'var(--font-mono)' }}
          />
        </label>
      )}

      {error && (
        <div style={{ padding: '12px', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '8px', fontSize: '13px' }}>
          {error}
        </div>
      )}

      <div style={{ border: '1px solid #d9d9d9', borderRadius: '12px', overflow: 'hidden', backgroundColor: '#fff' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1.2fr 120px 40px 1.2fr 120px 72px',
          gap: '12px',
          padding: '12px 16px',
          backgroundColor: '#234B5F',
          color: '#fff',
          fontSize: '12px',
          fontWeight: 700,
          textTransform: 'uppercase',
        }}
        >
          <span>Source parent</span>
          <span>Type</span>
          <span />
          <span>Target parent</span>
          <span>Type</span>
          <span>Ignore</span>
        </div>

        {loading ? (
          <div style={{ padding: '32px', textAlign: 'center', color: '#727786' }}>Loading JSON parents…</div>
        ) : rows.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: '#727786' }}>No top-level parents found.</div>
        ) : rows.map((row) => (
          <div
            key={row.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '1.2fr 120px 40px 1.2fr 120px 72px',
              gap: '12px',
              padding: '14px 16px',
              alignItems: 'center',
              borderTop: '1px solid #f0eded',
              opacity: row.ignored ? 0.55 : 1,
              backgroundColor: row.ignored ? '#fcf9f8' : '#fff',
            }}
          >
            <code style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: '#1b1b1c' }}>
              {row.source_parent || <span style={{ color: '#727786' }}>—</span>}
            </code>
            <TypeBadge value={row.source_type} />
            <ArrowRightOutlined style={{ color: '#727786', justifySelf: 'center' }} />
            {row.source_parent ? (
              <select
                value={row.target_parent ?? ''}
                onChange={(e) => updateRow(row.id, {
                  target_parent: e.target.value || null,
                  ignored: !e.target.value,
                })}
                style={{
                  height: '34px',
                  borderRadius: '6px',
                  border: '1px solid #d9d9d9',
                  padding: '0 10px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '13px',
                  backgroundColor: '#fff',
                }}
              >
                <option value="">Unmapped</option>
                {targetParents.map((parent) => (
                  <option key={parent} value={parent}>{parent}</option>
                ))}
              </select>
            ) : (
              <code style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: '#727786' }}>
                {row.target_parent || '—'}
              </code>
            )}
            <TypeBadge value={row.target_type} />
            <button
              type="button"
              disabled={!row.source_parent}
              onClick={() => updateRow(row.id, { ignored: !row.ignored })}
              title={row.ignored ? 'Include in comparison' : 'Ignore this parent'}
              style={{
                justifySelf: 'center',
                padding: '6px',
                borderRadius: '4px',
                border: 'none',
                background: row.ignored ? '#414755' : 'transparent',
                color: row.ignored ? '#fff' : '#727786',
                cursor: row.source_parent ? 'pointer' : 'not-allowed',
              }}
            >
              <StopOutlined />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

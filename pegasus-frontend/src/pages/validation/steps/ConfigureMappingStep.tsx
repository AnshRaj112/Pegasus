import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  KeyOutlined, CloseCircleFilled, CheckCircleOutlined, SyncOutlined, HolderOutlined
} from '@ant-design/icons';

import { Api } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { ValidationReport } from '../components/ValidationReport';

interface MappingItem {
  id: string;
  sourceColumn: string;
  targetMappings: string[];
  previewValue: string;
}

const inferType = (value: string): string => {
  if (/^(true|false)$/i.test(value)) return 'Bool';
  if (/^-?\d+$/.test(value)) return 'Int';
  if (/^-?\d+\.\d+$/.test(value)) return 'Float';
  return 'String';
};

export const ConfigureMappingStep: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const validationForm = useAppSelector((s) => s.validation.validationForm);
  const { data: validationResult, isFetching, error } = useAppSelector((s) => s.validation.validationDataState);
  const [searchQuery, setSearchQuery] = useState('');
  const [columnsMatrix, setColumnsMatrix] = useState<MappingItem[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const loadingPreview = Boolean(
    validationForm.sourcePath && validationForm.targetPath && columnsMatrix.length === 0 && !previewError,
  );
  const [viewDetailedReport, setViewDetailedReport] = useState(false);

  const selectedUidColumn = validationForm.uidColumn;
  const overrideDelimiter = validationForm.delimiter;

  useEffect(() => {
    if (!validationForm.sourcePath || !validationForm.targetPath) return;
    let cancelled = false;
    Api.previewLocalColumns({
      source_path: validationForm.sourcePath,
      target_path: validationForm.targetPath,
      uid_column: validationForm.uidColumn,
      delimiter: validationForm.delimiter,
    })
      .then((res) => {
        if (cancelled) return;
        const preview = res.data;
        const mappings: MappingItem[] = preview.compare_columns.map((col) => {
          const auto = preview.auto_mappings.find((m) => m.source_column === col);
          const targets = auto ? [auto.target_column] : [];
          const sample = preview.source_samples[col]?.[0] ?? '';
          return { id: col, sourceColumn: col, targetMappings: targets, previewValue: sample };
        });
        setColumnsMatrix(mappings);
        const uid = preview.source_columns.includes(validationForm.uidColumn)
          ? validationForm.uidColumn
          : preview.source_columns[0] ?? 'id';
        dispatch(validationActions.setValidationForm({
          uidColumn: uid,
          delimiter: preview.delimiter,
          columnMappings: preview.auto_mappings.map((m) => ({
            source_column: m.source_column,
            target_column: m.target_column,
          })),
        }));
      })
      .catch(() => {
        if (!cancelled) setPreviewError('Could not load column preview from server');
      });
    return () => { cancelled = true; };
  }, [validationForm.sourcePath, validationForm.targetPath, validationForm.uidColumn, validationForm.delimiter, dispatch]);

  const handleUidChange = (uid: string) => {
    dispatch(validationActions.setValidationForm({ uidColumn: uid }));
  };

  const handleDelimiterChange = (delimiter: string) => {
    dispatch(validationActions.setValidationForm({ delimiter: delimiter || 'auto' }));
  };

  const filteredColumns = columnsMatrix.filter((col) =>
    col.sourceColumn.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const results = validationResult?.results;

  if (viewDetailedReport) {
    return (
      <ValidationReport
        jobId={validationResult?.jobId ?? undefined}
        onBack={() => setViewDetailedReport(false)}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h1 style={{ fontSize: '22px', margin: 0, fontWeight: 600 }}>Mapping Configuration Matrix</h1>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #d9d9d9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            Delimiter:
            <input
              type="text"
              value={overrideDelimiter}
              onChange={(e) => handleDelimiterChange(e.target.value)}
              style={{ width: '64px', height: '32px', textAlign: 'center', borderRadius: '6px', border: '1px solid #d9d9d9' }}
            />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <KeyOutlined style={{ color: '#fa8c16' }} /> UID:
            <select
              value={selectedUidColumn}
              onChange={(e) => handleUidChange(e.target.value)}
              style={{ height: '32px', padding: '0 8px', borderRadius: '6px', border: '1px solid #d9d9d9' }}
            >
              {columnsMatrix.map((col) => (
                <option key={col.id} value={col.sourceColumn}>{col.sourceColumn}</option>
              ))}
            </select>
          </label>
        </div>
        <span style={{ fontSize: '13px', color: '#727786' }}>
          {loadingPreview ? 'Loading columns…' : `${columnsMatrix.length} columns`}
        </span>
      </div>

      {previewError && <p style={{ color: '#ba1a1a', margin: 0, fontSize: '13px' }}>{previewError}</p>}

      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #d9d9d9', overflow: 'hidden' }}>
        <div style={{ padding: '16px', borderBottom: '1px solid #d9d9d9' }}>
          <input
            type="text"
            placeholder="Filter columns..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: '8px', border: '1px solid #d9d9d9', width: '320px' }}
          />
        </div>
        <div className="custom-scrollbar" style={{ overflowY: 'auto', maxHeight: '350px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', fontSize: '11px', textTransform: 'uppercase' }}>
                <th style={{ padding: '12px', textAlign: 'left' }}>Source</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Type</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Target</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Preview</th>
              </tr>
            </thead>
            <tbody>
              {filteredColumns.map((row) => (
                <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: row.sourceColumn === selectedUidColumn ? '#fffbe6' : 'transparent' }}>
                  <td style={{ padding: '12px' }}>
                    <HolderOutlined style={{ marginRight: '8px', color: '#94a3b8' }} />
                    {row.sourceColumn}
                  </td>
                  <td style={{ padding: '12px' }}>{inferType(row.previewValue)}</td>
                  <td style={{ padding: '12px' }}>{row.targetMappings.join(', ') || '—'}</td>
                  <td style={{ padding: '12px' }}><code>{row.previewValue || '—'}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {isFetching && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#1677ff' }}>
          <SyncOutlined spin /> Running validation on server…
        </div>
      )}

      {error && (
        <div style={{ backgroundColor: '#ffdad6', border: '1px solid #ba1a1a', padding: '16px', borderRadius: '8px' }}>
          <CloseCircleFilled style={{ color: '#ba1a1a', marginRight: '8px' }} />
          {error}
        </div>
      )}

      {validationResult?.status === 'Complete' && results && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h3 style={{ margin: 0, fontSize: '16px' }}>Validation Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
            <Stat label="Match" value={results.summary.is_match ? 'YES' : 'NO'} color={results.summary.is_match ? '#16a34a' : '#ba1a1a'} />
            <Stat label="Source Rows" value={results.summary.source_row_count.toLocaleString()} />
            <Stat label="Target Rows" value={results.summary.target_row_count.toLocaleString()} />
            <Stat label="Mismatches" value={results.summary.total_mismatch_records.toLocaleString()} color="#ba1a1a" />
            <Stat label="Run Time" value={`${(results.durations?.validation_seconds ?? results.durations?.total_seconds ?? 0).toFixed(2)}s`} color="#1677ff" />
          </div>
          <button
            type="button"
            onClick={() => (validationResult.jobId ? navigate(`/validation/report/${validationResult.jobId}`) : setViewDetailedReport(true))}
            style={{ alignSelf: 'center', padding: '10px 24px', backgroundColor: '#ffffff', color: '#1677ff', border: '1px solid #1677ff', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <CheckCircleOutlined /> View Detailed Report
          </button>
        </div>
      )}
    </div>
  );
};

const Stat: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color = '#1b1b1c' }) => (
  <div style={{ backgroundColor: '#fff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
    <p style={{ margin: 0, fontSize: '12px', color: '#727786', textTransform: 'uppercase' }}>{label}</p>
    <p style={{ margin: '8px 0 0', fontSize: '18px', fontWeight: 700, color }}>{value}</p>
  </div>
);

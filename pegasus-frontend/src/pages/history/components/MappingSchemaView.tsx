import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftOutlined } from '@ant-design/icons';

import { Api, type ColumnMapping, type ValidationHistoryDetail } from '../../../shared/api/Api';
import styles from '../History.module.scss';

const formatColumns = (primary: string, extras?: string[] | null): string => {
  const all = [primary, ...(extras ?? [])].filter(Boolean);
  return all.length > 1 ? all.join(', ') : primary || '—';
};

const MappingRow: React.FC<{ mapping: ColumnMapping; index: number }> = ({ mapping, index }) => {
  const sourceCols = formatColumns(
    mapping.source_column,
    mapping.source_columns?.filter((c) => c !== mapping.source_column),
  );
  const targetCol = mapping.target_column || mapping.source_column;
  const targetCols = formatColumns(
    targetCol,
    mapping.target_columns?.filter((c) => c !== targetCol),
  );

  return (
    <tr className={styles.antTableRow}>
      <td style={{ textAlign: 'center', color: '#727786', fontSize: '12px' }}>{index + 1}</td>
      <td>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: '#1b1b1c' }}>{sourceCols}</span>
      </td>
      <td style={{ textAlign: 'center', color: '#727786' }}>→</td>
      <td>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: '#1b1b1c' }}>{targetCols}</span>
      </td>
      <td>
        <span style={{ background: '#f0eded', padding: '4px 8px', borderRadius: '4px', fontSize: '12px' }}>
          {mapping.compare_mode ?? 'auto'}
        </span>
      </td>
    </tr>
  );
};

export const MappingSchemaView: React.FC = () => {
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<ValidationHistoryDetail | null>(null);

  useEffect(() => {
    if (!runId) return;

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await Api.getValidationHistoryRun(runId);
        if (!cancelled) setDetail(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load mapping schema');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => { cancelled = true; };
  }, [runId]);

  const mappings = detail?.column_mappings ?? [];

  return (
    <div className={styles.historyLayout}>
      <div className={styles.historyTopHeader}>
        <div>
          <span style={{ fontSize: '12px', color: '#727786', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>
            Mapping schema
          </span>
          <h1 style={{ fontSize: '32px', color: '#1b1b1c', margin: '4px 0 0 0', fontWeight: 600, letterSpacing: '-0.02em' }}>
            Source → Target Mapping
          </h1>
          {detail && (
            <p style={{ fontSize: '14px', color: '#414755', margin: '8px 0 0 0' }}>
              {detail.source_filename ?? 'Source'} → {detail.target_filename ?? 'Target'}
              {detail.uid_column ? ` · UID: ${detail.uid_column}` : ''}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => navigate(-1)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer' }}
        >
          <ArrowLeftOutlined /> Back
        </button>
      </div>

      <div className={styles.historyMasterCard}>
        {loading && (
          <p style={{ padding: '32px', margin: 0, color: '#727786' }}>Loading mapping schema…</p>
        )}
        {error && (
          <p style={{ padding: '32px', margin: 0, color: '#ba1a1a' }}>{error}</p>
        )}
        {!loading && !error && detail && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '16px', padding: '20px 24px', borderBottom: '1px solid #e8e8e8' }}>
              <div>
                <p style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#727786', textTransform: 'uppercase' }}>Source</p>
                <p style={{ margin: '4px 0 0 0', fontSize: '13px', fontWeight: 600 }}>{detail.source_filename ?? '—'}</p>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', fontFamily: 'var(--font-mono)', color: '#414755', wordBreak: 'break-all' }}>{detail.source_path ?? '—'}</p>
              </div>
              <div>
                <p style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#727786', textTransform: 'uppercase' }}>Target</p>
                <p style={{ margin: '4px 0 0 0', fontSize: '13px', fontWeight: 600 }}>{detail.target_filename ?? '—'}</p>
                <p style={{ margin: '4px 0 0 0', fontSize: '12px', fontFamily: 'var(--font-mono)', color: '#414755', wordBreak: 'break-all' }}>{detail.target_path ?? '—'}</p>
              </div>
            </div>

            <div className={styles.historyTableScrollFrame}>
              <table className={styles.antTableLayout}>
                <thead>
                  <tr>
                    <th style={{ width: '48px', textAlign: 'center' }}>#</th>
                    <th style={{ width: '40%' }}>Source Column(s)</th>
                    <th style={{ width: '48px', textAlign: 'center' }} />
                    <th style={{ width: '40%' }}>Target Column(s)</th>
                    <th>Compare Mode</th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '32px', color: '#727786' }}>
                        No column mappings saved for this record.
                      </td>
                    </tr>
                  ) : (
                    mappings.map((mapping, index) => (
                      <MappingRow key={`${mapping.source_column}-${index}`} mapping={mapping} index={index} />
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

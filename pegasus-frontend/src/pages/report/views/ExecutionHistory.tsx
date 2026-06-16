import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  PlayCircleOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  CalendarOutlined,
  FileTextOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { ReportService } from '../Report.service';
import type { ValidationHistorySummary } from '../../../shared/api/Api';

const formatEnd = (iso: string | null | undefined) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  return `${date} | ${time}`;
};

const formatDuration = (sec: number | null | undefined) => {
  if (sec == null || !Number.isFinite(sec)) return '—';
  if (sec < 60) return `${Math.round(sec)} sec`;
  return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`;
};

export const ExecutionHistory: React.FC = () => {
  const navigate = useNavigate();
  const { mappingId } = useParams<{ mappingId: string }>();
  const [runs, setRuns] = useState<ValidationHistorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pairLabel, setPairLabel] = useState('');

  useEffect(() => {
    if (!mappingId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const { sourcePath, targetPath } = await ReportService.resolvePairByMappingId(mappingId);
        const items = await ReportService.fetchRunsForPair(sourcePath, targetPath);
        if (cancelled) return;
        setRuns(items);
        const short = sourcePath.replace(/\\/g, '/').split('/').pop() ?? sourcePath;
        setPairLabel(short);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load history');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [mappingId]);

  const MAPPING_NAME = pairLabel || mappingId || 'Report';

  if (loading) {
    return <div style={{ padding: '32px', color: '#64748b' }}>Loading execution history…</div>;
  }

  if (error) {
    return <div style={{ padding: '32px', color: '#ba1a1a' }}>{error}</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '12px' }}>
            <span onClick={() => navigate('/reports')} style={{ cursor: 'pointer' }} onMouseEnter={(e) => { e.currentTarget.style.color = '#0057c2'; }} onMouseLeave={(e) => { e.currentTarget.style.color = '#64748b'; }}>Reports</span>
            <RightOutlined style={{ fontSize: '10px' }} />
            <span style={{ color: '#0057c2', fontWeight: 500 }}>{MAPPING_NAME}</span>
            <RightOutlined style={{ fontSize: '10px' }} />
            <span style={{ color: '#1b1b1c', fontWeight: 500 }}>History</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ backgroundColor: '#f0eded', border: '1px solid #c1c6d7', padding: '4px 12px', borderRadius: '999px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BranchesOutlined style={{ color: '#414755', fontSize: '14px' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#1b1b1c', fontWeight: 600 }}>{MAPPING_NAME}</span>
              {runs[0] && (
                <span style={{ marginLeft: '8px', fontWeight: 700, color: runs[0].is_match ? '#16a34a' : '#ba1a1a' }}>
                  {runs[0].is_match ? 'P' : 'F'}
                </span>
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button type="button" onClick={() => navigate('/validations')} style={{ backgroundColor: '#0057c2', border: 'none', color: '#fff', padding: '8px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer' }}>
            <PlayCircleOutlined /> Run Validation
          </button>
        </div>
      </div>

      {runs.length === 0 ? (
        <div style={{ padding: '32px', color: '#64748b', textAlign: 'center' }}>No validation runs for this file pair yet.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {runs.map((run, idx) => {
            const mc = run.mismatch_counts;
            const totalMis = mc.missing_in_target + mc.extra_in_target + mc.value_mismatch;
            return (
              <div key={run.run_id} style={{ backgroundColor: '#fff', border: '1px solid #e5e2e1', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', opacity: idx > 0 ? 0.85 : 1 }}>
                <div style={{ backgroundColor: '#fcf9f8', borderBottom: '1px solid #e5e2e1', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                    <span style={{ fontSize: '18px', fontWeight: 600, color: '#1b1b1c', fontFamily: 'var(--font-mono)' }}>{run.run_id}</span>
                    <span style={{ fontWeight: 700, color: run.is_match ? '#16a34a' : '#ba1a1a' }}>{run.is_match ? 'P' : 'F'}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', color: '#64748b', fontSize: '12px' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><ClockCircleOutlined /> {formatDuration(run.durations?.validation_seconds ?? run.durations?.total_seconds)}</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><CalendarOutlined /> Ended: {formatEnd(run.completed_at ?? run.created_at)}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => mappingId && navigate(`/reports/${mappingId}/history/${run.run_id}/snippet`)}
                    style={{ backgroundColor: '#fff', border: '1px solid #c1c6d7', color: '#1b1b1c', padding: '6px 12px', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500, cursor: 'pointer' }}
                  >
                    <FileTextOutlined /> Snippet
                  </button>
                </div>
                <div style={{ overflowX: 'auto', display: 'flex', padding: '16px 24px', gap: '24px' }}>
                  <MetricItem label="Source Rows" value={run.source_row_count != null ? run.source_row_count.toLocaleString() : '—'} />
                  <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
                  <MetricItem label="Target Rows" value={run.target_row_count != null ? run.target_row_count.toLocaleString() : '—'} />
                  <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
                  <MetricItem label="Cell Mismatch" value={String(mc.value_mismatch)} color={mc.value_mismatch ? '#ba1a1a' : '#1b1b1c'} />
                  <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
                  <MetricItem label="Extra Rows" value={String(mc.extra_in_target)} />
                  <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
                  <MetricItem label="Missing Rows" value={String(mc.missing_in_target)} />
                  <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
                  <MetricItem label="Total Mismatched" value={String(totalMis)} />
                  <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
                  <MetricItem label="Mapped Cols" value={String(run.mapping_count)} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const MetricItem: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color = '#1b1b1c' }) => (
  <div style={{ display: 'flex', flexDirection: 'column', minWidth: '120px' }}>
    <span style={{ fontSize: '10px', fontWeight: 700, color: '#727786', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>{label}</span>
    <span style={{ fontSize: '20px', fontWeight: 600, color }}>{value}</span>
  </div>
);

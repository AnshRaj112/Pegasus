import React, { useEffect, useState } from 'react';
import {
  PlayCircleOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  CalendarOutlined,
  FileTextOutlined,
  RightOutlined,
  FileOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useAppDispatch } from '../../../redux/store';
import { ReportService } from '../Report.service';
import { ValidationHistorySummary } from '../../../shared/api/Api';
import { validationActions } from '../../validation/Validation.reducer';
import styles from './ExecutionHistory.module.scss';

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

const MetricItem: React.FC<{ label: string; value: string; errorTone?: boolean }> = ({ label, value, errorTone }) => (
  <div className={styles.metricItem}>
    <span className={styles.metricLabel}>{label}</span>
    <span className={`${styles.metricValue} ${errorTone ? styles.metricValueError : ''}`}>{value}</span>
  </div>
);

const ExecutionHistory: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { mappingId } = useParams<{ mappingId: string }>();

  const [runs, setRuns] = useState<ValidationHistorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pairLabel, setPairLabel] = useState('');

  const [sourceFileInfo, setSourceFileInfo] = useState<{ name: string; path: string } | null>(null);
  const [targetFileInfo, setTargetFileInfo] = useState<{ name: string; path: string } | null>(null);

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

        const shortSource = sourcePath.replace(/\\/g, '/').split('/').pop() ?? sourcePath;
        const shortTarget = targetPath.replace(/\\/g, '/').split('/').pop() ?? targetPath;

        setPairLabel(shortSource);
        setSourceFileInfo({ name: shortSource, path: sourcePath });
        setTargetFileInfo({ name: shortTarget, path: targetPath });
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load history');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [mappingId]);

  const MAPPING_NAME = pairLabel;

  if (loading) {
    return <div className={styles.loading}>Loading execution history…</div>;
  }

  if (error) {
    return <div className={styles.error}>{error}</div>;
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.breadcrumb}>
            <span className={styles.breadcrumbLink} onClick={() => navigate('/reports')}>Reports</span>
            <RightOutlined className={styles.breadcrumbIcon} />
            <span className={styles.breadcrumbActive}>{MAPPING_NAME}</span>
            <RightOutlined className={styles.breadcrumbIcon} />
            <span className={styles.breadcrumbCurrent}>History</span>
          </div>
          <div className={styles.mappingBadge}>
            <BranchesOutlined className={styles.mappingIcon} />
            <span className={styles.mappingName}>{MAPPING_NAME}</span>
            {runs[0] && (
              <span className={runs[0].is_match ? styles.passBadge : styles.failBadge}>
                {runs[0].is_match ? 'P' : 'F'}
              </span>
            )}
          </div>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            disabled={!runs[0]?.run_id}
            onClick={() => runs[0]?.run_id && dispatch(validationActions.runValidationFromHistoryRequest(runs[0].run_id))}
            className={styles.runBtn}
          >
            <PlayCircleOutlined /> Run Validation
          </button>
        </div>
      </div>

      {sourceFileInfo && targetFileInfo && (
        <div className={styles.fileCard}>
          <div className={styles.fileSection}>
            <div className={styles.fileTitleRow}>
              <FileOutlined className={styles.fileIcon} />
              <span className={styles.fileName}>{sourceFileInfo.name}</span>
              <span className={styles.fileLabel}>(Source)</span>
            </div>
            <div className={styles.filePath}>{sourceFileInfo.path}</div>
          </div>

          <div className={styles.fileSection}>
            <div className={styles.fileTitleRow}>
              <FileOutlined className={styles.fileIcon} />
              <span className={styles.fileName}>{targetFileInfo.name}</span>
              <span className={styles.fileLabel}>(Target)</span>
            </div>
            <div className={styles.filePath}>{targetFileInfo.path}</div>
          </div>
        </div>
      )}

      {runs.length === 0 ? (
        <div className={styles.emptyState}>No validation runs for this file pair yet.</div>
      ) : (
        <div className={styles.runsList}>
          {runs.map((run, idx) => {
            const mc = run.mismatch_counts;
            const totalRowMismatched = mc.value_mismatch_rows != null ? mc.value_mismatch_rows : mc.value_mismatch;
            const totalRowErrors = totalRowMismatched + mc.extra_in_target + mc.missing_in_target;
            const isLitmus = run.test_mode === 'litmus';
            const passed = run.is_match === true;
            return (
              <div key={run.run_id} className={`${styles.runCard} ${idx > 0 ? styles.runCardFaded : ''}`}>
                <div className={styles.runHeader}>
                  <div className={styles.runHeaderLeft}>
                    <span className={styles.runTitle}>{MAPPING_NAME}</span>
                    <span className={passed ? styles.runPass : styles.runFail}>{passed ? 'P' : 'F'}</span>
                    <div className={styles.runMeta}>
                      <span className={styles.runMetaItem}><ClockCircleOutlined /> {formatDuration(run.durations?.validation_seconds ?? run.durations?.total_seconds)}</span>
                      <span className={styles.runMetaItem}><CalendarOutlined /> Ended: {formatEnd(run.completed_at ?? run.created_at)}</span>
                    </div>
                  </div>
                  {!isLitmus && (
                    <button
                      type="button"
                      onClick={() => mappingId && navigate(`/reports/${mappingId}/history/${run.run_id}/snippet`)}
                      className={styles.snippetBtn}
                    >
                      <FileTextOutlined /> Snippet
                    </button>
                  )}
                </div>
                <div className={styles.metricsRow}>
                  <MetricItem label="Source Rows" value={run.source_row_count != null ? run.source_row_count.toLocaleString() : '—'} />
                  <div className={styles.metricDivider} />
                  <MetricItem label="Target Rows" value={run.target_row_count != null ? run.target_row_count.toLocaleString() : '—'} />
                  <div className={styles.metricDivider} />
                  <MetricItem label="Cell Mismatch" value={String(mc.value_mismatch)} errorTone={Boolean(mc.value_mismatch)} />
                  <div className={styles.metricDivider} />
                  <MetricItem label="Total Row Mismatched" value={String(totalRowMismatched)} />
                  <div className={styles.metricDivider} />
                  <MetricItem label="Extra Rows" value={String(mc.extra_in_target)} />
                  <div className={styles.metricDivider} />
                  <MetricItem label="Missing Rows" value={String(mc.missing_in_target)} />
                  <div className={styles.metricDivider} />
                  <MetricItem label="Total Row Errors" value={String(totalRowErrors)} />
                  <div className={styles.metricDivider} />
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

export default ExecutionHistory;

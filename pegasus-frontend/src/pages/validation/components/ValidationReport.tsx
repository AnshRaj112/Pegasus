import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeftOutlined,
  ExclamationCircleFilled,
  CheckCircleFilled,
  SyncOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';

import {
  Api,
  type ValidateResult,
  type ValidationHistoryDetail,
} from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { reportActions } from '../../report/Report.reducer';
import { validationActions } from '../Validation.reducer';
import { getActiveSession, removeActiveSession } from '../validationSessionStorage';

type ActiveSectionTab = 'mismatches' | 'missing' | 'extra';

interface ReportMeta {
  jobId: string | null;
  runId: string | null;
  sourceLabel: string | null;
  targetLabel: string | null;
  uidColumn: string | null;
  delimiter: string | null;
  isMatch: boolean;
  sourceRowCount: number;
  targetRowCount: number;
  comparedColumnCount: number;
  comparedColumns: string[];
}

interface ValidationReportProps {
  onBack?: () => void;
  jobId?: string;
  runId?: string;
  initialResult?: ValidateResult | null;
}

const TAB_TO_TYPE: Record<ActiveSectionTab, string> = {
  mismatches: 'value_mismatch',
  missing: 'missing_in_target',
  extra: 'extra_in_target',
};

const pickInitialTab = (counts: ValidateResult['mismatch_counts']): ActiveSectionTab => {
  if (counts.value_mismatch > 0) return 'mismatches';
  if (counts.missing_in_target > 0) return 'missing';
  if (counts.extra_in_target > 0) return 'extra';
  return 'mismatches';
};

const normalizeRecord = (raw: unknown): Record<string, unknown> | null => {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    try {
      return normalizeRecord(JSON.parse(trimmed));
    } catch {
      return null;
    }
  }
  if (typeof raw !== 'object' || Array.isArray(raw)) return null;
  return raw as Record<string, unknown>;
};

const historyToResult = (history: ValidationHistoryDetail): ValidateResult => ({
  summary: {
    source_row_count: history.source_row_count ?? 0,
    target_row_count: history.target_row_count ?? 0,
    total_mismatch_records:
      history.mismatch_counts.missing_in_target
      + history.mismatch_counts.extra_in_target
      + history.mismatch_counts.value_mismatch,
    is_match: history.is_match ?? false,
  },
  mismatch_counts: history.mismatch_counts,
  mismatch_sample_groups: {
    missing_in_target: [],
    extra_in_target: [],
    value_mismatch: [],
  },
  run_id: history.run_id,
  durations: history.durations,
});

const metaFromHistory = (history: ValidationHistoryDetail): ReportMeta => ({
  jobId: null,
  runId: history.run_id,
  sourceLabel: history.source_path ?? history.source_filename,
  targetLabel: history.target_path ?? history.target_filename,
  uidColumn: history.uid_column,
  delimiter: history.delimiter,
  isMatch: history.is_match ?? false,
  sourceRowCount: history.source_row_count ?? 0,
  targetRowCount: history.target_row_count ?? 0,
  comparedColumnCount: history.compared_column_count ?? history.compared_columns.length,
  comparedColumns: history.compared_columns ?? [],
});

const metaFromResult = (result: ValidateResult, jobId: string | null): ReportMeta => ({
  jobId,
  runId: result.run_id,
  sourceLabel: null,
  targetLabel: null,
  uidColumn: null,
  delimiter: null,
  isMatch: result.summary.is_match,
  sourceRowCount: result.summary.source_row_count,
  targetRowCount: result.summary.target_row_count,
  comparedColumnCount: result.summary.compared_column_count ?? result.compared_columns?.length ?? 0,
  comparedColumns: result.compared_columns ?? [],
});

export const ValidationReport: React.FC<ValidationReportProps> = ({
  onBack,
  jobId: jobIdProp,
  runId: runIdProp,
  initialResult: initialResultProp,
}) => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { jobId: routeJobId, runId: routeRunId } = useParams<{ jobId?: string; runId?: string }>();
  const jobId = jobIdProp ?? routeJobId ?? null;
  const runIdParam = runIdProp ?? routeRunId ?? null;
  const pendingReportJobId = useAppSelector((s) => s.validation.pendingReportJobId);

  const [activeTab, setActiveTab] = useState<ActiveSectionTab>('mismatches');
  const [pageSize] = useState<number>(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reportMeta, setReportMeta] = useState<ReportMeta | null>(null);
  const [serverPageActive, setServerPageActive] = useState(false);
  const [comparedColumns, setComparedColumns] = useState<string[]>([]);
  const [statsOverview, setStatsOverview] = useState({
    totalWrong: 0,
    mismatchedCount: 0,
    missingCount: 0,
    extraCount: 0,
  });
  const [tabTotals, setTabTotals] = useState<Record<ActiveSectionTab, number>>({
    mismatches: 0,
    missing: 0,
    extra: 0,
  });
  const [resolvedRunId, setResolvedRunId] = useState<string | null>(null);
  const [embeddedCounts, setEmbeddedCounts] = useState<Record<ActiveSectionTab, number>>({
    mismatches: 0,
    missing: 0,
    extra: 0,
  });
  const [isRunning, setIsRunning] = useState(false);
  const [runningMessage, setRunningMessage] = useState('Validating…');
  const [reloadToken, setReloadToken] = useState(0);

  const applyResult = useCallback((
    result: ValidateResult,
    meta: ReportMeta,
    runId: string | null,
  ) => {
    const counts = result.mismatch_counts;
    const totalWrong = counts.missing_in_target + counts.extra_in_target + counts.value_mismatch;
    setStatsOverview({
      totalWrong,
      mismatchedCount: counts.value_mismatch,
      missingCount: counts.missing_in_target,
      extraCount: counts.extra_in_target,
    });
    setTabTotals({
      mismatches: counts.value_mismatch,
      missing: counts.missing_in_target,
      extra: counts.extra_in_target,
    });
    setActiveTab(pickInitialTab(counts));
    setReportMeta(meta);
    setResolvedRunId(runId);
    const cols = result.compared_columns ?? meta.comparedColumns ?? [];
    setComparedColumns(cols);
    setEmbeddedCounts({
      mismatches: result.mismatch_sample_groups.value_mismatch.length,
      missing: result.mismatch_sample_groups.missing_in_target.length,
      extra: result.mismatch_sample_groups.extra_in_target.length,
    });
    setServerPageActive(false);
    setIsRunning(false);
    setError(null);
  }, []);

  useEffect(() => {
    if (!jobId && !runIdParam && !initialResultProp) return;

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        let result: ValidateResult | null = initialResultProp ?? null;
        let meta: ReportMeta | null = result && jobId
          ? metaFromResult(result, jobId)
          : null;
        let runId: string | null = runIdParam ?? result?.run_id ?? null;

        if (result && !meta && runId) {
          meta = metaFromResult(result, jobId);
        }

        if (jobId && !result) {
          try {
            const { data: job } = await Api.getValidationJob(jobId);
            if (cancelled) return;
            if (job.status === 'completed' && job.result) {
              result = job.result;
              runId = runId ?? job.result.run_id ?? null;
              meta = metaFromResult(job.result, jobId);
            } else if (job.status === 'failed') {
              setError(job.error || 'Validation failed');
              setLoading(false);
              return;
            } else if (job.status !== 'completed') {
              const session = getActiveSession(jobId);
              setIsRunning(true);
              setRunningMessage(job.message || job.phase || 'Validation in progress…');
              setReportMeta({
                jobId,
                runId: null,
                sourceLabel: session?.sourcePath ?? null,
                targetLabel: session?.targetPath ?? null,
                uidColumn: session?.formSnapshot?.uidColumn ?? null,
                delimiter: session?.formSnapshot?.delimiter ?? null,
                isMatch: false,
                sourceRowCount: 0,
                targetRowCount: 0,
                comparedColumnCount: session?.formSnapshot?.columnMappings.length ?? 0,
                comparedColumns: [],
              });
              setLoading(false);
              return;
            }
          } catch {
          }

          if (!result) {
            try {
              const { data: history } = await Api.getValidationHistoryRun(jobId);
              if (cancelled) return;
              result = historyToResult(history);
              meta = metaFromHistory(history);
              runId = history.run_id;
            } catch {
            }
          }
        }

        if (!result && runId) {
          const { data: history } = await Api.getValidationHistoryRun(runId);
          if (cancelled) return;
          result = historyToResult(history);
          meta = metaFromHistory(history);
          if (jobId) {
            meta = { ...meta, jobId };
          }
        } else if (result && meta && runId) {
          try {
            const { data: history } = await Api.getValidationHistoryRun(runId);
            if (cancelled) return;
            const historyMeta = metaFromHistory(history);
            meta = {
              ...meta,
              sourceLabel: historyMeta.sourceLabel,
              targetLabel: historyMeta.targetLabel,
              uidColumn: historyMeta.uidColumn,
              delimiter: historyMeta.delimiter,
              sourceRowCount: meta.sourceRowCount || historyMeta.sourceRowCount,
              targetRowCount: meta.targetRowCount || historyMeta.targetRowCount,
              comparedColumnCount: meta.comparedColumnCount || historyMeta.comparedColumnCount,
              comparedColumns: meta.comparedColumns.length ? meta.comparedColumns : historyMeta.comparedColumns,
            };
          } catch {
            // Job result alone is sufficient when history is unavailable.
          }
        }

        if (!result || !meta) {
          setError('Validation report not found. The job may have expired; open from History using the run id.');
          setLoading(false);
          return;
        }

        applyResult(result, meta, runId);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load validation report');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => { cancelled = true; };
  }, [jobId, runIdParam, initialResultProp, reloadToken, applyResult]);

  useEffect(() => {
    if (!jobId || !isRunning) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const { data: job } = await Api.getValidationJob(jobId);
        if (cancelled) return;
        if (job.status === 'completed' && job.result) {
          removeActiveSession(jobId);
          dispatch(reportActions.fetchReportsRequest());
          setReloadToken((t) => t + 1);
          return;
        }
        if (job.status === 'failed') {
          removeActiveSession(jobId);
          setIsRunning(false);
          setError(job.error || 'Validation failed');
          dispatch(reportActions.fetchReportsRequest());
          return;
        }
        setRunningMessage(job.message || job.phase || 'Validation in progress…');
        timer = setTimeout(() => { void poll(); }, 2000);
      } catch {
        timer = setTimeout(() => { void poll(); }, 3000);
      }
    };

    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId, isRunning, dispatch]);

  useEffect(() => {
    if (pendingReportJobId) {
      navigate(`/validation/report/${pendingReportJobId}`);
      dispatch(validationActions.clearPendingReportJob());
    }
  }, [pendingReportJobId, navigate, dispatch]);

  const currentTabTotalRows = tabTotals[activeTab];
  const wantsServerPage = Boolean(
    resolvedRunId
    && currentTabTotalRows > 0
    && (serverPageActive || currentTabTotalRows > embeddedCounts[activeTab]),
  );

  useEffect(() => {
    if (!resolvedRunId || !wantsServerPage) {
      setServerPageActive(false);
      return;
    }

    let cancelled = false;

    const loadPage = async () => {
      try {
        const { data: page } = await Api.getValidationMismatches(resolvedRunId, {
          limit: pageSize,
          offset: 0,
          mismatch_type: TAB_TO_TYPE[activeTab],
        });
        if (cancelled) return;
        if (page.items.length > 0) {
          setServerPageActive(true);
          if (page.total > 0) {
            setTabTotals((prev) => ({
              ...prev,
              [activeTab]: page.total,
            }));
          }
        } else {
          setServerPageActive(false);
        }
      } catch {
        setServerPageActive(false);
      }
    };

    void loadPage();
    return () => { cancelled = true; };
  }, [resolvedRunId, wantsServerPage, pageSize, activeTab, comparedColumns]);

  const handleBack = () => {
    if (onBack) onBack();
    else navigate(-1);
  };

  const handleRerun = () => {
    const runId = resolvedRunId ?? reportMeta?.runId;
    if (!runId) return;
    dispatch(validationActions.runValidationFromHistoryRequest(runId));
  };

  if (!jobId && !runIdParam && !initialResultProp) {
    return (
      <div style={{ padding: '24px' }}>
        <p style={{ color: '#ba1a1a' }}>Missing job or run id in URL</p>
        <button onClick={handleBack} type="button">Back</button>
      </div>
    );
  }

  if (loading) {
    return <p style={{ padding: '24px' }}>Loading validation report…</p>;
  }

  if (isRunning && reportMeta) {
    return (
      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <SyncOutlined spin style={{ fontSize: '24px', color: '#1677ff' }} />
          <div>
            <h2 style={{ margin: 0, fontSize: '20px' }}>Validation in progress</h2>
            <p style={{ margin: '4px 0 0', color: '#64748b' }}>{runningMessage}</p>
          </div>
        </div>
        {(reportMeta.sourceLabel || reportMeta.targetLabel) && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '16px' }}>
            <FileLabel label="Source" path={reportMeta.sourceLabel} />
            <FileLabel label="Target" path={reportMeta.targetLabel} />
          </div>
        )}
        <p style={{ color: '#64748b', fontSize: '13px' }}>
          This session stays in Reports → Active until validation finishes. You will be notified when the report is ready.
        </p>
        <button onClick={handleBack} type="button" style={{ alignSelf: 'flex-start', padding: '8px 16px' }}>Back</button>
      </div>
    );
  }

  if (error || !reportMeta) {
    return (
      <div style={{ padding: '24px' }}>
        <p style={{ color: '#ba1a1a' }}>{error ?? 'Report unavailable'}</p>
        <button onClick={handleBack} type="button">Back</button>
      </div>
    );
  }

  const passWithNoMismatches = reportMeta.isMatch && statsOverview.totalWrong === 0;
  const zeroRowsValidated = reportMeta.sourceRowCount === 0 && reportMeta.targetRowCount === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', fontFamily: 'var(--font-sans)', color: '#1b1b1c' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '12px', color: '#727786', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>Validation output</span>
          <h2 style={{ fontSize: '24px', fontWeight: 700, margin: '4px 0 0 0' }}>Detailed Report</h2>
          <p style={{ fontSize: '13px', color: '#727786', margin: '4px 0 0 0' }}>
            {reportMeta.jobId ? `Job ${reportMeta.jobId}` : ''}
            {reportMeta.jobId && reportMeta.runId ? ' · ' : ''}
            {reportMeta.runId ? `Run ${reportMeta.runId}` : ''}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {(resolvedRunId ?? reportMeta.runId) && (
            <button
              type="button"
              onClick={handleRerun}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#0057c2', border: 'none', color: '#fff', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
            >
              <PlayCircleOutlined /> Run Again
            </button>
          )}
          <button onClick={handleBack} type="button" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
            <ArrowLeftOutlined /> Back
          </button>
        </div>
      </div>

      {(reportMeta.sourceLabel || reportMeta.targetLabel) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '16px' }}>
          <FileLabel label="Source" path={reportMeta.sourceLabel} />
          <FileLabel label="Target" path={reportMeta.targetLabel} />
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: '16px' }}>
        <StatCard label="Result" value={reportMeta.isMatch ? 'PASS' : 'FAIL'} color={reportMeta.isMatch ? '#16a34a' : '#ba1a1a'} />
        <StatCard label="Source Rows" value={reportMeta.sourceRowCount.toLocaleString()} />
        <StatCard label="Target Rows" value={reportMeta.targetRowCount.toLocaleString()} />
        <StatCard label="Columns Compared" value={String(reportMeta.comparedColumnCount)} />
        <StatCard label="Total Wrong Entries" value={statsOverview.totalWrong.toLocaleString()} color={statsOverview.totalWrong ? '#ba1a1a' : '#1b1b1c'} />
      </div>

      {passWithNoMismatches && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px 20px', borderRadius: '8px', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0' }}>
          <CheckCircleFilled style={{ color: '#16a34a', fontSize: '20px' }} />
          <div>
            <h5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700 }}>Validation passed</h5>
            <p style={{ margin: 0, fontSize: '13px' }}>
              No mismatches were found between source and target
              {reportMeta.sourceRowCount > 0 ? ` across ${reportMeta.sourceRowCount.toLocaleString()} rows` : ''}.
            </p>
          </div>
        </div>
      )}

      {zeroRowsValidated && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px 20px', borderRadius: '8px', backgroundColor: '#fffbeb', border: '1px solid #fde68a' }}>
          <ExclamationCircleFilled style={{ color: '#d97706', fontSize: '20px' }} />
          <div>
            <h5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700 }}>No rows were compared</h5>
            <p style={{ margin: 0, fontSize: '13px' }}>
              Check that source and target files are different objects, delimiter
              {reportMeta.delimiter ? ` (${reportMeta.delimiter})` : ''} matches the file format, and UID column
              {reportMeta.uidColumn ? ` (${reportMeta.uidColumn})` : ''} exists in both files.
            </p>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px' }}>
        <StatCard label="Mismatched" value={statsOverview.mismatchedCount.toLocaleString()} color="#fa8c16" />
        <StatCard label="Missing in Target" value={statsOverview.missingCount.toLocaleString()} color="#fa8c16" />
        <StatCard label="Extra in Target" value={statsOverview.extraCount.toLocaleString()} color="#1677ff" />
      </div>
    </div>
  );
};

const StatCard: React.FC<{ label: string; value: string; color?: string; small?: boolean }> = ({
  label, value, color = '#1b1b1c', small,
}) => (
  <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: small ? '12px' : '16px' }}>
    <p style={{ margin: 0, fontSize: small ? '10px' : '12px', color: '#727786', fontWeight: 500, textTransform: small ? 'uppercase' : undefined }}>{label}</p>
    <p style={{ margin: '4px 0 0 0', fontSize: small ? '16px' : '24px', fontWeight: 700, color }}>{value}</p>
  </div>
);

const FileLabel: React.FC<{ label: string; path: string | null }> = ({ label, path }) => (
  <div style={{ backgroundColor: '#f8fafc', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '12px 16px' }}>
    <p style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#727786', textTransform: 'uppercase' }}>{label}</p>
    <p style={{ margin: '4px 0 0 0', fontSize: '12px', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{path ?? '—'}</p>
  </div>
);
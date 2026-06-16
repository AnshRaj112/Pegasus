import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeftOutlined,
  ExclamationCircleFilled,
  CheckCircleFilled,
  SyncOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  MinusCircleFilled,
  PlusCircleFilled,
} from '@ant-design/icons';

import {
  Api,
  type MismatchSampleRow,
  type ValidateResult,
  type ValidationHistoryDetail,
} from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { reportActions } from '../../report/Report.reducer';
import { validationActions } from '../Validation.reducer';
import { getActiveSession, removeActiveSession } from '../validationSessionStorage';

type ActiveSectionTab = 'mismatches' | 'missing' | 'extra';

interface ReportRow {
  id: string;
  uid: string;
  column: string;
  expected: string;
  actual: string;
}

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

type RowDetail = {
  source_record?: Record<string, unknown> | null;
  target_record?: Record<string, unknown> | null;
};

const pickInitialTab = (counts: ValidateResult['mismatch_counts']): ActiveSectionTab => {
  if (counts.value_mismatch > 0) return 'mismatches';
  if (counts.missing_in_target > 0) return 'missing';
  if (counts.extra_in_target > 0) return 'extra';
  return 'mismatches';
};

const parseRowDetail = (raw: MismatchSampleRow['row_detail']): RowDetail | null => {
  if (!raw) return null;
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw) as RowDetail;
    } catch {
      return null;
    }
  }
  return raw as RowDetail;
};

const formatCell = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '—';
  const text = String(value);
  if (text === '__NULL__') return '—';
  return text;
};

const formatRecord = (
  record: Record<string, unknown> | null | undefined,
  column?: string | null,
): string => {
  if (!record) return '—';
  if (column && column !== '—' && record[column] !== undefined && record[column] !== null) {
    return formatCell(record[column]);
  }
  const keys = Object.keys(record).filter((k) => k !== 'uid');
  if (keys.length === 0) return '—';
  return keys.map((k) => `${k}: ${formatCell(record[k])}`).join(' · ');
};

const mapRow = (row: MismatchSampleRow, index: number, tab: ActiveSectionTab): ReportRow => {
  const detail = parseRowDetail(row.row_detail);
  const column = row.column_name?.trim() || null;

  let expected = formatCell(row.source_value);
  let actual = formatCell(row.target_value);

  if (expected === '—' && detail?.source_record) {
    expected = formatRecord(detail.source_record, column);
  }
  if (actual === '—' && detail?.target_record) {
    actual = formatRecord(detail.target_record, column);
  }

  if (tab === 'missing') {
    expected = formatRecord(detail?.source_record) !== '—'
      ? formatRecord(detail?.source_record)
      : expected;
    actual = '— (not in target)';
  } else if (tab === 'extra') {
    expected = '— (not in source)';
    actual = formatRecord(detail?.target_record) !== '—'
      ? formatRecord(detail?.target_record)
      : actual;
  }

  return {
    id: `${row.uid}-${column ?? 'row'}-${index}`,
    uid: row.uid,
    column: column ?? (tab === 'mismatches' ? '—' : 'Full record'),
    expected,
    actual,
  };
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

const fetchMismatchPage = async (
  runId: string | null,
  jobId: string | null,
  params: { limit: number; offset: number; mismatch_type: string },
) => {
  if (runId) {
    try {
      return await Api.getValidationMismatches(runId, params);
    } catch {
      // Fall back to on-disk job artifact when DB persistence is still running.
    }
  }
  if (jobId) {
    return await Api.getValidationJobMismatches(jobId, params);
  }
  throw new Error('No run or job id for mismatch pagination');
};

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
  const [uidSearchQuery, setUidSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [manualPageJump, setManualPageJump] = useState('1');
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportMeta, setReportMeta] = useState<ReportMeta | null>(null);
  const [rowsByTab, setRowsByTab] = useState<Record<ActiveSectionTab, ReportRow[]>>({
    mismatches: [],
    missing: [],
    extra: [],
  });
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
    setRowsByTab({ mismatches: [], missing: [], extra: [] });
    setCurrentPage(1);
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
            const { data: job } = await Api.getValidationJob(jobId, { summaryOnly: true });
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
            // Job may have expired from disk; fall back to history via run id.
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
        const { data: job } = await Api.getValidationJob(jobId, { summaryOnly: true });
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

  useEffect(() => {
    const tabCount = activeTab === 'mismatches'
      ? statsOverview.mismatchedCount
      : activeTab === 'missing'
        ? statsOverview.missingCount
        : statsOverview.extraCount;

    if (!reportMeta || tabCount === 0) {
      setRowsByTab((prev) => ({ ...prev, [activeTab]: [] }));
      return;
    }

    let cancelled = false;

    const loadPage = async () => {
      setPageLoading(true);
      try {
        const { data: page } = await fetchMismatchPage(
          resolvedRunId,
          reportMeta.jobId,
          {
            limit: pageSize,
            offset: (currentPage - 1) * pageSize,
            mismatch_type: TAB_TO_TYPE[activeTab],
          },
        );
        if (cancelled) return;
        setRowsByTab((prev) => ({
          ...prev,
          [activeTab]: page.items.map((row, index) => mapRow(row, index, activeTab)),
        }));
        if (page.total > 0) {
          setTabTotals((prev) => ({
            ...prev,
            [activeTab]: page.total,
          }));
        }
      } catch {
        if (!cancelled) {
          setRowsByTab((prev) => ({ ...prev, [activeTab]: [] }));
        }
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    };

    void loadPage();
    return () => { cancelled = true; };
  }, [reportMeta, resolvedRunId, activeTab, currentPage, pageSize, statsOverview]);

  useEffect(() => {
    setManualPageJump(String(currentPage));
  }, [currentPage]);

  const currentTabTotalRows = tabTotals[activeTab];
  const calculatedTotalPages = Math.max(1, Math.ceil(currentTabTotalRows / pageSize));
  const activeRows = rowsByTab[activeTab];
  const filteredItems = activeRows.filter((item) =>
    item.uid.toLowerCase().includes(uidSearchQuery.toLowerCase()),
  );

  const handlePageJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsedPage = parseInt(manualPageJump, 10);
    if (!isNaN(parsedPage) && parsedPage >= 1 && parsedPage <= calculatedTotalPages) {
      setCurrentPage(parsedPage);
    }
  };

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

      {currentTabTotalRows > 0 && (
        <>
          <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: 700, color: '#1b1b1c' }}>Filter by UID</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Enter UID to search..."
                value={uidSearchQuery}
                onChange={(e) => setUidSearchQuery(e.target.value)}
                style={{ width: '100%', height: '36px', padding: '0 12px 0 36px', borderRadius: '6px', border: '1px solid #d9d9d9', fontSize: '13px', outline: 'none' }}
              />
              <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            </div>
          </div>

          <div style={{ display: 'flex', borderBottom: '1px solid #d9d9d9', gap: '4px' }}>
            {(['mismatches', 'missing', 'extra'] as ActiveSectionTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => { setActiveTab(tab); setCurrentPage(1); }}
                style={{ padding: '10px 24px', background: 'none', border: 'none', borderBottom: activeTab === tab ? '2px solid #1677ff' : '2px solid transparent', color: activeTab === tab ? '#1677ff' : '#727786', fontWeight: 600, cursor: 'pointer', fontSize: '13px' }}
              >
                {tab === 'mismatches' ? 'Mismatches' : tab === 'missing' ? 'Missing' : 'Extra'} ({tabTotals[tab].toLocaleString()})
              </button>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px' }}>
            <StatCard label="Active Page" value={String(currentPage)} small />
            <StatCard label="Page Size" value={String(pageSize)} small />
            <StatCard label="Total Pages" value={String(calculatedTotalPages)} small />
          </div>

          {pageLoading && (
            <p style={{ margin: 0, fontSize: '13px', color: '#727786' }}>
              Loading page {currentPage} of {calculatedTotalPages}…
            </p>
          )}

          {!pageLoading && filteredItems.length === 0 && (
            <p style={{ margin: 0, fontSize: '13px', color: '#727786', padding: '8px 4px' }}>
              No {activeTab === 'mismatches' ? 'value mismatches' : activeTab === 'missing' ? 'missing records' : 'extra records'} on this page.
            </p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {filteredItems.map((item) => (
              <div key={item.id} style={{ backgroundColor: '#ffffff', border: '1px solid #fa8c16', borderRadius: '8px', padding: '16px', position: 'relative' }}>
                <span style={{ position: 'absolute', right: '16px', top: '16px', fontSize: '11px', fontWeight: 700, backgroundColor: activeTab === 'extra' ? '#e6f4ff' : '#fff7e6', color: activeTab === 'extra' ? '#1677ff' : '#fa8c16', padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase' }}>
                  {activeTab === 'mismatches' && <ExclamationCircleFilled />}
                  {activeTab === 'missing' && <MinusCircleFilled />}
                  {activeTab === 'extra' && <PlusCircleFilled />}
                  {' '}{activeTab}
                </span>
                <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Record</span>
                <h4 style={{ fontSize: '16px', fontWeight: 700, margin: '2px 0 0 0' }}>{item.uid}</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '12px', border: '1px solid #d9d9d9', borderRadius: '6px', padding: '12px', backgroundColor: '#f8fafc', marginTop: '12px' }}>
                  <div>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Column</span>
                    <p style={{ margin: '4px 0 0 0', fontSize: '13px', fontWeight: 600, color: '#ba1a1a' }}>{item.column}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Expected (Source)</span>
                    <p style={{ margin: '4px 0 0 0', fontSize: '13px', fontFamily: 'var(--font-mono)', color: '#52c41a' }}>{item.expected}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Actual (Target)</span>
                    <p style={{ margin: '4px 0 0 0', fontSize: '13px', fontFamily: 'var(--font-mono)', color: '#ba1a1a' }}>{item.actual}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#ffffff' }}>
            <div style={{ fontSize: '13px', color: '#414755' }}>
              Showing <strong>{filteredItems.length ? (currentPage - 1) * pageSize + 1 : 0}</strong> to <strong>{(currentPage - 1) * pageSize + filteredItems.length}</strong> of <strong>{currentTabTotalRows.toLocaleString()}</strong> rows
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  type="button"
                  disabled={currentPage === 1 || pageLoading}
                  onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                  style={{ height: '32px', padding: '0 12px', border: '1px solid #d9d9d9', borderRadius: '6px', backgroundColor: '#ffffff', cursor: currentPage === 1 || pageLoading ? 'not-allowed' : 'pointer', opacity: currentPage === 1 || pageLoading ? 0.5 : 1, fontSize: '12px', fontWeight: 500 }}
                >
                  Previous
                </button>
                <span style={{ fontSize: '13px', padding: '0 8px', color: '#414755', backgroundColor: '#f5f5f5', height: '32px', display: 'inline-flex', alignItems: 'center', borderRadius: '6px', border: '1px solid #d9d9d9' }}>
                  Page {currentPage} of {calculatedTotalPages}
                </span>
                <button
                  type="button"
                  disabled={currentPage === calculatedTotalPages || pageLoading}
                  onClick={() => setCurrentPage((prev) => Math.min(calculatedTotalPages, prev + 1))}
                  style={{ height: '32px', padding: '0 12px', border: '1px solid #d9d9d9', borderRadius: '6px', backgroundColor: '#ffffff', cursor: currentPage === calculatedTotalPages || pageLoading ? 'not-allowed' : 'pointer', opacity: currentPage === calculatedTotalPages || pageLoading ? 0.5 : 1, fontSize: '12px', fontWeight: 500 }}
                >
                  Next
                </button>
              </div>
              <form onSubmit={handlePageJumpSubmit} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', letterSpacing: '0.05em' }}>GO TO</span>
                <input
                  type="text"
                  value={manualPageJump}
                  onChange={(e) => setManualPageJump(e.target.value)}
                  style={{ width: '48px', height: '32px', borderRadius: '6px', border: '1px solid #d9d9d9', outline: 'none', textAlign: 'center', fontSize: '13px', fontWeight: 600 }}
                />
              </form>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', letterSpacing: '0.05em' }}>ROWS</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(parseInt(e.target.value, 10)); setCurrentPage(1); }}
                  style={{ height: '32px', padding: '0 8px', borderRadius: '6px', border: '1px solid #d9d9d9', background: '#ffffff', outline: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: 600 }}
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>
          </div>
        </>
      )}
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

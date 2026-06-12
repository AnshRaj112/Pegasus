import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeftOutlined,
  SearchOutlined,
  ExclamationCircleFilled,
  MinusCircleFilled,
  PlusCircleFilled,
  CheckCircleFilled,
} from '@ant-design/icons';

import {
  Api,
  type MismatchSampleRow,
  type ValidateResult,
  type ValidationHistoryDetail,
} from '../../../shared/api/Api';

type ActiveSectionTab = 'mismatches' | 'missing' | 'extra';

interface ReportRow {
  id: string;
  uid: string;
  column: string;
  expected: string;
  actual: string;
  srcFields: string;
  tgtFields: string;
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
}

interface ValidationReportProps {
  onBack?: () => void;
  jobId?: string;
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

  const srcCount = detail?.source_record && typeof detail.source_record === 'object'
    ? Object.keys(detail.source_record).filter((k) => k !== 'uid').length
    : 0;
  const tgtCount = detail?.target_record && typeof detail.target_record === 'object'
    ? Object.keys(detail.target_record).filter((k) => k !== 'uid').length
    : 0;

  return {
    id: `${row.uid}-${column ?? 'row'}-${index}`,
    uid: row.uid,
    column: column ?? (tab === 'mismatches' ? '—' : 'Full record'),
    expected,
    actual,
    srcFields: srcCount ? `${srcCount} fields` : '0 fields',
    tgtFields: tgtCount ? `${tgtCount} fields` : '0 fields',
  };
};

const rowsFromSamples = (samples: MismatchSampleRow[], tab: ActiveSectionTab): ReportRow[] =>
  samples.map((row, index) => mapRow(row, index, tab));

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
});

export const ValidationReport: React.FC<ValidationReportProps> = ({ onBack, jobId: jobIdProp }) => {
  const navigate = useNavigate();
  const { jobId: routeJobId, runId: routeRunId } = useParams<{ jobId?: string; runId?: string }>();
  const jobId = jobIdProp ?? routeJobId ?? null;
  const runIdParam = routeRunId ?? null;

  const [activeTab, setActiveTab] = useState<ActiveSectionTab>('mismatches');
  const [uidSearchQuery, setUidSearchQuery] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [manualPageJump, setManualPageJump] = useState<string>('1');
  const [loading, setLoading] = useState(true);
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
  const [useHistoryPagination, setUseHistoryPagination] = useState(false);

  useEffect(() => {
    if (!jobId && !runIdParam) return;

    let cancelled = false;

    const embeddedSamplesEmpty = (result: ValidateResult) =>
      result.mismatch_sample_groups.missing_in_target.length === 0
      && result.mismatch_sample_groups.extra_in_target.length === 0
      && result.mismatch_sample_groups.value_mismatch.length === 0;

    const applyResult = (
      result: ValidateResult,
      meta: ReportMeta,
      runId: string | null,
      preferHistoryPagination: boolean,
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
      setReportMeta(meta);
      setResolvedRunId(runId);
      setUseHistoryPagination(preferHistoryPagination);
      setRowsByTab({
        mismatches: rowsFromSamples(result.mismatch_sample_groups.value_mismatch, 'mismatches'),
        missing: rowsFromSamples(result.mismatch_sample_groups.missing_in_target, 'missing'),
        extra: rowsFromSamples(result.mismatch_sample_groups.extra_in_target, 'extra'),
      });
    };

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        let result: ValidateResult | null = null;
        let meta: ReportMeta | null = null;
        let runId: string | null = runIdParam;

        if (jobId) {
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
              setError(job.error || 'Validation is still running');
              setLoading(false);
              return;
            }
          } catch {
            // Job may have expired from disk; fall back to history via run id.
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

        applyResult(result, meta, runId, Boolean(runId) && embeddedSamplesEmpty(result));
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
  }, [jobId, runIdParam]);

  useEffect(() => {
    if (!resolvedRunId || !useHistoryPagination) return;

    let cancelled = false;

    const loadPage = async () => {
      try {
        const { data: page } = await Api.getValidationMismatches(resolvedRunId, {
          limit: pageSize,
          offset: (currentPage - 1) * pageSize,
          mismatch_type: TAB_TO_TYPE[activeTab],
        });
        if (cancelled) return;
        if (page.items.length === 0 && page.total === 0) {
          return;
        }
        setRowsByTab((prev) => ({
          ...prev,
          [activeTab]: page.items.map((row, index) => mapRow(row, index, activeTab)),
        }));
        setTabTotals((prev) => ({
          ...prev,
          [activeTab]: page.total,
        }));
      } catch {
        // Keep embedded sample rows when history pagination is unavailable.
      }
    };

    void loadPage();
    return () => { cancelled = true; };
  }, [resolvedRunId, useHistoryPagination, currentPage, pageSize, activeTab]);

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

  if (!jobId && !runIdParam) {
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
        <button onClick={handleBack} type="button" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
          <ArrowLeftOutlined /> Back
        </button>
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
            {tab === 'mismatches' ? 'Mismatches' : tab === 'missing' ? 'Missing' : 'Extra'} ({tabTotals[tab]})
          </button>
        ))}
      </div>

      {filteredItems.length === 0 && (
        <p style={{ margin: 0, fontSize: '13px', color: '#727786', padding: '8px 4px' }}>
          No {activeTab === 'mismatches' ? 'value mismatches' : activeTab === 'missing' ? 'missing records' : 'extra records'} to display.
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px' }}>
          <StatCard label="Active Page" value={String(currentPage)} small />
          <StatCard label="Page Size" value={String(pageSize)} small />
          <StatCard label="Total Pages" value={String(calculatedTotalPages)} small />
        </div>

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

        {currentTabTotalRows > 0 && (
          <div style={{ border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#ffffff', marginTop: '12px' }}>
            <div style={{ fontSize: '13px', color: '#414755' }}>
              Showing <strong>{filteredItems.length ? (currentPage - 1) * pageSize + 1 : 0}</strong> to <strong>{(currentPage - 1) * pageSize + filteredItems.length}</strong> of <strong>{currentTabTotalRows}</strong> rows
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                  style={{ height: '32px', padding: '0 12px', border: '1px solid #d9d9d9', borderRadius: '6px', backgroundColor: '#ffffff', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', opacity: currentPage === 1 ? 0.5 : 1, fontSize: '12px', fontWeight: 500 }}
                >
                  Previous
                </button>
                <span style={{ fontSize: '13px', padding: '0 8px', color: '#414755', backgroundColor: '#f5f5f5', height: '32px', display: 'inline-flex', alignItems: 'center', borderRadius: '6px', border: '1px solid #d9d9d9' }}>
                  Page {currentPage} of {calculatedTotalPages}
                </span>
                <button
                  type="button"
                  disabled={currentPage === calculatedTotalPages}
                  onClick={() => setCurrentPage((prev) => Math.min(calculatedTotalPages, prev + 1))}
                  style={{ height: '32px', padding: '0 12px', border: '1px solid #d9d9d9', borderRadius: '6px', backgroundColor: '#ffffff', cursor: currentPage === calculatedTotalPages ? 'not-allowed' : 'pointer', opacity: currentPage === calculatedTotalPages ? 0.5 : 1, fontSize: '12px', fontWeight: 500 }}
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
        )}
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

import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeftOutlined,
  SearchOutlined,
  ExclamationCircleFilled,
  MinusCircleFilled,
  PlusCircleFilled
} from '@ant-design/icons';

import { Api, type MismatchSampleRow } from '../../../shared/api/Api';

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

interface ValidationReportProps {
  onBack?: () => void;
  jobId?: string;
}

const TAB_TO_TYPE: Record<ActiveSectionTab, string> = {
  mismatches: 'value_mismatch',
  missing: 'missing_in_target',
  extra: 'extra_in_target',
};

const mapRow = (row: MismatchSampleRow, index: number): ReportRow => {
  const detail = typeof row.row_detail === 'string'
    ? null
    : row.row_detail;
  const srcCount = detail?.source_record && typeof detail.source_record === 'object'
    ? Object.keys(detail.source_record).length
    : 0;
  const tgtCount = detail?.target_record && typeof detail.target_record === 'object'
    ? Object.keys(detail.target_record).length
    : 0;

  return {
    id: `${row.uid}-${row.column_name ?? 'row'}-${index}`,
    uid: row.uid,
    column: row.column_name ?? '[ALL_COLUMNS]',
    expected: row.source_value ?? '[Not found in source]',
    actual: row.target_value ?? '[Null / Record missing from source pool]',
    srcFields: srcCount ? `${srcCount} fields` : '0 fields',
    tgtFields: tgtCount ? `${tgtCount} fields` : '0 fields',
  };
};

export const ValidationReport: React.FC<ValidationReportProps> = ({ onBack, jobId: jobIdProp }) => {
  const navigate = useNavigate();
  const { jobId: routeJobId } = useParams<{ jobId: string }>();
  const jobId = jobIdProp ?? routeJobId;
  const [activeTab, setActiveTab] = useState<ActiveSectionTab>('mismatches');
  const [uidSearchQuery, setUidSearchQuery] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [manualPageJump, setManualPageJump] = useState<string>('1');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
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

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const { data: job } = await Api.getValidationJob(jobId);
        if (cancelled) return;

        if (job.status !== 'completed' || !job.result) {
          setError(job.error || 'Validation is still running or has no result yet');
          setLoading(false);
          return;
        }

        const counts = job.result.mismatch_counts;
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

        const resolvedRunId = job.result.run_id;
        setRunId(resolvedRunId);

        if (resolvedRunId) {
          const page = await Api.getValidationMismatches(resolvedRunId, {
            limit: pageSize,
            offset: (currentPage - 1) * pageSize,
            mismatch_type: TAB_TO_TYPE[activeTab],
          });
          if (cancelled) return;
          setRowsByTab((prev) => ({
            ...prev,
            [activeTab]: page.data.items.map(mapRow),
          }));
          setTabTotals((prev) => ({
            ...prev,
            [activeTab]: page.data.total,
          }));
        } else {
          const groups = job.result.mismatch_sample_groups;
          setRowsByTab({
            mismatches: groups.value_mismatch.map(mapRow),
            missing: groups.missing_in_target.map(mapRow),
            extra: groups.extra_in_target.map(mapRow),
          });
        }
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
  }, [jobId, currentPage, pageSize, activeTab]);

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

  if (!jobId) {
    return (
      <div style={{ padding: '24px' }}>
        <p style={{ color: '#ba1a1a' }}>Missing job id</p>
        <button onClick={handleBack} type="button">Back</button>
      </div>
    );
  }

  if (loading) {
    return <p style={{ padding: '24px' }}>Loading validation report…</p>;
  }

  if (error) {
    return (
      <div style={{ padding: '24px' }}>
        <p style={{ color: '#ba1a1a' }}>{error}</p>
        <button onClick={handleBack} type="button">Back</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', fontFamily: 'var(--font-sans)', color: '#1b1b1c' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '12px', color: '#727786', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>Validation output</span>
          <h2 style={{ fontSize: '24px', fontWeight: 700, margin: '4px 0 0 0' }}>Detailed Report</h2>
          <p style={{ fontSize: '13px', color: '#727786', margin: '4px 0 0 0' }}>
            Job {jobId}{runId ? ` · Run ${runId}` : ''}
          </p>
        </div>
        <button onClick={handleBack} type="button" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
          <ArrowLeftOutlined /> Back
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '16px' }}>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px' }}>
          <p style={{ margin: 0, fontSize: '12px', color: '#727786', fontWeight: 500 }}>Total Wrong Entries</p>
          <p style={{ margin: '4px 0 0 0', fontSize: '24px', fontWeight: 700 }}>{statsOverview.totalWrong.toLocaleString()}</p>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px' }}>
          <p style={{ margin: 0, fontSize: '12px', color: '#727786', fontWeight: 500 }}>Mismatched</p>
          <p style={{ margin: '4px 0 0 0', fontSize: '24px', fontWeight: 700, color: '#fa8c16' }}>{statsOverview.mismatchedCount.toLocaleString()}</p>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px' }}>
          <p style={{ margin: 0, fontSize: '12px', color: '#727786', fontWeight: 500 }}>Missing in Target</p>
          <p style={{ margin: '4px 0 0 0', fontSize: '24px', fontWeight: 700, color: '#fa8c16' }}>{statsOverview.missingCount.toLocaleString()}</p>
        </div>
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px' }}>
          <p style={{ margin: 0, fontSize: '12px', color: '#727786', fontWeight: 500 }}>Extra in Target</p>
          <p style={{ margin: '4px 0 0 0', fontSize: '24px', fontWeight: 700, color: '#1677ff' }}>{statsOverview.extraCount.toLocaleString()}</p>
        </div>
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px' }}>
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '12px' }}>
            <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Active Page</span>
            <p style={{ margin: '4px 0 0 0', fontSize: '16px', fontWeight: 700 }}>{currentPage}</p>
          </div>
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '12px' }}>
            <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Page Size</span>
            <p style={{ margin: '4px 0 0 0', fontSize: '16px', fontWeight: 700 }}>{pageSize}</p>
          </div>
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '12px' }}>
            <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Total Pages</span>
            <p style={{ margin: '4px 0 0 0', fontSize: '16px', fontWeight: 700 }}>{calculatedTotalPages}</p>
          </div>
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
      </div>
    </div>
  );
};

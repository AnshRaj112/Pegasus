import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { 
  ArrowLeftOutlined,
  SearchOutlined,
  ExclamationCircleFilled,
  MinusCircleFilled,
  PlusCircleFilled
} from '@ant-design/icons';

type ActiveSectionTab = 'mismatches' | 'missing' | 'extra';

interface ValidationReportProps {
  onBack: () => void;
}

export const ValidationReport: React.FC<ValidationReportProps> = ({ onBack }) => {
  // Navigation & Sizing Hooks mapped to layout mock specifications
  const [activeTab, setActiveTab] = useState<ActiveSectionTab>('mismatches');
  const [uidSearchQuery, setUidSearchQuery] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [manualPageJump, setManualPageJump] = useState<string>('1');

  const { jobId } = useParams<{ jobId: string }>();

  const reportSummary = {
    jobId: jobId || 'JOB-2026-VAL-99X', // It uses the real URL ID, or falls back to our default if empty
    timestamp: '2026-06-10 15:30',
    matchStatus: 'Failed',
    sourceRows: 12400000,
    targetRows: 12405221,
    totalMismatches: 8000,
    executionTime: '4.23s'
  };

  // Unified Metric Dataset Values
  const statsOverview = {
    totalWrong: 8000,
    mismatchedCount: 2000,
    missingCount: 1000,
    extraCount: 5000
  };

  // Structured Item Discrepancy Array Items
  const demoDataPayloads = {
    mismatches: [
      { id: '1', uid: 'UID 1986', column: 'amount_gross', expected: '1240.50', actual: '1240.00', srcFields: '1 fields', tgtFields: '1 fields' },
      { id: '2', uid: 'UID 2044', column: 'customer_email', expected: 'j.doe@enterprise.com', actual: 'J.DOE@ENTERPRISE.COM', srcFields: '1 fields', tgtFields: '1 fields' },
      { id: '3', uid: 'UID 2891', column: 'is_active', expected: 'true', actual: 'false', srcFields: '1 fields', tgtFields: '1 fields' }
    ],
    missing: [
      { id: '1', uid: 'UID 3011', column: '[ALL_COLUMNS]', expected: 'Row Data Signature present', actual: '[Null / Record missing from source pool]', srcFields: '48 fields', tgtFields: '0 fields' },
      { id: '2', uid: 'UID 3144', column: '[ALL_COLUMNS]', expected: 'Row Data Signature present', actual: '[Null / Record missing from source pool]', srcFields: '48 fields', tgtFields: '0 fields' }
    ],
    extra: [
      { id: '1', uid: 'UID 8944', column: '[SCHEMA_MISMATCH]', expected: '[Not found in source]', actual: 'Appended system orphan payload tracking', srcFields: '0 fields', tgtFields: '52 fields' },
      { id: '2', uid: 'UID 9022', column: '[SCHEMA_MISMATCH]', expected: '[Not found in source]', actual: 'Appended system orphan payload tracking', srcFields: '0 fields', tgtFields: '52 fields' }
    ]
  };

  const getActiveArray = () => {
    if (activeTab === 'mismatches') return demoDataPayloads.mismatches;
    if (activeTab === 'missing') return demoDataPayloads.missing;
    return demoDataPayloads.extra;
  };

  const currentTabTotalRows = 
    activeTab === 'mismatches' ? statsOverview.mismatchedCount :
    activeTab === 'missing' ? statsOverview.missingCount : statsOverview.extraCount;

  const calculatedTotalPages = Math.ceil(currentTabTotalRows / pageSize);

  const filteredItems = getActiveArray().filter(item => 
    item.uid.toLowerCase().includes(uidSearchQuery.toLowerCase())
  );

  const handlePageJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsedPage = parseInt(manualPageJump);
    if (!isNaN(parsedPage) && parsedPage >= 1 && parsedPage <= calculatedTotalPages) {
      setCurrentPage(parsedPage);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', fontFamily: 'var(--font-sans)', color: '#1b1b1c' }}>
      
      {/* Structural Inner module shell title header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '12px', color: '#727786', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>Validation output</span>
          <h2 style={{ fontSize: '24px', fontWeight: 700, margin: '4px 0 0 0' }}>Detailed Report</h2>
          <p style={{ fontSize: '13px', color: '#727786', margin: '4px 0 0 0' }}>Review mismatched, missing, and extra records in separate sections with unified cards and page-by-page navigation.</p>
        </div>
        <button onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 16px', backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
          <ArrowLeftOutlined /> Back
        </button>
      </div>

      {/* 4 Block Metric Indicators Row */}
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

      {/* Search Filter by UID Header Card wrapper parameters */}
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

      {/* Primary Section Selection Tab Bar Component Row Layout Strings */}
      <div style={{ display: 'flex', borderBottom: '1px solid #d9d9d9', gap: '4px' }}>
        <button 
          onClick={() => { setActiveTab('mismatches'); setCurrentPage(1); }}
          style={{ padding: '10px 24px', background: 'none', border: 'none', borderBottom: activeTab === 'mismatches' ? '2px solid #1677ff' : '2px solid transparent', color: activeTab === 'mismatches' ? '#1677ff' : '#727786', fontWeight: 600, cursor: 'pointer', fontSize: '13px' }}
        >
          Mismatches ({statsOverview.mismatchedCount})
        </button>
        <button 
          onClick={() => { setActiveTab('missing'); setCurrentPage(1); }}
          style={{ padding: '10px 24px', background: 'none', border: 'none', borderBottom: activeTab === 'missing' ? '2px solid #1677ff' : '2px solid transparent', color: activeTab === 'missing' ? '#1677ff' : '#727786', fontWeight: 600, cursor: 'pointer', fontSize: '13px' }}
        >
          Missing ({statsOverview.missingCount})
        </button>
        <button 
          onClick={() => { setActiveTab('extra'); setCurrentPage(1); }}
          style={{ padding: '10px 24px', background: 'none', border: 'none', borderBottom: activeTab === 'extra' ? '2px solid #1677ff' : '2px solid transparent', color: activeTab === 'extra' ? '#1677ff' : '#727786', fontWeight: 600, cursor: 'pointer', fontSize: '13px' }}
        >
          Extra ({statsOverview.extraCount})
        </button>
      </div>

      {/* Active viewport content panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div>
          <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#727786', fontWeight: 700, letterSpacing: '0.05em' }}>Section</span>
          <h3 style={{ fontSize: '20px', fontWeight: 700, margin: '2px 0 0 0', textTransform: 'capitalize' }}>{activeTab} values</h3>
          <p style={{ fontSize: '13px', color: '#414755', margin: '4px 0 0 0' }}>
            {activeTab === 'mismatches' && 'Records where the same row exists in both files but one or more values differ.'}
            {activeTab === 'missing' && 'Records matching initial configurations detected only within the source baseline repository.'}
            {activeTab === 'extra' && 'Orphan column targets appended exclusively onto output systems parameters.'}
          </p>
        </div>

        {/* Mini Page Properties Specs Row indicators */}
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

        {/* Dynamic List Render Loop Frame blocks */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {filteredItems.map(item => (
            <div key={item.id} style={{ backgroundColor: '#ffffff', border: '1px solid #fa8c16', borderRadius: '8px', padding: '16px', position: 'relative' }}>
              <span style={{ position: 'absolute', right: '16px', top: '16px', fontSize: '11px', fontWeight: 700, backgroundColor: activeTab === 'extra' ? '#e6f4ff' : '#fff7e6', color: activeTab === 'extra' ? '#1677ff' : '#fa8c16', padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase' }}>
                {activeTab === 'mismatches' && <ExclamationCircleFilled />}
                {activeTab === 'missing' && <MinusCircleFilled />}
                {activeTab === 'extra' && <PlusCircleFilled />}
                {' '}{activeTab}
              </span>
              
              <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#727786', fontWeight: 700 }}>Record</span>
              <h4 style={{ fontSize: '16px', fontWeight: 700, margin: '2px 0 0 0' }}>{item.uid}</h4>
              <p style={{ fontSize: '12px', color: '#414755', margin: '4px 0 16px 0' }}>Values differ between source and target for at least one shared column.</p>

              {/* Internal data sub-table structures layout */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '12px', border: '1px solid #d9d9d9', borderRadius: '6px', padding: '12px', backgroundColor: '#f8fafc' }}>
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

              {/* Meta sub-compartments structural blocks matching mockup profiles */}
              <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                <div style={{ flex: 1, backgroundColor: '#f6ffed', border: '1px solid #bbf7d0', borderRadius: '4px', padding: '8px 12px', display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#15803d', fontWeight: 600 }}>Source record</span>
                  <span style={{ color: '#166534' }}>{item.srcFields}</span>
                </div>
                <div style={{ flex: 1, backgroundColor: '#fff1f0', border: '1px solid #ffa39e', borderRadius: '4px', padding: '8px 12px', display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#b71c1c', fontWeight: 600 }}>Target record</span>
                  <span style={{ color: '#7f1d1d' }}>{item.tgtFields}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Pagination Action Footer Controls Layout Block matching Image Reference Specifications */}
        <div style={{ border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#ffffff', marginTop: '12px' }}>
          <div style={{ fontSize: '13px', color: '#414755' }}>
            Showing <strong>1</strong> to <strong>{filteredItems.length}</strong> of <strong>{currentTabTotalRows}</strong> rows
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button 
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                style={{ height: '32px', padding: '0 12px', border: '1px solid #d9d9d9', borderRadius: '6px', backgroundColor: '#ffffff', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', opacity: currentPage === 1 ? 0.5 : 1, fontSize: '12px', fontWeight: 500 }}
              >
                Previous
              </button>
              <span style={{ fontSize: '13px', padding: '0 8px', color: '#414755', backgroundColor: '#f5f5f5', height: '32px', display: 'inline-flex', alignItems: 'center', borderRadius: '6px', border: '1px solid #d9d9d9' }}>
                Page {currentPage} of {calculatedTotalPages}
              </span>
              <button 
                disabled={currentPage === calculatedTotalPages}
                onClick={() => setCurrentPage(prev => Math.min(calculatedTotalPages, prev + 1))}
                style={{ height: '32px', padding: '0 12px', border: '1px solid #d9d9d9', borderRadius: '6px', backgroundColor: '#ffffff', cursor: currentPage === calculatedTotalPages ? 'not-allowed' : 'pointer', opacity: currentPage === calculatedTotalPages ? 0.5 : 1, fontSize: '12px', fontWeight: 500 }}
              >
                Next
              </button>
            </div>

            {/* Manual Jump Submit Form Control */}
            <form onSubmit={handlePageJumpSubmit} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', letterSpacing: '0.05em' }}>GO TO</span>
              <input 
                type="text"
                value={manualPageJump}
                onChange={(e) => setManualPageJump(e.target.value)}
                style={{ width: '48px', height: '32px',borderRadius: '6px', border: '1px solid #d9d9d9', outline: 'none', textAlign: 'center', fontSize: '13px', fontWeight: 600 }}
              />
            </form>

            {/* Rows Per-Page Dropdown Selector Customizer */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', letterSpacing: '0.05em' }}>ROWS</span>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(parseInt(e.target.value)); setCurrentPage(1); }}
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
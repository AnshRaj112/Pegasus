import React, { useRef, useState } from 'react';
import { DownloadOutlined, RightOutlined, DatabaseOutlined, LeftOutlined } from '@ant-design/icons';

// ⚡ DEMO DATA IMPLEMENTING THE SPECIFIC STATUSES
type RowStatus = 'match' | 'mismatch' | 'extra_source' | 'missing_target';

const DEMO_COLUMNS = [
  'transaction_id', 
  'amount_usd', 
  'vendor_name', 
  'status', 
  'region', 
  'currency', 
  'account_tier', 
  't_stamp'
];

const DEMO_ROWS: { id: string; status: RowStatus; source: string[]; target: string[]; mismatchIndices: number[] }[] = [
  { id: '1', status: 'match', 
    source: ['TX_001', '1200.50', 'Cloudflare', 'SUCCESS', 'US-EAST', 'USD', 'ENTERPRISE', '2023-11-20'], 
    target: ['TX_001', '1200.50', 'Cloudflare', 'SUCCESS', 'US-EAST', 'USD', 'ENTERPRISE', '2023-11-20'], 
    mismatchIndices: [] },
  { id: '2', status: 'match', 
    source: ['TX_002', '850.00', 'AWS', 'SUCCESS', 'US-WEST', 'USD', 'PRO', '2023-11-20'], 
    target: ['TX_002', '850.00', 'AWS', 'SUCCESS', 'US-WEST', 'USD', 'PRO', '2023-11-20'], 
    mismatchIndices: [] },
  { id: '3', status: 'match', 
    source: ['TX_003', '15.00', 'Stripe', 'PENDING', 'EU-CENTRAL', 'EUR', 'BASIC', '2023-11-20'], 
    target: ['TX_003', '15.00', 'Stripe', 'PENDING', 'EU-CENTRAL', 'EUR', 'BASIC', '2023-11-20'], 
    mismatchIndices: [] },
  
  // ⚡ Mismatches (Now with multiple mismatched columns: Vendor and Region)
  { id: '4', status: 'mismatch', 
    source: ['TX_004', '99.00', 'Sybase', 'SUCCESS', 'US-EAST', 'USD', 'PRO', '2023-11-21'], 
    target: ['TX_004', '99.00', 'Oracle', 'SUCCESS', 'US-WEST', 'USD', 'PRO', '2023-11-21'], 
    mismatchIndices: [2, 4] },
  { id: '5', status: 'mismatch', 
    source: ['TX_005', '450.00', 'GCP', 'FAILED', 'AP-SOUTH', 'INR', 'ENTERPRISE', '2023-11-21'], 
    target: ['TX_005', '400.00', 'GCP', 'FAILED', 'AP-SOUTH', 'INR', 'ENTERPRISE', '2023-11-21'], 
    mismatchIndices: [1] },

  // ⚡ Extra Rows in Source (Missing in Target)
  { id: '6', status: 'extra_source', 
    source: ['TX_006', '120.00', 'Azure', 'SUCCESS', 'EU-WEST', 'GBP', 'PRO', '2023-11-22'], 
    target: ['—', '—', '—', '—', '—', '—', '—', '—'], 
    mismatchIndices: [] },
  { id: '7', status: 'extra_source', 
    source: ['TX_007', '55.00', 'Vercel', 'SUCCESS', 'US-EAST', 'USD', 'BASIC', '2023-11-22'], 
    target: ['—', '—', '—', '—', '—', '—', '—', '—'], 
    mismatchIndices: [] },

  // ⚡ Missing in Source (Extra in Target)
  { id: '8', status: 'missing_target', 
    source: ['—', '—', '—', '—', '—', '—', '—', '—'], 
    target: ['TX_008', '890.00', 'Databricks', 'SUCCESS', 'US-WEST', 'USD', 'ENTERPRISE', '2023-11-23'], 
    mismatchIndices: [] },

  { id: '9', status: 'match', 
    source: ['TX_009', '75.00', 'DigitalOcean', 'SUCCESS', 'AP-EAST', 'SGD', 'PRO', '2023-11-23'], 
    target: ['TX_009', '75.00', 'DigitalOcean', 'SUCCESS', 'AP-EAST', 'SGD', 'PRO', '2023-11-23'], 
    mismatchIndices: [] },
  { id: '10', status: 'match', 
    source: ['TX_010', '150.00', 'MongoDB', 'PENDING', 'US-EAST', 'USD', 'ENTERPRISE', '2023-11-24'], 
    target: ['TX_010', '150.00', 'MongoDB', 'PENDING', 'US-EAST', 'USD', 'ENTERPRISE', '2023-11-24'], 
    mismatchIndices: [] },
];

export const SnippetComparison: React.FC = () => {
  const MAPPING_NAME = "DEMO_MAPPING_2026";
  const RUN_ID = "RUN_882910_A";

  const [itemsPerPage, setItemsPerPage] = useState(10);
  
  // Ref hooks to sync the scrollbar between the two tables
  const sourceRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef<HTMLDivElement>(null);

  const handleSourceScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (targetRef.current) {
      targetRef.current.scrollTop = e.currentTarget.scrollTop;
      targetRef.current.scrollLeft = e.currentTarget.scrollLeft;
    }
  };

  const handleTargetScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (sourceRef.current) {
      sourceRef.current.scrollTop = e.currentTarget.scrollTop;
      sourceRef.current.scrollLeft = e.currentTarget.scrollLeft;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      
      {/* Header & Breadcrumbs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '13px' }}>
          <span style={{ cursor: 'pointer' }}>Reports</span> <RightOutlined style={{ fontSize: '10px' }} />
          <span style={{ backgroundColor: '#f0eded', padding: '2px 6px', borderRadius: '4px', fontFamily: 'var(--font-mono)' }}>{MAPPING_NAME}</span> <RightOutlined style={{ fontSize: '10px' }} />
          <span style={{ backgroundColor: '#f0eded', padding: '2px 6px', borderRadius: '4px', fontFamily: 'var(--font-mono)' }}>{RUN_ID}</span> <RightOutlined style={{ fontSize: '10px' }} />
          <span style={{ color: '#1b1b1c', fontWeight: 600 }}>Snippet</span>
        </div>

        {/* ⚡ Only Download Button kept */}
        <button style={{ backgroundColor: '#1e293b', border: 'none', color: '#fff', padding: '8px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer' }}>
          <DownloadOutlined /> Download Snippet
        </button>
      </div>

      {/* Side-by-Side Tables Container */}
      <div style={{ display: 'flex', gap: '24px', flex: 1, minHeight: '400px', overflow: 'hidden' }}>
        
        {/* SOURCE TABLE */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', minWidth: 0 }}>
          <div style={{ backgroundColor: '#1e293b', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#fff' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Source &gt; db_prod_core</span>
          </div>
          <div ref={sourceRef} onScroll={handleSourceScroll} style={{ overflow: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', whiteSpace: 'nowrap' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', zIndex: 10 }}>
                <tr>
                  {DEMO_COLUMNS.map(col => (
                    <th key={col} style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#414755' }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {DEMO_ROWS.map((row) => (
                  <tr key={`src-${row.id}`} style={{ 
                    // ⚡ ORANGE BG for Missing/Extra, normal otherwise
                    backgroundColor: row.status === 'extra_source' || row.status === 'missing_target' ? '#fff7ed' : '#fff',
                    borderBottom: '1px solid #f1f5f9'
                  }}>
                    {row.source.map((cell, cIdx) => {
                      const isMismatchCell = row.status === 'mismatch' && row.mismatchIndices.includes(cIdx);
                      return (
                        <td key={cIdx} style={{ 
                          padding: '12px 16px', fontSize: '13px', fontFamily: 'var(--font-mono)',
                          // ⚡ RED BG for Mismatch cell. GREEN text for Match. ORANGE text for extra/missing.
                          backgroundColor: isMismatchCell ? '#fee2e2' : 'transparent',
                          color: isMismatchCell ? '#991b1b' : (row.status === 'match' ? '#166534' : (row.status === 'extra_source' || row.status === 'missing_target' ? '#c2410c' : '#1b1b1c')),
                          fontWeight: isMismatchCell ? 600 : 400
                        }}>
                          {cell}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* TARGET TABLE */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', minWidth: 0 }}>
          <div style={{ backgroundColor: '#e2e8f0', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '8px', color: '#1b1b1c' }}>
            <DatabaseOutlined /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Target &gt; dwh_snowflake_core</span>
          </div>
          <div ref={targetRef} onScroll={handleTargetScroll} style={{ overflow: 'auto', flex: 1 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', whiteSpace: 'nowrap' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', zIndex: 10 }}>
                <tr>
                  {DEMO_COLUMNS.map(col => (
                    <th key={col} style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#414755' }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {DEMO_ROWS.map((row) => (
                  <tr key={`tgt-${row.id}`} style={{ 
                    // ⚡ ORANGE BG for Missing/Extra
                    backgroundColor: row.status === 'extra_source' || row.status === 'missing_target' ? '#fff7ed' : '#fff',
                    borderBottom: '1px solid #f1f5f9'
                  }}>
                    {row.target.map((cell, cIdx) => {
                      const isMismatchCell = row.status === 'mismatch' && row.mismatchIndices.includes(cIdx);
                      return (
                        <td key={cIdx} style={{ 
                          padding: '12px 16px', fontSize: '13px', fontFamily: 'var(--font-mono)',
                          // ⚡ RED BG for Mismatch cell. GREEN text for Match. ORANGE text for extra/missing.
                          backgroundColor: isMismatchCell ? '#fee2e2' : 'transparent',
                          color: isMismatchCell ? '#991b1b' : (row.status === 'match' ? '#166534' : (row.status === 'extra_source' || row.status === 'missing_target' ? '#c2410c' : '#1b1b1c')),
                          fontWeight: isMismatchCell ? 600 : 400
                        }}>
                          {cell}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Footer / Pagination */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 0', borderTop: '1px solid #e2e8f0', marginTop: '16px' }}>
        <span style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic' }}>Note: Download snippet to get more information on this Test.</span>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#64748b' }}>
            Rows per page: 
            <select value={itemsPerPage} onChange={(e) => setItemsPerPage(Number(e.target.value))} style={{ border: 'none', fontWeight: 600, outline: 'none', backgroundColor: 'transparent' }}>
              <option value={10}>10</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', backgroundColor: '#f0eded', padding: '4px 8px', borderRadius: '6px' }}>
            <LeftOutlined style={{ fontSize: '12px', color: '#a0aabf', cursor: 'not-allowed' }} />
            <span style={{ fontSize: '13px', fontWeight: 600 }}>1 <span style={{ color: '#a0aabf', margin: '0 4px', fontWeight: 400 }}>/</span> 1</span>
            <RightOutlined style={{ fontSize: '12px', color: '#a0aabf', cursor: 'not-allowed' }} />
          </div>
        </div>
      </div>

    </div>
  );
};
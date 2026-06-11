import React from 'react';
import { 
  DatabaseOutlined, FileTextOutlined, ArrowRightOutlined, 
  CheckCircleFilled, WarningFilled, ProfileOutlined, 
  HddOutlined, TableOutlined, BarcodeOutlined
} from '@ant-design/icons';

export const MappingOverviewStep: React.FC = () => {
  const sourceStats = {
    name: 'sales_transactions_2024_Q1.parquet',
    path: 's3://prod-lake/sales_data/',
    format: 'Apache Parquet',
    sizeMB: 1400,
    columns: 48,
    rows: 12400000
  };

  const targetStats = {
    name: 'FACT_DAILY_REVENUE',
    path: 'snowflake://FINANCE_DB/CORE_SCHEMA/',
    format: 'Snowflake Table',
    sizeMB: 1450,
    columns: 52,
    rows: 12405221
  };

  const runComparison = () => {
    const sizeDiff = Math.abs(sourceStats.sizeMB - targetStats.sizeMB) / sourceStats.sizeMB;
    const colDiff = Math.abs(sourceStats.columns - targetStats.columns) / sourceStats.columns;
    const rowDiff = Math.abs(sourceStats.rows - targetStats.rows) / sourceStats.rows;

    const mismatches = {
      size: sizeDiff > 0.20,
      columns: colDiff > 0.20,
      rows: rowDiff > 0.05
    };

    const issues = [];
    if (mismatches.size) issues.push(`File Size`);
    if (mismatches.columns) issues.push(`Columns`);
    if (mismatches.rows) issues.push(`Row Count`);

    if (issues.length > 0) {
      return {
        status: 'warning',
        title: 'Significant Mismatch Detected',
        message: `There is a huge discrepancy in: ${issues.join(', ')}. Please verify these are the correct files before proceeding.`,
        mismatches
      };
    }

    return {
      status: 'success',
      title: 'Litmus Test Passed',
      message: 'Source and Target profiles look highly compatible.',
      mismatches
    };
  };

  const alert = runComparison();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px' }}>
        
        {/* SOURCE CARD */}
        <div style={{ flex: 1, backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileTextOutlined style={{ color: '#1677ff', fontSize: '18px' }} />
              <span style={{ fontSize: '12px', color: '#1677ff', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Source Entity</span>
            </div>
            <span style={{ fontSize: '10px', backgroundColor: '#e6f4ff', color: '#1677ff', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>CONNECTED</span>
          </div>
          
          <h4 style={{ fontSize: '18px', color: '#1b1b1c', margin: '0 0 4px 0', fontWeight: 600 }}>{sourceStats.name}</h4>
          <p style={{ fontSize: '12px', color: '#727786', fontFamily: 'var(--font-mono)', margin: '0 0 24px 0', wordBreak: 'break-all' }}>{sourceStats.path}</p>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><ProfileOutlined /> Format</span>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#1b1b1c' }}>{sourceStats.format}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><HddOutlined /> Size</span>
              {/* ⚡ Red text color applied if mismatch detected */}
              <span style={{ fontSize: '13px', fontWeight: 600, color: alert.mismatches.size ? '#ba1a1a' : '#1b1b1c' }}>{(sourceStats.sizeMB / 1024).toFixed(2)} GB</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><TableOutlined /> Columns</span>
              {/* ⚡ Red text color applied if mismatch detected */}
              <span style={{ fontSize: '13px', fontWeight: 600, color: alert.mismatches.columns ? '#ba1a1a' : '#1b1b1c' }}>{sourceStats.columns}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><BarcodeOutlined /> Rows</span>
              {/* ⚡ Red text color applied if mismatch detected */}
              <span style={{ fontSize: '13px', fontWeight: 600, color: alert.mismatches.rows ? '#ba1a1a' : '#1b1b1c' }}>{(sourceStats.rows / 1000000).toFixed(1)}M</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: '#f6f3f2', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #d9d9d9' }}>
            <ArrowRightOutlined style={{ fontSize: '20px', color: '#727786' }} />
          </div>
          <span style={{ fontSize: '10px', marginTop: '8px', fontWeight: 700, color: '#727786', letterSpacing: '0.05em' }}>MAPPING</span>
        </div>

        {/* TARGET CARD */}
        <div style={{ flex: 1, backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <DatabaseOutlined style={{ color: '#16a34a', fontSize: '18px' }} />
              <span style={{ fontSize: '12px', color: '#16a34a', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Target Entity</span>
            </div>
            <span style={{ fontSize: '10px', backgroundColor: '#f0fdf4', color: '#16a34a', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>READY</span>
          </div>
          
          <h4 style={{ fontSize: '18px', color: '#1b1b1c', margin: '0 0 4px 0', fontWeight: 600 }}>{targetStats.name}</h4>
          <p style={{ fontSize: '12px', color: '#727786', fontFamily: 'var(--font-mono)', margin: '0 0 24px 0', wordBreak: 'break-all' }}>{targetStats.path}</p>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><ProfileOutlined /> Format</span>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#1b1b1c' }}>{targetStats.format}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><HddOutlined /> Size</span>
              {/* ⚡ Red text color applied if mismatch detected */}
              <span style={{ fontSize: '13px', fontWeight: 600, color: alert.mismatches.size ? '#ba1a1a' : '#1b1b1c' }}>{(targetStats.sizeMB / 1024).toFixed(2)} GB</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><TableOutlined /> Columns</span>
              {/* ⚡ Red text color applied if mismatch detected */}
              <span style={{ fontSize: '13px', fontWeight: 600, color: alert.mismatches.columns ? '#ba1a1a' : '#1b1b1c' }}>{targetStats.columns}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}><BarcodeOutlined /> Rows</span>
              {/* ⚡ Red text color applied if mismatch detected */}
              <span style={{ fontSize: '13px', fontWeight: 600, color: alert.mismatches.rows ? '#ba1a1a' : '#1b1b1c' }}>{(targetStats.rows / 1000000).toFixed(1)}M</span>
            </div>
          </div>
        </div>

      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px 20px', borderRadius: '8px', backgroundColor: alert.status === 'success' ? '#f0fdf4' : '#fffbeb', border: alert.status === 'success' ? '1px solid #bbf7d0' : '1px solid #fde68a' }}>
        {alert.status === 'success' ? (
          <CheckCircleFilled style={{ color: '#16a34a', fontSize: '20px', marginTop: '2px' }} />
        ) : (
          <WarningFilled style={{ color: '#d97706', fontSize: '20px', marginTop: '2px' }} />
        )}
        <div>
          <h5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700, color: alert.status === 'success' ? '#15803d' : '#92400e' }}>{alert.title}</h5>
          <p style={{ margin: 0, fontSize: '13px', color: alert.status === 'success' ? '#166534' : '#b45309', lineHeight: '20px' }}>{alert.message}</p>
        </div>
      </div>

    </div>
  );
};
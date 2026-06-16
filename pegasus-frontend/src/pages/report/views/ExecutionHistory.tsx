import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  DownloadOutlined, 
  PlayCircleOutlined, 
  BranchesOutlined, // ⚡ FIX 1: Swapped to the correct Ant Design icon
  ClockCircleOutlined, 
  CalendarOutlined,
  FileTextOutlined,
  RightOutlined
} from '@ant-design/icons';

export const ExecutionHistory: React.FC = () => {
  const navigate = useNavigate();
  // ⚡ FIX 2: Properly extracted and typed the mappingId
  const { mappingId } = useParams<{ mappingId: string }>(); 
  
  // ⚡ Now mappingId is strictly read and used as the fallback!
  const MAPPING_NAME = mappingId || "DEMO_MAPPING_2026";

  const runs = [
    { id: 'RUN_882910_A', duration: '25 sec', end: "Jun 15 '26 | 18:00:27", metrics: { src: '79,999', tgt: '79,999', mismatch: '0', extra: '0', missing: '0', totalMis: '0', mapped: '42' } },
    { id: 'RUN_882909_A', duration: '18 sec', end: "Jun 15 '26 | 17:45:12", metrics: { src: '45,210', tgt: '45,210', mismatch: '12', extra: '0', missing: '3', totalMis: '15', mapped: '42' } }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
      {/* Header Area */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {/* Breadcrumbs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '12px' }}>
            <span onClick={() => navigate('/reports')} style={{ cursor: 'pointer', transition: 'color 0.2s' }} onMouseEnter={e => e.currentTarget.style.color = '#0057c2'} onMouseLeave={e => e.currentTarget.style.color = '#64748b'}>Reports</span>
            <RightOutlined style={{ fontSize: '10px' }} />
            <span style={{ color: '#0057c2', fontWeight: 500 }}>{MAPPING_NAME}</span>
            <RightOutlined style={{ fontSize: '10px' }} />
            <span style={{ color: '#1b1b1c', fontWeight: 500 }}>History</span>
          </div>

          {/* Mapping Title Badge */}
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ backgroundColor: '#f0eded', border: '1px solid #c1c6d7', padding: '4px 12px', borderRadius: '999px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BranchesOutlined style={{ color: '#414755', fontSize: '14px' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#1b1b1c', fontWeight: 600 }}>{MAPPING_NAME}</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '12px' }}>
          <button style={{ backgroundColor: '#fff', border: '1px solid #c1c6d7', color: '#1b1b1c', padding: '8px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
            <DownloadOutlined /> Download PDF Report
          </button>
          <button style={{ backgroundColor: '#0057c2', border: 'none', color: '#fff', padding: '8px 16px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', fontWeight: 500, cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
            <PlayCircleOutlined /> Run Validation
          </button>
        </div>
      </div>

      {/* Execution Runs List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {runs.map((run, idx) => (
          <div key={idx} style={{ backgroundColor: '#fff', border: '1px solid #e5e2e1', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', opacity: idx > 0 ? 0.8 : 1 }}>
            
            {/* Card Header */}
            <div style={{ backgroundColor: '#fcf9f8', borderBottom: '1px solid #e5e2e1', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                <span style={{ fontSize: '18px', fontWeight: 600, color: '#1b1b1c', fontFamily: 'var(--font-mono)' }}>{run.id}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', color: '#64748b', fontSize: '12px' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><ClockCircleOutlined /> {run.duration}</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><CalendarOutlined /> Ended: {run.end}</span>
                </div>
              </div>
              <button 
                onClick={() => navigate(`/reports/${MAPPING_NAME}/history/${run.id}/snippet`)}
                style={{ backgroundColor: '#fff', border: '1px solid #c1c6d7', color: '#1b1b1c', padding: '6px 12px', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500, cursor: 'pointer' }}
              >
                <FileTextOutlined /> Snippet
              </button>
            </div>

            {/* Metrics Row */}
            <div style={{ overflowX: 'auto', display: 'flex', padding: '16px 24px', gap: '24px' }}>
              <MetricItem label="Source Rows" value={run.metrics.src} />
              <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
              <MetricItem label="Target Rows" value={run.metrics.tgt} />
              <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
              <MetricItem label="Cell Mismatch" value={run.metrics.mismatch} color={run.metrics.mismatch !== '0' ? '#ba1a1a' : '#1b1b1c'} />
              <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
              <MetricItem label="Extra Rows" value={run.metrics.extra} />
              <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
              <MetricItem label="Missing Rows" value={run.metrics.missing} />
              <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
              <MetricItem label="Total Mismatched" value={run.metrics.totalMis} />
              <div style={{ width: '1px', backgroundColor: '#e5e2e1' }} />
              <MetricItem label="Mapped Cols" value={run.metrics.mapped} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const MetricItem: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color = '#1b1b1c' }) => (
  <div style={{ display: 'flex', flexDirection: 'column', minWidth: '120px' }}>
    <span style={{ fontSize: '10px', fontWeight: 700, color: '#727786', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>{label}</span>
    <span style={{ fontSize: '20px', fontWeight: 600, color }}>{value}</span>
  </div>
);
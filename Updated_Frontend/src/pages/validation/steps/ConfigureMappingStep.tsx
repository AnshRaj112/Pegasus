import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  SearchOutlined,
  FilterOutlined,
  ThunderboltOutlined,
  HolderOutlined,
  CloseOutlined,
  LeftOutlined,
  RightOutlined,
  KeyOutlined,
  DashboardOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  CloseCircleFilled,
  CheckCircleOutlined,
  SyncOutlined
} from '@ant-design/icons';
import { ValidationReport } from '../components/ValidationReport';

interface MappingItem {
  id: string;
  sourceColumn: string;
  dataType: 'String' | 'Float' | 'Int' | 'Bool';
  targetMappings: string[];
  previewValue: string;
}

export const ConfigureMappingStep: React.FC = () => {
  const [overrideDelimiter, setOverrideDelimiter] = useState<string>(',');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [newTagText, setNewTagText] = useState<{ [key: string]: string }>({});
  
  // State Engine Loops
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationStatus, setValidationStatus] = useState<'idle' | 'success' | 'failed'>('idle');
  const [viewDetailedReport, setViewDetailedReport] = useState<boolean>(false);
  const navigate = useNavigate();

  const [columnsMatrix, setColumnsMatrix] = useState<MappingItem[]>([
    { id: '1', sourceColumn: 'transaction_id', dataType: 'String', targetMappings: ['ID_Primary', 'Legacy_Key'], previewValue: 'TXN-99283-XQA' },
    { id: '2', sourceColumn: 'customer_email', dataType: 'String', targetMappings: ['Email_Address'], previewValue: 'j.doe@enterprise.com' },
    { id: '3', sourceColumn: 'amount_gross', dataType: 'Float', targetMappings: ['Total_Value'], previewValue: '1240.50' },
    { id: '4', sourceColumn: 'quantity', dataType: 'Int', targetMappings: [], previewValue: '5' },
    { id: '5', sourceColumn: 'timestamp_utc', dataType: 'String', targetMappings: ['Event_Time'], previewValue: '2023-10-27T10:22:01Z' },
    { id: '6', sourceColumn: 'region_code', dataType: 'String', targetMappings: ['Geo_ID'], previewValue: 'US-WEST-2' },
    { id: '7', sourceColumn: 'is_active', dataType: 'Bool', targetMappings: ['Status_Flag'], previewValue: 'true' }
  ]);

  const defaultUid = columnsMatrix.find(col => 
    ['id', 'uid', 'emp_id', 'transaction_id'].includes(col.sourceColumn.toLowerCase())
  )?.sourceColumn || columnsMatrix[0]?.sourceColumn;

  const [selectedUidColumn, setSelectedUidColumn] = useState<string>(defaultUid);

  const handleRemoveTag = (rowId: string, tagToRemove: string) => {
    setColumnsMatrix(prev => prev.map(row => {
      if (row.id === rowId) {
        return { ...row, targetMappings: row.targetMappings.filter(t => t !== tagToRemove) };
      }
      return row;
    }));
  };

  const handleAddTag = (rowId: string) => {
    const text = newTagText[rowId]?.trim();
    if (!text) return;
    setColumnsMatrix(prev => prev.map(row => {
      if (row.id === rowId && !row.targetMappings.includes(text)) {
        return { ...row, targetMappings: [...row.targetMappings, text] };
      }
      return row;
    }));
    setNewTagText(prev => ({ ...prev, [rowId]: '' }));
  };

  // Simulates an operational success path
  const simulateSuccessPipeline = () => {
    setIsValidating(true);
    setValidationStatus('idle');
    setTimeout(() => {
      setIsValidating(false);
      setValidationStatus('success');
    }, 1200);
  };

  // Simulates an execution failure error path
  const simulateFailurePipeline = () => {
    setIsValidating(true);
    setValidationStatus('idle');
    setTimeout(() => {
      setIsValidating(false);
      setValidationStatus('failed');
    }, 1200);
  };

  const getTypeBadgeStyle = (type: MappingItem['dataType']): React.CSSProperties => {
    const base: React.CSSProperties = { padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 };
    if (type === 'String') return { ...base, backgroundColor: '#e6f4ff', color: '#1677ff' };
    if (type === 'Float') return { ...base, backgroundColor: '#f9f0ff', color: '#722ed1' };
    if (type === 'Int') return { ...base, backgroundColor: '#fff7e6', color: '#fa8c16' };
    return { ...base, backgroundColor: '#f6ffed', color: '#52c41a' };
  };

  const filteredColumns = columnsMatrix.filter(col => 
    col.sourceColumn.toLowerCase().includes(searchQuery.toLowerCase()) ||
    col.dataType.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (viewDetailedReport) {
    return <ValidationReport onBack={() => setViewDetailedReport(false)} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '22px', color: '#1b1b1c', margin: 0, fontWeight: 600 }}>
          Mapping Configuration Matrix
        </h1>
      </div>

      {/* Control Action Toolbar Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #d9d9d9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 500, color: '#414755' }}>Override Delimiter:</span>
            <input 
              type="text"
              value={overrideDelimiter}
              onChange={(e) => setOverrideDelimiter(e.target.value)}
              style={{ width: '64px', height: '32px', textAlign: 'center', borderRadius: '6px', border: '1px solid #d9d9d9', outline: 'none', fontWeight: 600, backgroundColor: '#ffffff' }}
              maxLength={5}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 500, color: '#414755' }}><KeyOutlined style={{ color: '#fa8c16' }} /> Primary UID Column:</span>
            <select
              value={selectedUidColumn}
              onChange={(e) => setSelectedUidColumn(e.target.value)}
              style={{ height: '32px', padding: '0 8px', borderRadius: '6px', border: '1px solid #d9d9d9', background: '#ffffff', outline: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: 500 }}
            >
              {columnsMatrix.map(col => (
                <option key={col.id} value={col.sourceColumn}>{col.sourceColumn}</option>
              ))}
            </select>
          </div>
        </div>
        <div style={{ fontSize: '13px', color: '#727786', fontStyle: 'italic' }}>Auto-Detected 42 schema columns</div>
      </div>

      {/* Grid Canvas Table Frame */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #d9d9d9', overflow: 'hidden' }}>
        <div style={{ padding: '16px', borderBottom: '1px solid #d9d9d9', display: 'flex', justifyContent: 'space-between', backgroundColor: '#ffffff' }}>
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', display: 'flex', alignItems: 'center' }}><SearchOutlined /></span>
            <input 
              type="text" 
              placeholder="Filter attributes by label names..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ padding: '6px 12px 6px 36px', borderRadius: '8px', border: '1px solid #d9d9d9', backgroundColor: '#f8fafc', fontSize: '13px', width: '320px', outline: 'none' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button style={{ height: '32px', padding: '0 12px', background: 'none', border: '1px solid #d9d9d9', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '13px' }}><FilterOutlined /> Filters</button>
            <button style={{ height: '32px', padding: '0 12px', background: 'none', border: '1px solid #d9d9d9', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '13px' }}><ThunderboltOutlined /> Auto-Map</button>
          </div>
        </div>

        <div className="custom-scrollbar" style={{ overflowY: 'auto', maxHeight: '350px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', color: '#64748b', fontSize: '11px', textTransform: 'uppercase', fontWeight: 600, borderBottom: '1px solid #d9d9d9', zIndex: 10 }}>
              <tr>
                <th style={{ padding: '12px', width: '25%' }}>Source Column</th>
                <th style={{ padding: '12px', width: '140px' }}>Data Type</th>
                <th style={{ padding: '12px' }}>Target Mapping fields</th>
                <th style={{ padding: '12px', width: '25%' }}>Preview Value</th>
              </tr>
            </thead>
            <tbody>
              {filteredColumns.map(row => {
                const isUidColumn = row.sourceColumn === selectedUidColumn;
                return (
                  <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: isUidColumn ? '#fffbe6' : 'transparent' }}>
                    <td style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <HolderOutlined style={{ color: '#94a3b8' }} />
                        <span style={{ fontWeight: isUidColumn ? 700 : 500, color: isUidColumn ? '#fa8c16' : 'inherit' }}>{row.sourceColumn}</span>
                        {isUidColumn && <span style={{ fontSize: '10px', backgroundColor: '#fa8c16', color: 'white', padding: '1px 4px', borderRadius: '4px', fontWeight: 700 }}>UID</span>}
                      </div>
                    </td>
                    <td style={{ padding: '12px' }}><span style={getTypeBadgeStyle(row.dataType)}>{row.dataType}</span></td>
                    <td style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                        {row.targetMappings.length === 0 ? (
                          <span style={{ fontSize: '13px', color: '#727786', fontStyle: 'italic' }}>Unmapped column field...</span>
                        ) : (
                          row.targetMappings.map(tag => (
                            <span key={tag} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: '#f5f5f5', border: '1px solid #d9d9d9', borderRadius: '4px', padding: '2px 8px', fontSize: '13px' }}>
                              {tag}
                              <button onClick={() => handleRemoveTag(row.id, tag)} style={{ border: 'none', background: 'none', padding: 0, cursor: 'pointer', display: 'flex', alignItems: 'center', color: '#8c8c8c' }}><CloseOutlined style={{ fontSize: '10px' }} /></button>
                            </span>
                          ))
                        )}
                        <input 
                          type="text" placeholder="+ Add..."
                          value={newTagText[row.id] || ''}
                          onChange={(e) => setNewTagText({ ...newTagText, [row.id]: e.target.value })}
                          onKeyDown={(e) => e.key === 'Enter' && handleAddTag(row.id)}
                          style={{ border: 'none', outline: 'none', padding: '2px 4px', fontSize: '13px', width: '80px', color: '#1677ff', background: 'transparent' }}
                        />
                      </div>
                    </td>
                    <td style={{ padding: '12px' }}><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#414755', backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: '4px' }}>{row.previewValue}</code></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div style={{ padding: '12px 16px', borderTop: '1px solid #d9d9d9', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f8fafc' }}>
          <div style={{ fontSize: '13px', color: '#727786' }}>Showing 1-7 of 42 attributes</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button disabled style={{ background: 'none', border: 'none', opacity: 0.3, cursor: 'not-allowed' }}><LeftOutlined /></button>
            <span style={{ fontSize: '13px' }}>Page 1 of 6</span>
            <button style={{ background: 'none', border: 'none', cursor: 'pointer' }}><RightOutlined /></button>
          </div>
        </div>
      </div>

      {/* Execution Sim Controls Dashboard */}
      {validationStatus === 'idle' && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
          <button 
            onClick={simulateFailurePipeline}
            disabled={isValidating}
            style={{ padding: '10px 20px', backgroundColor: '#ffffff', color: '#ba1a1a', border: '1px solid #ba1a1a', borderRadius: '6px', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}
          >
            Simulate Failed Run
          </button>
          <button 
            onClick={simulateSuccessPipeline}
            disabled={isValidating}
            style={{ padding: '10px 24px', backgroundColor: '#1677ff', color: '#ffffff', border: 'none', borderRadius: '6px', fontSize: '14px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {isValidating ? <SyncOutlined spin /> : <DashboardOutlined />} 
            {isValidating ? 'Running Computations...' : 'Execute Audit Validation'}
          </button>
        </div>
      )}

      {/* 🔴 ERROR STATE UI DASHBOARD */}
      {validationStatus === 'failed' && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px', backgroundColor: '#ffdad6', border: '1px solid #ba1a1a', padding: '20px', borderRadius: '8px', marginTop: '16px' }}>
          <CloseCircleFilled style={{ color: '#ba1a1a', fontSize: '24px', marginTop: '2px' }} />
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: '0 0 6px 0', fontSize: '16px', fontWeight: 700, color: '#ba1a1a' }}>Validation Processing Interrupt Event</h4>
            <p style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#ba1a1a', lineHeight: '20px' }}>
              The computation pipeline was terminated due to a parsing exception: <strong>Inconsistent schema record width structure at row ledger position index 405,221</strong>. The column lengths provided do not align with specified system delimiter arguments.
            </p>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button onClick={simulateSuccessPipeline} style={{ padding: '6px 14px', backgroundColor: '#ba1a1a', color: '#ffffff', border: 'none', borderRadius: '4px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                Re-Run Pipeline Process
              </button>
              <button onClick={() => setValidationStatus('idle')} style={{ padding: '6px 14px', backgroundColor: 'transparent', color: '#ba1a1a', border: '1px solid #ba1a1a', borderRadius: '4px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                Reset Matrix Config
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 🟢 SUCCESS STATE SUMMARY PANEL BLOCK */}
      {validationStatus === 'success' && (
        <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#1b1b1c', margin: 0 }}>Validation Output Summary Metrics</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: '16px' }}>
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
              <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#727786', textTransform: 'uppercase' }}>Match Status</p>
              <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', color: '#ba1a1a', fontSize: '20px', fontWeight: 700 }}>
                <CloseCircleFilled style={{ fontSize: '18px' }} /> NO
              </div>
            </div>
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
              <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#727786', textTransform: 'uppercase' }}><FileTextOutlined /> Source Rows</p>
              <p style={{ margin: '8px 0 0 0', fontSize: '20px', fontWeight: 700, color: '#1b1b1c' }}>12,400,000</p>
            </div>
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
              <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#727786', textTransform: 'uppercase' }}><DatabaseOutlined /> Target Rows</p>
              <p style={{ margin: '8px 0 0 0', fontSize: '20px', fontWeight: 700, color: '#1b1b1c' }}>12,405,221</p>
            </div>
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
              <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#727786', textTransform: 'uppercase' }}>Total Mismatches</p>
              <p style={{ margin: '8px 0 0 0', fontSize: '20px', fontWeight: 700, color: '#ba1a1a' }}>8,000</p>
            </div>
            <div style={{ backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
              <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#727786', textTransform: 'uppercase' }}><SyncOutlined /> Run Time</p>
              <p style={{ margin: '8px 0 0 0', fontSize: '20px', fontWeight: 700, color: '#1677ff' }}>4.23s</p>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '8px' }}>
            <button 
              onClick={() => navigate('/validation/report/JOB-2026-VAL-99X')}
              style={{ padding: '10px 24px', backgroundColor: '#ffffff', color: '#1677ff', border: '1px solid #1677ff', borderRadius: '6px', fontSize: '14px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <CheckCircleOutlined /> View Detailed Analytical Evaluation Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
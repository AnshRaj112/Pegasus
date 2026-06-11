import React, { useState, useEffect } from 'react';
import { useAppDispatch } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { 
  DatabaseOutlined, FolderOutlined, FolderOpenOutlined, 
  SearchOutlined, ArrowRightOutlined, 
  FileTextOutlined, DeleteOutlined, CheckOutlined,
  CloudOutlined, RightOutlined, DownOutlined, FolderFilled
} from '@ant-design/icons';

export interface FileExplorerItem {
  id: string;
  name: string;
  type: 'file' | 'folder';
  size: string;
  modified: string;
  status: 'Ready' | 'Scanning';
}

export const FileSelectionStep: React.FC = () => {
  const dispatch = useAppDispatch();
  
  const [validationMode, setValidationMode] = useState<string>('Single to Single (Default)');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // ⚡ Hierarchical Storage State
  const [expandedStoreId, setExpandedStoreId] = useState<string>('gcs');
  const [activeDatabaseId, setActiveDatabaseId] = useState<string>('prod-lake');

  // ⚡ Arrays for Many-to-Many capability
  const [selectingFor, setSelectingFor] = useState<'source' | 'target'>('source');
  const [sourceFiles, setSourceFiles] = useState<FileExplorerItem[]>([]);
  const [targetFiles, setTargetFiles] = useState<FileExplorerItem[]>([]);

  // Redux Gatekeeper
  useEffect(() => {
    const isStepFullyConfigured = sourceFiles.length > 0 && targetFiles.length > 0;
    dispatch(validationActions.setStep1Valid(isStepFullyConfigured));
  }, [sourceFiles, targetFiles, dispatch]);

  const dataStores = [
    {
      id: 'gcs', name: 'GCS Cloud Storage', icon: <CloudOutlined />, databases: [
        { id: 'prod-lake', name: 'production-datalake-v1', region: 'us-central1-standard' },
        { id: 'staging-raw', name: 'staging-raw-events', region: 'multi-region-asia' },
        { id: 'archive', name: 'archive-2023-q4', region: 'coldline-storage' }
      ]
    },
    {
      id: 'snowflake', name: 'Snowflake Warehouse', icon: <DatabaseOutlined />, databases: [
        { id: 'finance-db', name: 'FINANCE_DB', region: 'aws-us-east-1' },
        { id: 'hr-db', name: 'HR_DB', region: 'aws-us-east-1' }
      ]
    }
  ];

  const filesMockData: FileExplorerItem[] = [
    { id: 'f1', name: '2023_Archive', type: 'folder', size: '--', modified: '2024-01-01 00:00', status: 'Ready' },
    { id: 'f2', name: '2024_Q1_Extracts', type: 'folder', size: '--', modified: '2024-04-01 10:00', status: 'Ready' },
    { id: '1', name: 'sales_transactions_2024_Q1.parquet', type: 'file', size: '1.4 GB', modified: '2024-04-02 11:20', status: 'Ready' },
    { id: '2', name: 'customer_master_legacy_v2.csv', type: 'file', size: '450 MB', modified: '2023-11-14 18:20', status: 'Ready' },
    { id: '3', name: 'inventory_sync_err.log', type: 'file', size: '12 MB', modified: '2024-01-15 11:05', status: 'Scanning' },
    { id: '4', name: 'financial_ledger_eu_region.parquet', type: 'file', size: '2.1 GB', modified: '2024-03-15 14:30', status: 'Ready' },
  ];

  const filteredFiles = filesMockData.filter(f => f.name.toLowerCase().includes(searchQuery.toLowerCase()));

  // ⚡ Multi-Select Logic
  const handleRowClick = (file: FileExplorerItem) => {
    if (file.type === 'folder') return; // Prevent selecting folders as files for now

    const isMultiMode = validationMode === 'Many to Many' || validationMode === 'Batch Comparison';

    if (selectingFor === 'source') {
      if (isMultiMode) {
        setSourceFiles(prev => prev.some(f => f.id === file.id) ? prev.filter(f => f.id !== file.id) : [...prev, file]);
      } else {
        setSourceFiles([file]);
        if (targetFiles.length === 0) setSelectingFor('target');
      }
    } else if (selectingFor === 'target') {
      if (isMultiMode) {
        setTargetFiles(prev => prev.some(f => f.id === file.id) ? prev.filter(f => f.id !== file.id) : [...prev, file]);
      } else {
        setTargetFiles([file]);
        setSelectingFor('none' as any);
      }
    }
  };

  const clearSelection = (type: 'source' | 'target', fileId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (type === 'source') setSourceFiles(prev => prev.filter(f => f.id !== fileId));
    if (type === 'target') setTargetFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const getActiveDbName = () => {
    for (const store of dataStores) {
      const db = store.databases.find(d => d.id === activeDatabaseId);
      if (db) return db.name;
    }
    return 'Database';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '24px' }}>
      
      <div>
        <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px', color: '#414755' }}>
          Validation Mode
        </label>
        <select
          value={validationMode}
          onChange={(e) => {
            setValidationMode(e.target.value);
            // Reset selections when changing modes to prevent invalid states
            setSourceFiles([]);
            setTargetFiles([]);
            setSelectingFor('source');
          }}
          style={{ width: '320px', height: '40px', padding: '0 12px', borderRadius: '8px', border: '1px solid #d9d9d9', backgroundColor: '#ffffff', fontSize: '14px', outline: 'none', cursor: 'pointer' }}
        >
          <option>Single to Single (Default)</option>
          <option>Many to Many</option>
          <option>Batch Comparison</option>
        </select>
      </div>

      <div style={{ display: 'flex', alignItems: 'stretch', gap: '24px', backgroundColor: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #d9d9d9' }}>
        {/* Source Box */}
        <div onClick={() => setSelectingFor('source')} style={{ flex: 1, padding: '16px', borderRadius: '8px', border: selectingFor === 'source' ? '2px solid #1677ff' : '1px dashed #727786', backgroundColor: selectingFor === 'source' ? '#e6f4ff' : (sourceFiles.length > 0 ? '#f6f3f2' : 'transparent'), cursor: 'pointer', transition: 'all 0.2s' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#1677ff', textTransform: 'uppercase' }}>1. Source Files ({sourceFiles.length})</span>
          </div>
          <div style={{ marginTop: '8px', minHeight: '40px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {sourceFiles.length > 0 ? sourceFiles.map(file => (
              <div key={file.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: '#ffffff', padding: '6px 12px', borderRadius: '6px', border: '1px solid #d9d9d9' }}>
                <CheckOutlined style={{ color: '#1677ff' }} />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>{file.name}</span>
                <button onClick={(e) => clearSelection('source', file.id, e)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#ba1a1a' }}><DeleteOutlined /></button>
              </div>
            )) : <p style={{ margin: '8px 0 0 0', fontSize: '14px', color: '#414755', fontStyle: 'italic' }}>Awaiting selection...</p>}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center' }}><ArrowRightOutlined style={{ fontSize: '24px', color: '#727786' }} /></div>

        {/* Target Box */}
        <div onClick={() => setSelectingFor('target')} style={{ flex: 1, padding: '16px', borderRadius: '8px', border: selectingFor === 'target' ? '2px solid #16a34a' : '1px dashed #727786', backgroundColor: selectingFor === 'target' ? '#f0fdf4' : (targetFiles.length > 0 ? '#f6f3f2' : 'transparent'), cursor: 'pointer', transition: 'all 0.2s' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#16a34a', textTransform: 'uppercase' }}>2. Target Files ({targetFiles.length})</span>
          </div>
          <div style={{ marginTop: '8px', minHeight: '40px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {targetFiles.length > 0 ? targetFiles.map(file => (
              <div key={file.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: '#ffffff', padding: '6px 12px', borderRadius: '6px', border: '1px solid #d9d9d9' }}>
                <CheckOutlined style={{ color: '#16a34a' }} />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>{file.name}</span>
                <button onClick={(e) => clearSelection('target', file.id, e)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#ba1a1a' }}><DeleteOutlined /></button>
              </div>
            )) : <p style={{ margin: '8px 0 0 0', fontSize: '14px', color: '#414755', fontStyle: 'italic' }}>Awaiting selection...</p>}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, minmax(0, 1fr))', gap: '24px', height: '500px' }}>
        
        {/* Hierarchical Navigation Left Column */}
        <div className="custom-scrollbar" style={{ gridColumn: 'span 4 / span 4', display: 'flex', flexDirection: 'column', backgroundColor: '#f8fafc', borderRadius: '12px', border: '1px solid #d9d9d9', overflowY: 'auto', padding: '12px' }}>
          {dataStores.map(store => (
            <div key={store.id} style={{ marginBottom: '8px' }}>
              {/* Datastore Header */}
              <div 
                onClick={() => setExpandedStoreId(expandedStoreId === store.id ? '' : store.id)}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '14px' }}
              >
                {store.icon}
                <span style={{ flex: 1 }}>{store.name}</span>
                {expandedStoreId === store.id ? <DownOutlined style={{ fontSize: '12px' }} /> : <RightOutlined style={{ fontSize: '12px' }} />}
              </div>
              
              {/* Database Children */}
              {expandedStoreId === store.id && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px', paddingLeft: '24px' }}>
                  {store.databases.map(db => (
                    <div 
                      key={db.id} 
                      onClick={() => setActiveDatabaseId(db.id)}
                      style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', backgroundColor: activeDatabaseId === db.id ? '#e6f4ff' : 'transparent', color: activeDatabaseId === db.id ? '#1677ff' : '#414755' }}
                    >
                      <FolderOutlined />
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: activeDatabaseId === db.id ? 700 : 500 }}>{db.name}</div>
                        <div style={{ fontSize: '10px', color: '#727786' }}>{db.region}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Right Column: Files */}
        <div style={{ gridColumn: 'span 8 / span 8', display: 'flex', flexDirection: 'column', backgroundColor: 'white', borderRadius: '12px', border: '1px solid #d9d9d9', overflow: 'hidden' }}>
          <div style={{ padding: '16px', borderBottom: '1px solid #d9d9d9', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
              <FolderOpenOutlined />
              <span>{getActiveDbName()} / data / </span>
            </div>
            <div style={{ position: 'relative' }}>
              <input type="text" placeholder="Search files..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={{ padding: '6px 12px 6px 36px', borderRadius: '8px', border: '1px solid #d9d9d9', backgroundColor: '#f8fafc', fontSize: '12px', width: '256px', outline: 'none' }} />
              <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            </div>
          </div>

          <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', color: '#64748b', fontSize: '11px', textTransform: 'uppercase', fontWeight: 600, borderBottom: '1px solid #d9d9d9', zIndex: 10 }}>
                <tr>
                  <th style={{ padding: '12px', width: '40px' }}></th>
                  <th style={{ padding: '12px' }}>Name</th>
                  <th style={{ padding: '12px' }}>Size</th>
                  <th style={{ padding: '12px' }}>Status</th>
                </tr>
              </thead>
              <tbody style={{ fontSize: '14px' }}>
                {filteredFiles.map(file => {
                  const isSource = sourceFiles.some(f => f.id === file.id);
                  const isTarget = targetFiles.some(f => f.id === file.id);
                  const isSelected = isSource || isTarget;

                  return (
                    <tr 
                      key={file.id} 
                      onClick={() => handleRowClick(file)}
                      style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: isSelected ? '#f0f8ff' : 'transparent', cursor: file.type === 'folder' ? 'default' : 'pointer' }}
                    >
                      <td style={{ padding: '12px' }}>
                        {file.type === 'file' && <input type="checkbox" checked={isSelected} readOnly style={{ cursor: 'pointer', accentColor: '#1677ff' }} />}
                      </td>
                      <td style={{ padding: '12px', fontWeight: 500 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {file.type === 'folder' ? <FolderFilled style={{ color: '#faad14', fontSize: '18px' }} /> : <FileTextOutlined style={{ color: isSelected ? '#1677ff' : '#727786', fontSize: '16px' }} />}
                          <span style={{ color: file.type === 'folder' ? '#1b1b1c' : 'inherit' }}>{file.name}</span>
                          {isSource && <span style={{ fontSize: '10px', backgroundColor: '#1677ff', color: 'white', padding: '2px 6px', borderRadius: '4px' }}>SOURCE</span>}
                          {isTarget && <span style={{ fontSize: '10px', backgroundColor: '#16a34a', color: 'white', padding: '2px 6px', borderRadius: '4px' }}>TARGET</span>}
                        </div>
                      </td>
                      <td style={{ padding: '12px', fontSize: '12px', color: '#414755', fontFamily: 'var(--font-mono)' }}>{file.size}</td>
                      <td style={{ padding: '12px' }}>
                        {file.type === 'file' && (
                          <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', backgroundColor: file.status === 'Ready' ? '#f0fdf4' : '#fffbeb', color: file.status === 'Ready' ? '#15803d' : '#b45309', border: file.status === 'Ready' ? '1px solid #bbf7d0' : '1px solid #fde68a' }}>
                            {file.status}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { Api, type CloudConnection } from '../../../shared/api/Api';
import {
  FolderOutlined, FolderOpenOutlined, SearchOutlined, ArrowRightOutlined,
  FileTextOutlined, DeleteOutlined, CheckOutlined, CloudOutlined,
  FolderFilled, ArrowUpOutlined
} from '@ant-design/icons';

export interface FileExplorerItem {
  id: string;
  name: string;
  objectName: string;
  type: 'file' | 'folder';
  size: string;
  sizeBytes: number | null;
  createdAt: string;
  modifiedAt: string;
  owner: string;
  bucket?: string;
  connectionId?: string;
}

const formatBytes = (bytes: number | null | undefined): string => {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const formatDate = (dateString?: string | null): string => {
  if (!dateString) return '—';
  return new Date(dateString).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const toExplorerItem = (entry: any): FileExplorerItem => ({ 
  id: entry.path,
  name: entry.name,
  objectName: entry.path,
  type: entry.is_dir ? 'folder' : 'file',
  size: entry.is_dir ? '—' : formatBytes(entry.size_bytes),
  sizeBytes: entry.size_bytes ?? null,
  createdAt: formatDate(entry.created_at),
  modifiedAt: formatDate(entry.modified_at || entry.updated_at),
  owner: entry.owner || entry.created_by || '—',
});

const envFallbackConnection = (): CloudConnection | null => {
  const id = import.meta.env.VITE_GCS_CONNECTION_ID as string | undefined;
  const bucket = import.meta.env.VITE_GCS_BUCKET as string | undefined;
  if (!id) return null;
  return { id, name: 'Configured GCS connection', provider: 'google-cloud-storage', bucket: bucket ?? '', project_id: null, active: true };
};

export const FileSelectionStep: React.FC = () => {
  const dispatch = useAppDispatch();
  // ⚡ Pull existing validation form to restore state if navigating back
  const validationForm = useAppSelector((s) => s.validation.validationForm);

  const [validationMode, setValidationMode] = useState('Single to Single (Default)');
  const [searchQuery, setSearchQuery] = useState('');
  const [connections, setConnections] = useState<CloudConnection[]>([]);
  const [connectionsError, setConnectionsError] = useState<string | null>(null);
  const [activeConnectionId, setActiveConnectionId] = useState<string | null>(null);
  const [activeBucket, setActiveBucket] = useState<string | null>(null);
  const [browsePrefix, setBrowsePrefix] = useState('');
  const [parentPrefix, setParentPrefix] = useState<string | null>(null);
  const [browseEntries, setBrowseEntries] = useState<FileExplorerItem[]>([]);
  const [browseError, setBrowseError] = useState<string | null>(null);

  const [selectingFor, setSelectingFor] = useState<'source' | 'target' | 'none'>('source');
  
  // ⚡ Hydrate local state from Redux so selections persist across steps
  const [sourceFile, setSourceFile] = useState<FileExplorerItem | null>(() => {
    if (!validationForm.sourceCloud) return null;
    return {
      id: validationForm.sourceCloud.object_name,
      name: validationForm.sourceFileName || validationForm.sourceCloud.object_name.split('/').pop() || '',
      objectName: validationForm.sourceCloud.object_name,
      type: 'file', size: formatBytes(validationForm.sourceFileSize), sizeBytes: validationForm.sourceFileSize,
      bucket: validationForm.sourceCloud.bucket, connectionId: validationForm.sourceCloud.connection_id,
      createdAt: '—', modifiedAt: '—', owner: '—'
    } as FileExplorerItem;
  });

  const [targetFile, setTargetFile] = useState<FileExplorerItem | null>(() => {
    if (!validationForm.targetCloud) return null;
    return {
      id: validationForm.targetCloud.object_name,
      name: validationForm.targetFileName || validationForm.targetCloud.object_name.split('/').pop() || '',
      objectName: validationForm.targetCloud.object_name,
      type: 'file', size: formatBytes(validationForm.targetFileSize), sizeBytes: validationForm.targetFileSize,
      bucket: validationForm.targetCloud.bucket, connectionId: validationForm.targetCloud.connection_id,
      createdAt: '—', modifiedAt: '—', owner: '—'
    } as FileExplorerItem;
  });

  useEffect(() => {
    Api.listCloudConnections()
      .then((res) => {
        const active = res.data.filter((c) => c.active && c.provider === 'google-cloud-storage');
        setConnections(active);
        setConnectionsError(null);
        if (active[0]) {
          setActiveConnectionId(active[0].id);
          setActiveBucket(active[0].bucket);
        }
      })
      .catch(() => {
        const fallback = envFallbackConnection();
        if (fallback) {
          setConnections([fallback]); setActiveConnectionId(fallback.id); setActiveBucket(fallback.bucket); setConnectionsError(null);
        } else {
          setConnectionsError('Sign in via Admin to load GCS connections, or set VITE_GCS_CONNECTION_ID.');
        }
      });
  }, []);

  const loadBrowse = useCallback((connectionId: string, bucket: string, prefix: string) => {
    Api.browseCloud({ connection_id: connectionId, bucket, prefix, file_format: 'csv' })
      .then((res) => {
        setBrowseError(null);
        setBrowsePrefix(res.data.prefix);
        setParentPrefix(res.data.parent_prefix);
        const mappedEntries = res.data.entries.map((entry: any) => ({
          ...toExplorerItem(entry), connectionId, bucket: res.data.bucket
        }));
        setBrowseEntries(mappedEntries);
      })
      .catch(() => setBrowseError('Could not browse GCS bucket. Check connection credentials.'));
  }, []);

  useEffect(() => {
    if (activeConnectionId && activeBucket != null) {
      loadBrowse(activeConnectionId, activeBucket, browsePrefix);
    }
  }, [activeConnectionId, activeBucket, browsePrefix, loadBrowse]);

  useEffect(() => {
    const isStepFullyConfigured = Boolean(sourceFile && targetFile);
    dispatch(validationActions.setStep1Valid(isStepFullyConfigured));

    const makeCloudRef = (file: FileExplorerItem | null) =>
      file && file.connectionId
        ? { provider: 'google-cloud-storage' as const, connection_id: file.connectionId, bucket: file.bucket, object_name: file.objectName }
        : null;

    dispatch(validationActions.setValidationForm({
      sourceCloud: makeCloudRef(sourceFile),
      targetCloud: makeCloudRef(targetFile),
      sourceFileName: sourceFile?.name ?? null,
      targetFileName: targetFile?.name ?? null,
      sourceFileSize: sourceFile?.sizeBytes ?? null,
      targetFileSize: targetFile?.sizeBytes ?? null,
    }));
  }, [sourceFile, targetFile, dispatch]);

  const handleConnectionSelect = (conn: CloudConnection) => {
    setActiveConnectionId(conn.id);
    setActiveBucket(conn.bucket);
    setBrowsePrefix('');
  };

  const handleRowClick = (file: FileExplorerItem) => {
    if (file.type === 'folder') {
      setBrowsePrefix(file.objectName.endsWith('/') ? file.objectName : `${file.objectName}/`);
      return;
    }
    const isMultiMode = validationMode === 'Many to Many' || validationMode === 'Batch Comparison';
    if (selectingFor === 'source') {
      if (isMultiMode) return;
      setSourceFile(file);
      if (!targetFile) setSelectingFor('target');
    } else if (selectingFor === 'target') {
      if (isMultiMode) return;
      setTargetFile(file);
      setSelectingFor('none');
    }
  };

  const filteredFiles = browseEntries.filter((f) => f.name.toLowerCase().includes(searchQuery.toLowerCase()));
  const breadcrumb = activeBucket ? `gs://${activeBucket}/${browsePrefix}` : 'Select a connection';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '24px' }}>
      <div>
        <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px', color: '#414755' }}>Validation Pattern</label>
        <select
          value={validationMode}
          onChange={(e) => {
            setValidationMode(e.target.value); setSourceFile(null); setTargetFile(null); setSelectingFor('source');
          }}
          style={{ width: '320px', height: '40px', padding: '0 12px', borderRadius: '8px', border: '1px solid #d9d9d9', fontSize: '14px' }}
        >
          <option>Single to Single (Default)</option><option>Many to Many</option><option>Batch Comparison</option>
        </select>
      </div>

      <div style={{ display: 'flex', gap: '24px', backgroundColor: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #d9d9d9' }}>
        <div onClick={() => setSelectingFor('source')} style={{ flex: 1, padding: '16px', borderRadius: '8px', border: selectingFor === 'source' ? '2px solid #1677ff' : '1px dashed #727786', cursor: 'pointer' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#1677ff' }}>1. Source ({sourceFile ? 1 : 0})</span>
          {sourceFile ? (
            <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckOutlined style={{ color: '#1677ff' }} />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>{sourceFile.name}</span>
                <button type="button" onClick={(e) => { e.stopPropagation(); setSourceFile(null); setSelectingFor('source'); }} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#ba1a1a' }}><DeleteOutlined /></button>
              </div>
              <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'var(--font-mono)', wordBreak: 'break-all', paddingLeft: '22px' }}>
                gs://{sourceFile.bucket}/{sourceFile.objectName}
              </span>
            </div>
          ) : (
            <p style={{ margin: '8px 0 0', fontSize: '14px', color: '#727786', fontStyle: 'italic' }}>Pick a GCS object…</p>
          )}
        </div>
        
        <ArrowRightOutlined style={{ fontSize: '24px', color: '#727786', alignSelf: 'center' }} />
        
        <div onClick={() => setSelectingFor('target')} style={{ flex: 1, padding: '16px', borderRadius: '8px', border: selectingFor === 'target' ? '2px solid #16a34a' : '1px dashed #727786', cursor: 'pointer' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#16a34a' }}>2. Target ({targetFile ? 1 : 0})</span>
          {targetFile ? (
            <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckOutlined style={{ color: '#16a34a' }} />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>{targetFile.name}</span>
                <button type="button" onClick={(e) => { e.stopPropagation(); setTargetFile(null); setSelectingFor('target'); }} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#ba1a1a' }}><DeleteOutlined /></button>
              </div>
              <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'var(--font-mono)', wordBreak: 'break-all', paddingLeft: '22px' }}>
                gs://{targetFile.bucket}/{targetFile.objectName}
              </span>
            </div>
          ) : (
            <p style={{ margin: '8px 0 0', fontSize: '14px', color: '#727786', fontStyle: 'italic' }}>Pick a GCS object…</p>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '24px', height: '500px' }}>
        <div className="custom-scrollbar" style={{ gridColumn: 'span 3', backgroundColor: '#f8fafc', borderRadius: '12px', border: '1px solid #d9d9d9', overflowY: 'auto', padding: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', fontWeight: 600, fontSize: '14px' }}>
            <CloudOutlined /> GCS Connections
          </div>
          {connectionsError && (
            <p style={{ fontSize: '12px', color: '#ba1a1a', padding: '0 12px' }}>
              {connectionsError} <Link to="/admin" style={{ color: '#1677ff' }}>Sign in as admin</Link>
            </p>
          )}
          {connections.map((conn) => (
            <div
              key={conn.id}
              onClick={() => handleConnectionSelect(conn)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', margin: '4px 0',
                borderRadius: '6px', cursor: 'pointer', backgroundColor: activeConnectionId === conn.id ? '#e6f4ff' : 'transparent', color: activeConnectionId === conn.id ? '#1677ff' : '#414755',
              }}
            >
              <FolderOutlined />
              <div style={{ overflow: 'hidden' }}>
                <div style={{ fontSize: '13px', fontWeight: activeConnectionId === conn.id ? 700 : 500, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{conn.name}</div>
                <div style={{ fontSize: '10px', color: '#727786', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>gs://{conn.bucket}</div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ gridColumn: 'span 9', display: 'flex', flexDirection: 'column', backgroundColor: 'white', borderRadius: '12px', border: '1px solid #d9d9d9', overflow: 'hidden' }}>
          <div style={{ padding: '16px', borderBottom: '1px solid #d9d9d9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
              <FolderOpenOutlined />
              <span>{breadcrumb}</span>
              {parentPrefix != null && (
                <button type="button" onClick={() => setBrowsePrefix(parentPrefix)} style={{ marginLeft: '8px', border: 'none', background: '#f0f0f0', borderRadius: '4px', padding: '2px 8px', cursor: 'pointer', fontSize: '12px' }}><ArrowUpOutlined /> Up</button>
              )}
            </div>
            <div style={{ position: 'relative' }}>
              <input type="text" placeholder="Search…" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={{ padding: '6px 12px 6px 36px', borderRadius: '8px', border: '1px solid #d9d9d9', width: '200px', fontSize: '12px' }} />
              <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            </div>
          </div>

          <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto', overflowX: 'auto' }}>
            {browseError && <p style={{ padding: '16px', color: '#ba1a1a', fontSize: '13px' }}>{browseError}</p>}
            <table style={{ width: '100%', borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', fontSize: '11px', textTransform: 'uppercase', color: '#727786' }}>
                <tr>
                  <th style={{ padding: '12px', width: 40, borderBottom: '1px solid #d9d9d9' }} />
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9' }}>Name</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9' }}>Size</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9' }}>Date Modified</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9' }}>Owner</th>
                </tr>
              </thead>
              <tbody>
                {filteredFiles.map((file) => {
                  const isSource = sourceFile?.id === file.id;
                  const isTarget = targetFile?.id === file.id;
                  return (
                    <tr
                      key={file.id}
                      onClick={() => handleRowClick(file)}
                      style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: isSource || isTarget ? '#f0f8ff' : 'transparent', cursor: 'pointer', transition: 'background-color 0.2s' }}
                      onMouseEnter={(e) => { if (!isSource && !isTarget) e.currentTarget.style.backgroundColor = '#f8fafc'; }}
                      onMouseLeave={(e) => { if (!isSource && !isTarget) e.currentTarget.style.backgroundColor = 'transparent'; }}
                    >
                      <td style={{ padding: '12px' }}>{file.type === 'file' && <input type="checkbox" readOnly checked={isSource || isTarget} />}</td>
                      <td style={{ padding: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#1b1b1c', fontWeight: 500 }}>
                          {file.type === 'folder' ? <FolderFilled style={{ color: '#faad14', fontSize: '16px' }} /> : <FileTextOutlined style={{ color: '#64748b', fontSize: '16px' }} />}
                          {file.name}
                          {isSource && <span style={{ fontSize: '10px', backgroundColor: '#1677ff', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>SOURCE</span>}
                          {isTarget && <span style={{ fontSize: '10px', backgroundColor: '#16a34a', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>TARGET</span>}
                        </div>
                      </td>
                      <td style={{ padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#414755' }}>{file.size}</td>
                      <td style={{ padding: '12px', fontSize: '12px', color: '#414755' }}>{file.modifiedAt}</td>
                      <td style={{ padding: '12px', fontSize: '12px', color: '#414755' }}>{file.owner}</td>
                    </tr>
                  );
                })}
                {filteredFiles.length === 0 && !browseError && (
                  <tr>
                    <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: '#727786', fontStyle: 'italic', fontSize: '13px' }}>
                      No files or folders found in this directory.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
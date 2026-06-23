import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { Api, type CloudConnection, type CloudBrowseEntry, type GoogleCloudStorageConfig } from '../../../shared/api/Api';
import {
  getConnectionBrowsePath,
  isBrowsePathFresh,
  setConnectionBrowsePath,
} from '../browseCacheStorage';
import {
  FolderOutlined, FolderOpenOutlined, SearchOutlined, ArrowRightOutlined,
  FileTextOutlined, DeleteOutlined, CheckOutlined, CloudOutlined,
  FolderFilled, ArrowUpOutlined, SyncOutlined,
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
  createdBy: string;
  bucket?: string;
  connectionId?: string;
  rawModifiedAt: number; // ⚡ Added for sorting Date Modified accurately
}

type BrowseContext = {
  connectionId: string | null;
  bucket: string | null;
  prefix: string;
};

type BrowseCacheEntry = {
  entries: FileExplorerItem[];
  parentPrefix: string | null;
  error: string | null;
};

const browsePathId = (ctx: BrowseContext): string | null => {
  if (!ctx.connectionId || ctx.bucket == null) return null;
  return `${ctx.connectionId}:${ctx.bucket}:${ctx.prefix}`;
};

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

const toExplorerItem = (entry: CloudBrowseEntry): FileExplorerItem => ({
  id: entry.path,
  name: entry.name,
  objectName: entry.path,
  type: entry.is_dir ? 'folder' : 'file',
  size: entry.is_dir ? '—' : formatBytes(entry.size_bytes),
  sizeBytes: entry.size_bytes ?? null,
  createdAt: formatDate(entry.created_at),
  // ⚡ Added (entry as any) to bypass the TypeScript strict type check
  modifiedAt: formatDate(entry.updated_at || (entry as any).modified_at),
  owner: entry.owner?.trim() || '—',
  createdBy: entry.created_by?.trim() || '—',
  // ⚡ Added (entry as any) here as well
  rawModifiedAt: new Date(entry.updated_at || (entry as any).modified_at || 0).getTime(),
});

const envFallbackConnection = (): CloudConnection | null => {
  const id = import.meta.env.VITE_GCS_CONNECTION_ID as string | undefined;
  const bucket = import.meta.env.VITE_GCS_BUCKET as string | undefined;
  if (!id) return null;
  return { id, name: 'Configured GCS connection', provider: 'google-cloud-storage', bucket: bucket ?? '', project_id: null, active: true };
};

const folderPrefixFromObject = (objectName: string): string => {
  const slash = objectName.lastIndexOf('/');
  return slash >= 0 ? objectName.slice(0, slash + 1) : '';
};

const browseContextFromCloud = (
  cloud: { connection_id?: string | null; bucket?: string | null; object_name?: string | null } | null,
): BrowseContext => ({
  connectionId: cloud?.connection_id ?? null,
  bucket: cloud?.bucket ?? null,
  prefix: cloud?.object_name ? folderPrefixFromObject(cloud.object_name) : '',
});

const browseContextFromConnection = (conn: CloudConnection): BrowseContext => ({
  connectionId: conn.id,
  bucket: conn.bucket?.trim() ? conn.bucket : '',
  prefix: '',
});

const emptyBrowseContext = (): BrowseContext => ({
  connectionId: null,
  bucket: null,
  prefix: '',
});

const cloudObjectKey = (
  cloud: { connection_id?: string | null; bucket?: string | null; object_name?: string | null } | null,
): string => (cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '');

const initialSelectingFor = (
  sourceCloud: GoogleCloudStorageConfig | null,
  targetCloud: GoogleCloudStorageConfig | null,
): 'source' | 'target' | 'none' => {
  if (sourceCloud && targetCloud) return 'none';
  if (targetCloud && !sourceCloud) return 'target';
  return 'source';
};

const fileFromValidationCloud = (
  cloud: GoogleCloudStorageConfig,
  fileName: string | null,
  fileSize: number | null,
): FileExplorerItem => ({
  id: cloud.object_name,
  name: fileName || cloud.object_name.split('/').pop() || '',
  objectName: cloud.object_name,
  type: 'file',
  size: formatBytes(fileSize),
  sizeBytes: fileSize,
  bucket: cloud.bucket ?? undefined,
  connectionId: cloud.connection_id ?? undefined,
  createdAt: '—',
  modifiedAt: '—',
  owner: '—',
  createdBy: '—',
  rawModifiedAt: 0,
});

const SkeletonCell: React.FC<{ width?: string }> = ({ width = '100%' }) => (
  <div style={{ width, height: '14px', backgroundColor: '#e2e8f0', borderRadius: '4px', animation: 'browse-skeleton-pulse 1.5s ease-in-out infinite' }} />
);

const BrowseSkeletonRows: React.FC<{ rows?: number }> = ({ rows = 8 }) => (
  <>
    {Array.from({ length: rows }, (_, i) => (
      <tr key={`skeleton-${i}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
        <td style={{ padding: '12px' }}><SkeletonCell width="16px" /></td>
        <td style={{ padding: '12px' }}><SkeletonCell width={`${55 + (i % 3) * 12}%`} /></td>
        <td style={{ padding: '12px' }}><SkeletonCell width="64px" /></td>
        <td style={{ padding: '12px' }}><SkeletonCell width="96px" /></td>
        <td style={{ padding: '12px' }}><SkeletonCell width="96px" /></td>
        <td style={{ padding: '12px' }}><SkeletonCell width="80px" /></td>
        <td style={{ padding: '12px' }}><SkeletonCell width="72px" /></td>
      </tr>
    ))}
  </>
);

// ⚡ Custom component for long file names in the display cards
const TruncatableName: React.FC<{ text: string }> = ({ text }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <span
      title={text}
      onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
      style={{
        fontSize: '13px',
        fontWeight: 600,
        maxWidth: '180px',
        display: 'inline-block',
        whiteSpace: expanded ? 'normal' : 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        wordBreak: expanded ? 'break-all' : 'normal',
        verticalAlign: 'bottom',
        cursor: 'pointer'
      }}
    >
      {text}
    </span>
  );
};

export const FileSelectionStep: React.FC = () => {
  const dispatch = useAppDispatch();
  const validationForm = useAppSelector((s) => s.validation.validationForm);

  const [validationMode, setValidationMode] = useState('Single to Single (Default)');
  const [searchQuery, setSearchQuery] = useState('');

  // ⚡ New Sort State
  const [sortConfig, setSortConfig] = useState<{ key: 'name' | 'size' | 'modifiedAt'; direction: 'asc' | 'desc' } | null>(null);

  const [connections, setConnections] = useState<CloudConnection[]>([]);
  const [connectionsError, setConnectionsError] = useState<string | null>(null);

  const [browse, setBrowse] = useState<BrowseContext>(() =>
    validationForm.sourceCloud
      ? browseContextFromCloud(validationForm.sourceCloud)
      : emptyBrowseContext(),
  );
  const [parentPrefix, setParentPrefix] = useState<string | null>(null);
  const [browseEntries, setBrowseEntries] = useState<FileExplorerItem[]>([]);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const [loadingBrowseKey, setLoadingBrowseKey] = useState<string | null>(null);
  const browseRequestIdRef = useRef(0);

  const [selectingFor, setSelectingFor] = useState<'source' | 'target' | 'none'>(() =>
    initialSelectingFor(validationForm.sourceCloud, validationForm.targetCloud),
  );
  const [sourceFile, setSourceFile] = useState<FileExplorerItem | null>(() =>
    validationForm.sourceCloud
      ? fileFromValidationCloud(
        validationForm.sourceCloud,
        validationForm.sourceFileName,
        validationForm.sourceFileSize,
      )
      : null,
  );
  const [targetFile, setTargetFile] = useState<FileExplorerItem | null>(() =>
    validationForm.targetCloud
      ? fileFromValidationCloud(
        validationForm.targetCloud,
        validationForm.targetFileName,
        validationForm.targetFileSize,
      )
      : null,
  );

  const currentBrowsePathId = browsePathId(browse);
  const isBrowsing = loadingBrowseKey != null && loadingBrowseKey === currentBrowsePathId;

  // ⚡ Helper to wipe filters when changing environments
  const resetFilters = () => {
    setSearchQuery('');
    setSortConfig(null);
  };

  const readCachedSnapshot = useCallback((ctx: BrowseContext): BrowseCacheEntry | null => {
    if (!ctx.connectionId || ctx.bucket == null) return null;
    const cached = getConnectionBrowsePath(ctx.connectionId, ctx.bucket, ctx.prefix);
    if (!cached) return null;
    return {
      entries: cached.entries as FileExplorerItem[],
      parentPrefix: cached.parentPrefix,
      error: cached.error,
    };
  }, []);

  const persistSnapshot = useCallback((ctx: BrowseContext, snapshot: BrowseCacheEntry) => {
    if (!ctx.connectionId || ctx.bucket == null) return;
    setConnectionBrowsePath(ctx.connectionId, ctx.bucket, ctx.prefix, {
      entries: snapshot.entries,
      parentPrefix: snapshot.parentPrefix,
      error: snapshot.error,
    });
  }, []);

  const setActiveBrowse = useCallback((patch: Partial<BrowseContext>) => {
    setBrowse((prev) => ({ ...prev, ...patch }));
  }, []);

  const applyBrowseSnapshot = useCallback((ctx: BrowseContext | null) => {
    if (!ctx?.connectionId || ctx.bucket == null) {
      setBrowseEntries([]);
      setParentPrefix(null);
      setBrowseError(null);
      return;
    }
    const cached = readCachedSnapshot(ctx);
    if (cached) {
      setBrowseEntries(cached.entries);
      setParentPrefix(cached.parentPrefix);
      setBrowseError(cached.error);
      return;
    }
    setBrowseEntries([]);
    setParentPrefix(null);
    setBrowseError(null);
  }, [readCachedSnapshot]);

  const cancelInFlightBrowse = useCallback(() => {
    browseRequestIdRef.current += 1;
  }, []);

  const loadBrowse = useCallback((
    ctx: BrowseContext,
    pathId: string,
    requestId: number,
    options?: { background?: boolean },
  ) => {
    if (!ctx.connectionId || ctx.bucket == null) return;
    const connectionId = ctx.connectionId;

    if (!options?.background) {
      setLoadingBrowseKey(pathId);
    }

    Api.browseCloud({
      connection_id: connectionId,
      bucket: ctx.bucket.trim() ? ctx.bucket : null,
      prefix: ctx.prefix,
      file_format: 'csv',
    })
      .then((res) => {
        if (requestId !== browseRequestIdRef.current) return;
        const mappedEntries: FileExplorerItem[] = res.data.entries.map((entry) => ({
          ...toExplorerItem(entry),
          connectionId,
          bucket: res.data.bucket,
        }));
        const resolvedBucket = res.data.bucket || ctx.bucket || '';
        const cacheCtx: BrowseContext = { ...ctx, bucket: resolvedBucket };
        const snapshot: BrowseCacheEntry = {
          entries: mappedEntries,
          parentPrefix: res.data.parent_prefix,
          error: null,
        };
        persistSnapshot(cacheCtx, snapshot);
        if (resolvedBucket !== ctx.bucket) {
          setBrowse((prev) => ({ ...prev, bucket: resolvedBucket }));
        }
        setBrowseError(null);
        setParentPrefix(snapshot.parentPrefix);
        setBrowseEntries(snapshot.entries);
      })
      .catch(() => {
        if (requestId !== browseRequestIdRef.current) return;
        const resolvedBucket = ctx.bucket || '';
        const cacheCtx: BrowseContext = { ...ctx, bucket: resolvedBucket };
        const snapshot: BrowseCacheEntry = {
          entries: [],
          parentPrefix: null,
          error: 'Could not browse GCS bucket. Check connection credentials.',
        };
        persistSnapshot(cacheCtx, snapshot);
        setBrowseError(snapshot.error);
        setParentPrefix(null);
        setBrowseEntries([]);
      })
      .finally(() => {
        if (requestId === browseRequestIdRef.current) {
          setLoadingBrowseKey((prev) => (prev === pathId ? null : prev));
        }
      });
  }, [persistSnapshot]);

  useLayoutEffect(() => {
    if (!browse.connectionId || browse.bucket == null || !currentBrowsePathId) {
      setLoadingBrowseKey(null);
      applyBrowseSnapshot(null);
      return;
    }

    applyBrowseSnapshot(browse);
    const cached = getConnectionBrowsePath(
      browse.connectionId,
      browse.bucket,
      browse.prefix,
    );
    if (cached) {
      setLoadingBrowseKey(null);
      if (!isBrowsePathFresh(cached)) {
        const requestId = ++browseRequestIdRef.current;
        loadBrowse(browse, currentBrowsePathId, requestId, { background: true });
      }
      return;
    }

    const requestId = ++browseRequestIdRef.current;
    loadBrowse(browse, currentBrowsePathId, requestId);
  }, [
    browse.connectionId,
    browse.bucket,
    browse.prefix,
    currentBrowsePathId,
    loadBrowse,
    applyBrowseSnapshot,
  ]);

  const connectionName = (connectionId?: string) =>
    connections.find((c) => c.id === connectionId)?.name ?? 'Unknown connection';

  useEffect(() => {
    Api.listCloudConnections()
      .then((res) => {
        const active = res.data.filter((c) => c.active && c.provider === 'google-cloud-storage');
        setConnections(active);
        setConnectionsError(null);
        // ⚡ Intentionally removed logic that auto-selects the first bucket
      })
      .catch(() => {
        const fallback = envFallbackConnection();
        if (fallback) {
          setConnections([fallback]);
          // ⚡ Intentionally removed fallback auto-select logic
          setConnectionsError(null);
        } else {
          setConnectionsError('Sign in via Admin to load GCS connections, or set VITE_GCS_CONNECTION_ID.');
          setLoadingBrowseKey(null);
        }
      });
  }, []);

  useEffect(() => {
    const isStepFullyConfigured = Boolean(sourceFile && targetFile);
    dispatch(validationActions.setStep1Valid(isStepFullyConfigured));

    const makeCloudRef = (file: FileExplorerItem | null) =>
      file && file.connectionId
        ? { provider: 'google-cloud-storage' as const, connection_id: file.connectionId, bucket: file.bucket, object_name: file.objectName }
        : null;

    const nextSourceCloud = makeCloudRef(sourceFile);
    const nextTargetCloud = makeCloudRef(targetFile);

    // Wait until local state reflects a Redux-restored session before syncing outward.
    if (!sourceFile && validationForm.sourceCloud) return;
    if (!targetFile && validationForm.targetCloud) return;

    const nextSourceFileName = sourceFile?.name ?? null;
    const nextTargetFileName = targetFile?.name ?? null;
    const nextSourceFileSize = sourceFile?.sizeBytes ?? null;
    const nextTargetFileSize = targetFile?.sizeBytes ?? null;

    const hasChanges =
      cloudObjectKey(nextSourceCloud) !== cloudObjectKey(validationForm.sourceCloud) ||
      cloudObjectKey(nextTargetCloud) !== cloudObjectKey(validationForm.targetCloud) ||
      nextSourceFileName !== validationForm.sourceFileName ||
      nextTargetFileName !== validationForm.targetFileName ||
      nextSourceFileSize !== validationForm.sourceFileSize ||
      nextTargetFileSize !== validationForm.targetFileSize;

    if (!hasChanges) return;

    dispatch(validationActions.setValidationForm({
      sourceCloud: nextSourceCloud,
      targetCloud: nextTargetCloud,
      sourceFileName: nextSourceFileName,
      targetFileName: nextTargetFileName,
      sourceFileSize: nextSourceFileSize,
      targetFileSize: nextTargetFileSize,
    }));
  }, [
    sourceFile,
    targetFile,
    dispatch,
    validationForm.sourceCloud,
    validationForm.targetCloud,
    validationForm.sourceFileName,
    validationForm.targetFileName,
    validationForm.sourceFileSize,
    validationForm.targetFileSize,
  ]);

  const handleConnectionSelect = (conn: CloudConnection) => {
    resetFilters(); // ⚡ Wipe filters on connection change
    cancelInFlightBrowse();
    const next = browseContextFromConnection(conn);
    const nextPathId = browsePathId(next);
    applyBrowseSnapshot(next);
    if (nextPathId) {
      const cached = getConnectionBrowsePath(next.connectionId!, next.bucket, next.prefix);
      setLoadingBrowseKey(cached ? null : nextPathId);
    }
    setBrowse(next);
  };

  const handleSelectingFor = (side: 'source' | 'target') => {
    setSelectingFor(side);
  };

  const activeConnection = connections.find((c) => c.id === browse.connectionId) ?? null;
  const isMultiBucketConnection = Boolean(activeConnection && !activeConnection.bucket?.trim());
  const isFileTableLocked = isBrowsing;
  const showBrowseSkeleton = isBrowsing && browseEntries.length === 0 && !browseError;

  const handleRowClick = (file: FileExplorerItem) => {
    if (isFileTableLocked) return;

    if (file.type === 'folder') {
      cancelInFlightBrowse();
      if (!browse.bucket) {
        resetFilters(); // ⚡ Wipe filters when stepping into a new bucket
        setActiveBrowse({ bucket: file.objectName, prefix: '' });
        return;
      }
      setActiveBrowse({
        prefix: file.objectName.endsWith('/') ? file.objectName : `${file.objectName}/`,
      });
      return;
    }

    const isSource = sourceFile?.id === file.id;
    const isTarget = targetFile?.id === file.id;

    if (isSource && isTarget) {
      setTargetFile(null);
      setSelectingFor('target');
      return;
    } else if (isTarget) {
      setTargetFile(null);
      setSelectingFor('target');
      return;
    } else if (isSource) {
      setSourceFile(null);
      setSelectingFor('source');
      return;
    }

    if (sourceFile && targetFile) {
      return;
    }

    const isMultiMode = validationMode === 'Many to Many' || validationMode === 'Batch Comparison';
    if (selectingFor === 'source') {
      if (isMultiMode) return;
      setSourceFile(file);
      if (!targetFile) setSelectingFor('target');
      else setSelectingFor('none');
    } else if (selectingFor === 'target') {
      if (isMultiMode) return;
      setTargetFile(file);
      if (!sourceFile) setSelectingFor('source');
      else setSelectingFor('none');
    }
  };

  const handleSort = (key: 'name' | 'size' | 'modifiedAt') => {
    setSortConfig(prev => {
      if (prev && prev.key === key && prev.direction === 'asc') return { key, direction: 'desc' };
      return { key, direction: 'asc' };
    });
  };

  const SortIcon = ({ columnKey }: { columnKey: string }) => {
    if (sortConfig?.key !== columnKey) return <span style={{ color: '#c1c6d7', marginLeft: '4px', fontSize: '10px' }}>↕</span>;
    return <span style={{ color: '#234B5F', marginLeft: '4px', fontSize: '10px' }}>{sortConfig.direction === 'asc' ? '▲' : '▼'}</span>;
  };

  // ⚡ Integrated Search + Dynamic Sort applied sequentially
  const sortedAndFilteredFiles = useMemo(() => {
    let result = browseEntries.filter((f) =>
      f.name.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    if (sortConfig) {
      result.sort((a, b) => {
        // Keep folders at the top regardless of sort direction
        if (a.type === 'folder' && b.type === 'file') return -1;
        if (a.type === 'file' && b.type === 'folder') return 1;

        if (sortConfig.key === 'name') {
          return sortConfig.direction === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
        }
        if (sortConfig.key === 'size') {
          const sizeA = a.sizeBytes ?? -1;
          const sizeB = b.sizeBytes ?? -1;
          return sortConfig.direction === 'asc' ? sizeA - sizeB : sizeB - sizeA;
        }
        if (sortConfig.key === 'modifiedAt') {
          return sortConfig.direction === 'asc' ? a.rawModifiedAt - b.rawModifiedAt : b.rawModifiedAt - a.rawModifiedAt;
        }
        return 0;
      });
    }
    return result;
  }, [browseEntries, searchQuery, sortConfig]);

  const breadcrumb = !browse.bucket
    ? (isMultiBucketConnection ? 'Select a bucket' : 'Select a connection')
    : `gs://${browse.bucket}/${browse.prefix}`;

  const browsingForLabel = selectingFor === 'target' ? 'Target' : 'Source';
  const browsingForColor = selectingFor === 'target' ? '#234B5F' : '#234B5F';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '24px' }}>
      <style>{`@keyframes browse-skeleton-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }`}</style>
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
        <div onClick={() => handleSelectingFor('source')} style={{ flex: 1, padding: '16px', borderRadius: '8px', border: selectingFor === 'source' ? '2px solid #234B5F' : '1px dashed #727786', cursor: 'pointer' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#234B5F' }}>1. Source ({sourceFile ? 1 : 0})</span>
          {sourceFile ? (
            <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckOutlined style={{ color: '#234B5F' }} />
                {/* ⚡ Replaced plain name with truncatable component */}
                <TruncatableName text={sourceFile.name} />
                <button type="button" onClick={(e) => { e.stopPropagation(); setSourceFile(null); setSelectingFor('source'); }} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#ba1a1a' }}><DeleteOutlined /></button>
              </div>
              <span style={{ fontSize: '11px', color: '#64748b', paddingLeft: '22px' }}>
                {connectionName(sourceFile.connectionId)}
              </span>
              <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'var(--font-mono)', wordBreak: 'break-all', paddingLeft: '22px' }}>
                gs://{sourceFile.bucket}/{sourceFile.objectName}
              </span>
            </div>
          ) : (
            <p style={{ margin: '8px 0 0', fontSize: '14px', color: '#727786', fontStyle: 'italic' }}>Pick a GCS object from any connection…</p>
          )}
        </div>

        <ArrowRightOutlined style={{ fontSize: '24px', color: '#727786', alignSelf: 'center' }} />

        <div onClick={() => handleSelectingFor('target')} style={{ flex: 1, padding: '16px', borderRadius: '8px', border: selectingFor === 'target' ? '2px solid #234B5F' : '1px dashed #727786', cursor: 'pointer' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#234B5F' }}>2. Target ({targetFile ? 1 : 0})</span>
          {targetFile ? (
            <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckOutlined style={{ color: '#234B5F' }} />
                {/* ⚡ Replaced plain name with truncatable component */}
                <TruncatableName text={targetFile.name} />
                <button type="button" onClick={(e) => { e.stopPropagation(); setTargetFile(null); setSelectingFor('target'); }} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#ba1a1a' }}><DeleteOutlined /></button>
              </div>
              <span style={{ fontSize: '11px', color: '#64748b', paddingLeft: '22px' }}>
                {connectionName(targetFile.connectionId)}
              </span>
              <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'var(--font-mono)', wordBreak: 'break-all', paddingLeft: '22px' }}>
                gs://{targetFile.bucket}/{targetFile.objectName}
              </span>
            </div>
          ) : (
            <p style={{ margin: '8px 0 0', fontSize: '14px', color: '#727786', fontStyle: 'italic' }}>Pick a GCS object from any connection…</p>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '24px', height: '500px' }}>
        <div className="custom-scrollbar" style={{ gridColumn: 'span 3', backgroundColor: '#f8fafc', borderRadius: '12px', border: '1px solid #d9d9d9', overflowY: 'auto', padding: '12px', position: 'relative' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', padding: '10px 12px', fontWeight: 600, fontSize: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CloudOutlined /> GCS Connections
            </div>
            {isBrowsing && <SyncOutlined spin style={{ color: browsingForColor, fontSize: '14px' }} />}
          </div>
          <div style={{ fontSize: '11px', color: browsingForColor, fontWeight: 600, padding: '0 12px 8px' }}>
            Browsing for {browsingForLabel}
          </div>
          {connectionsError && (
            <p style={{ fontSize: '12px', color: '#ba1a1a', padding: '0 12px' }}>
              {connectionsError} <Link to="/admin" style={{ color: '#234B5F' }}>Sign in as admin</Link>
            </p>
          )}
          {connections.map((conn) => {
            const isActive = browse.connectionId === conn.id;
            const isSourceConn = sourceFile?.connectionId === conn.id;
            const isTargetConn = targetFile?.connectionId === conn.id;
            const isLoadingThis = isBrowsing && isActive;
            return (
              <button
                key={conn.id}
                type="button"
                onClick={() => handleConnectionSelect(conn)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', margin: '4px 0',
                  width: '100%', textAlign: 'left',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  backgroundColor: isActive ? '#e6f4ff' : 'transparent',
                  color: isActive ? '#234B5F' : '#414755',
                  border: isActive ? '1px solid #91caff' : '1px solid transparent',
                }}
              >
                {isLoadingThis ? (
                  <SyncOutlined spin style={{ color: browsingForColor, fontSize: '14px' }} />
                ) : (
                  <FolderOutlined />
                )}
                <div style={{ overflow: 'hidden', flex: 1 }}>
                  <div style={{ fontSize: '13px', fontWeight: isActive ? 700 : 500, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{conn.name}</div>
                  <div style={{ fontSize: '10px', color: '#727786', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {conn.bucket?.trim() ? `gs://${conn.bucket}` : 'All accessible buckets'}
                  </div>
                  {(isSourceConn || isTargetConn) && (
                    <div style={{ display: 'flex', gap: '4px', marginTop: '2px' }}>
                      {isSourceConn && <span style={{ fontSize: '9px', backgroundColor: '#234B5F', color: '#fff', padding: '1px 4px', borderRadius: '3px', fontWeight: 700 }}>SRC</span>}
                      {isTargetConn && <span style={{ fontSize: '9px', backgroundColor: '#234B5F', color: '#fff', padding: '1px 4px', borderRadius: '3px', fontWeight: 700 }}>TGT</span>}
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        <div style={{ gridColumn: 'span 9', display: 'flex', flexDirection: 'column', backgroundColor: 'white', borderRadius: '12px', border: '1px solid #d9d9d9', overflow: 'hidden', position: 'relative' }}>
          <div style={{ padding: '16px', borderBottom: '1px solid #d9d9d9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
              <FolderOpenOutlined />
              <span>{breadcrumb}</span>
              {isBrowsing && <SyncOutlined spin style={{ color: browsingForColor, fontSize: '14px' }} />}
              {parentPrefix != null && !isBrowsing && (
                <button type="button" onClick={() => { cancelInFlightBrowse(); setActiveBrowse({ prefix: parentPrefix }); }} style={{ marginLeft: '8px', border: 'none', background: '#f0f0f0', borderRadius: '4px', padding: '2px 8px', cursor: 'pointer', fontSize: '12px' }}><ArrowUpOutlined /> Up</button>
              )}
              {isMultiBucketConnection && browse.bucket && !browse.prefix && parentPrefix == null && !isBrowsing && (
                <button type="button" onClick={() => { cancelInFlightBrowse(); setActiveBrowse({ bucket: '' }); }} style={{ marginLeft: '8px', border: 'none', background: '#f0f0f0', borderRadius: '4px', padding: '2px 8px', cursor: 'pointer', fontSize: '12px' }}><ArrowUpOutlined /> Buckets</button>
              )}
            </div>
            <div style={{ position: 'relative' }}>
              <input type="text" placeholder="Search…" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} disabled={isBrowsing} style={{ padding: '6px 12px 6px 36px', borderRadius: '8px', border: '1px solid #d9d9d9', width: '200px', fontSize: '12px', opacity: isBrowsing ? 0.6 : 1 }} />
              <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            </div>
          </div>

          <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto', overflowX: 'auto' }}>
            {browseError && <p style={{ padding: '16px', color: '#ba1a1a', fontSize: '13px' }}>{browseError}</p>}
            <table style={{ width: '100%', borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', fontSize: '11px', textTransform: 'uppercase', color: '#727786' }}>
                <tr>
                  <th style={{ padding: '12px', width: 40, borderBottom: '1px solid #d9d9d9' }} />
                  {/* ⚡ Added Sortable Column Headers */}
                  <th onClick={() => handleSort('name')} style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9', cursor: 'pointer' }}>
                    Name <SortIcon columnKey="name" />
                  </th>
                  <th onClick={() => handleSort('size')} style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9', cursor: 'pointer' }}>
                    Size <SortIcon columnKey="size" />
                  </th>
                  <th onClick={() => handleSort('modifiedAt')} style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9', cursor: 'pointer' }}>
                    Date Modified <SortIcon columnKey="modifiedAt" />
                  </th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9' }}>Created At</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9' }}>Created By</th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #d9d9d9' }}>Owner</th>
                </tr>
              </thead>
              <tbody>
                {showBrowseSkeleton ? (
                  <BrowseSkeletonRows />
                ) : (
                  <>
                    {/* ⚡ Changed mapping to use the sorted array */}
                    {sortedAndFilteredFiles.map((file) => {
                      const isSource = sourceFile?.id === file.id && sourceFile?.connectionId === file.connectionId;
                      const isTarget = targetFile?.id === file.id && targetFile?.connectionId === file.connectionId;
                      const isSelected = isSource || isTarget;
                      const isDisabledFile = Boolean(sourceFile && targetFile && !isSelected && file.type === 'file');

                      return (
                        <tr
                          key={`${file.connectionId}-${file.id}`}
                          onClick={() => handleRowClick(file)}
                          style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: isSelected ? '#f0f8ff' : 'transparent', cursor: isDisabledFile ? 'not-allowed' : 'pointer', transition: 'background-color 0.2s', opacity: isDisabledFile ? 0.5 : 1 }}
                          onMouseEnter={(e) => { if (!isSelected && !isDisabledFile) e.currentTarget.style.backgroundColor = '#f8fafc'; }}
                          onMouseLeave={(e) => { if (!isSelected && !isDisabledFile) e.currentTarget.style.backgroundColor = 'transparent'; }}
                        >
                          <td style={{ padding: '12px' }}>{file.type === 'file' && <input type="checkbox" readOnly checked={isSelected} disabled={isDisabledFile} />}</td>
                          <td style={{ padding: '12px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#1b1b1c', fontWeight: 500 }}>
                              {file.type === 'folder' ? <FolderFilled style={{ color: '#faad14', fontSize: '16px' }} /> : <FileTextOutlined style={{ color: '#64748b', fontSize: '16px' }} />}
                              {file.name}
                              {isSource && <span style={{ fontSize: '10px', backgroundColor: '#234B5F', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>SOURCE</span>}
                              {isTarget && <span style={{ fontSize: '10px', backgroundColor: '#234B5F', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>TARGET</span>}
                            </div>
                          </td>
                          <td style={{ padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#414755' }}>{file.size}</td>
                          <td style={{ padding: '12px', fontSize: '12px', color: '#414755' }}>{file.modifiedAt}</td>
                          <td style={{ padding: '12px', fontSize: '12px', color: '#414755' }}>{file.createdAt}</td>
                          <td style={{ padding: '12px', fontSize: '12px', color: '#414755' }}>{file.createdBy}</td>
                          <td style={{ padding: '12px', fontSize: '12px', color: '#414755' }}>{file.owner}</td>
                        </tr>
                      );
                    })}
                    {sortedAndFilteredFiles.length === 0 && !browseError && (
                      <tr>
                        <td colSpan={7} style={{ padding: '32px', textAlign: 'center', color: '#727786', fontStyle: 'italic', fontSize: '13px' }}>
                          No files or folders found in this directory.
                        </td>
                      </tr>
                    )}
                  </>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
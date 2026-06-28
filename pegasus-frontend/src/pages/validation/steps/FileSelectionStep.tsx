import React, { useState, useEffect, useLayoutEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { CloudConnection, CloudBrowseEntry, GoogleCloudStorageConfig } from '../../../shared/api/Api';
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
import styles from './FileSelectionStep.module.scss';

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

const stripGcsUserPrefix = (value: string | null | undefined): string => {
  const text = value?.trim();
  if (!text) return '—';
  const stripped = text.replace(/^user-/i, '');
  return stripped || '—';
};

const toExplorerItem = (entry: CloudBrowseEntry): FileExplorerItem => ({
  id: entry.path,
  name: entry.name,
  objectName: entry.path,
  type: entry.is_dir ? 'folder' : 'file',
  size: entry.is_dir ? '—' : formatBytes(entry.size_bytes),
  sizeBytes: entry.size_bytes ?? null,
  createdAt: formatDate(entry.created_at),
  modifiedAt: formatDate(entry.updated_at || entry.modified_at),
  owner: stripGcsUserPrefix(entry.owner),
  createdBy: stripGcsUserPrefix(entry.created_by),
  rawModifiedAt: new Date(entry.updated_at || entry.modified_at || 0).getTime(),
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

const SKELETON_NAME_WIDTHS = [styles.skeletonW55, styles.skeletonW67, styles.skeletonW79];

const SkeletonCell: React.FC<{ widthClass: string }> = ({ widthClass }) => (
  <div className={`${styles.skeleton} ${widthClass}`} />
);

const BrowseSkeletonRows: React.FC<{ rows?: number }> = ({ rows = 8 }) => (
  <>
    {Array.from({ length: rows }, (_, i) => (
      <tr key={`skeleton-${i}`} className={styles.skeletonRow}>
        <td className={styles.td}><SkeletonCell widthClass={styles.skeletonW16} /></td>
        <td className={styles.td}><SkeletonCell widthClass={SKELETON_NAME_WIDTHS[i % SKELETON_NAME_WIDTHS.length]} /></td>
        <td className={styles.td}><SkeletonCell widthClass={styles.skeletonW64} /></td>
        <td className={styles.td}><SkeletonCell widthClass={styles.skeletonW96} /></td>
        <td className={styles.td}><SkeletonCell widthClass={styles.skeletonW96} /></td>
        <td className={styles.td}><SkeletonCell widthClass={styles.skeletonW80} /></td>
        <td className={styles.td}><SkeletonCell widthClass={styles.skeletonW72} /></td>
      </tr>
    ))}
  </>
);

const MAX_DISPLAY_NAME_LENGTH = 30;

const truncateWithEllipsis = (text: string, maxLength = MAX_DISPLAY_NAME_LENGTH): string => {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
};

const TruncatableName: React.FC<{ text: string; maxLength?: number; className?: string }> = ({
  text,
  maxLength = MAX_DISPLAY_NAME_LENGTH,
  className,
}) => {
  const display = truncateWithEllipsis(text, maxLength);
  const isTruncated = display !== text;
  return (
    <span title={isTruncated ? text : undefined} className={className}>
      {display}
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
  const browseCloudState = useAppSelector((state) => state.validation.browseCloudState);
  const cloudConnectionsState = useAppSelector((state) => state.validation.cloudConnectionsState);

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

  const loadBrowse = useCallback((
    ctx: BrowseContext,
    pathId: string,
    options?: { background?: boolean },
  ) => {
    if (!ctx.connectionId || ctx.bucket == null) return;

    if (!options?.background) {
      setLoadingBrowseKey(pathId);
    }

    dispatch(validationActions.browseCloudRequest({
      pathId,
      connectionId: ctx.connectionId,
      bucket: ctx.bucket,
      prefix: ctx.prefix,
      background: options?.background,
    }));
  }, [dispatch]);

  useEffect(() => {
    if (!browse.connectionId || browse.bucket == null || !currentBrowsePathId) return;
    if (browseCloudState.pathId !== currentBrowsePathId) return;

    if (browseCloudState.data) {
      const res = browseCloudState.data;
      const connectionId = browseCloudState.connectionId ?? browse.connectionId;
      const mappedEntries: FileExplorerItem[] = res.entries.map((entry) => ({
        ...toExplorerItem(entry),
        connectionId,
        bucket: res.bucket,
      }));
      const resolvedBucket = res.bucket || browse.bucket || '';
      const cacheCtx: BrowseContext = { ...browse, bucket: resolvedBucket };
      const snapshot: BrowseCacheEntry = {
        entries: mappedEntries,
        parentPrefix: res.parent_prefix,
        error: null,
      };
      persistSnapshot(cacheCtx, snapshot);
      if (resolvedBucket !== browse.bucket) {
        setBrowse((prev) => ({ ...prev, bucket: resolvedBucket }));
      }
      setBrowseError(null);
      setParentPrefix(snapshot.parentPrefix);
      setBrowseEntries(snapshot.entries);
      setLoadingBrowseKey(null);
    }

    if (browseCloudState.error) {
      const resolvedBucket = browse.bucket || '';
      const cacheCtx: BrowseContext = { ...browse, bucket: resolvedBucket };
      const snapshot: BrowseCacheEntry = {
        entries: [],
        parentPrefix: null,
        error: browseCloudState.error,
      };
      persistSnapshot(cacheCtx, snapshot);
      setBrowseError(snapshot.error);
      setParentPrefix(null);
      setBrowseEntries([]);
      setLoadingBrowseKey(null);
    }
  }, [browseCloudState, currentBrowsePathId, browse, persistSnapshot]);

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
        loadBrowse(browse, currentBrowsePathId, { background: true });
      }
      return;
    }

    loadBrowse(browse, currentBrowsePathId);
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
    dispatch(validationActions.listCloudConnectionsRequest());
  }, [dispatch]);

  useEffect(() => {
    if (!cloudConnectionsState.data) return;
    const active = cloudConnectionsState.data.filter((c) => c.active && c.provider === 'google-cloud-storage');
    setConnections(active);
    setConnectionsError(null);
  }, [cloudConnectionsState.data]);

  useEffect(() => {
    if (!cloudConnectionsState.error) return;
    const fallback = envFallbackConnection();
    if (fallback) {
      setConnections([fallback]);
      setConnectionsError(null);
    } else {
      setConnectionsError('Sign in via Admin to load GCS connections, or set VITE_GCS_CONNECTION_ID.');
      setLoadingBrowseKey(null);
    }
  }, [cloudConnectionsState.error]);

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
    resetFilters();
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
    if (sortConfig?.key !== columnKey) return <span className={styles.sortIconInactive}>↕</span>;
    return <span className={styles.sortIconActive}>{sortConfig.direction === 'asc' ? '▲' : '▼'}</span>;
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

  return (
    <div className={styles.page}>
      <div>
        <label className={styles.fieldLabel}>Validation Pattern</label>
        <select
          value={validationMode}
          onChange={(e) => {
            setValidationMode(e.target.value); setSourceFile(null); setTargetFile(null); setSelectingFor('source');
          }}
          className={styles.patternSelect}
        >
          <option>Single to Single (Default)</option><option>Many to Many</option><option>Batch Comparison</option>
        </select>
      </div>

      <div className={styles.selectionRow}>
        <div
          onClick={() => handleSelectingFor('source')}
          className={`${styles.selectionCard} ${selectingFor === 'source' ? styles.selectionCardActive : ''}`}
        >
          <span className={styles.selectionTitle}>1. Source ({sourceFile ? 1 : 0})</span>
          {sourceFile ? (
            <div className={styles.selectionContent}>
              <div className={styles.selectionFileRow}>
                <CheckOutlined className={styles.checkIcon} />
                <TruncatableName text={sourceFile.name} className={styles.fileName} />
                <button type="button" onClick={(e) => { e.stopPropagation(); setSourceFile(null); setSelectingFor('source'); }} className={styles.removeBtn}><DeleteOutlined /></button>
              </div>
              <span className={styles.fileMeta}>
                {connectionName(sourceFile.connectionId)}
              </span>
              <span className={styles.filePath}>
                gs://{sourceFile.bucket}/{sourceFile.objectName}
              </span>
            </div>
          ) : (
            <p className={styles.selectionPlaceholder}>Pick a GCS object from any connection…</p>
          )}
        </div>

        <ArrowRightOutlined className={styles.arrowIcon} />

        <div
          onClick={() => handleSelectingFor('target')}
          className={`${styles.selectionCard} ${selectingFor === 'target' ? styles.selectionCardActive : ''}`}
        >
          <span className={styles.selectionTitle}>2. Target ({targetFile ? 1 : 0})</span>
          {targetFile ? (
            <div className={styles.selectionContent}>
              <div className={styles.selectionFileRow}>
                <CheckOutlined className={styles.checkIcon} />
                <TruncatableName text={targetFile.name} className={styles.fileName} />
                <button type="button" onClick={(e) => { e.stopPropagation(); setTargetFile(null); setSelectingFor('target'); }} className={styles.removeBtn}><DeleteOutlined /></button>
              </div>
              <span className={styles.fileMeta}>
                {connectionName(targetFile.connectionId)}
              </span>
              <span className={styles.filePath}>
                gs://{targetFile.bucket}/{targetFile.objectName}
              </span>
            </div>
          ) : (
            <p className={styles.selectionPlaceholder}>Pick a GCS object from any connection…</p>
          )}
        </div>
      </div>

      <div className={styles.grid}>
        <div className={`custom-scrollbar ${styles.sidebar}`}>
          <div className={styles.sidebarHeader}>
            <div className={styles.sidebarHeaderLeft}>
              <CloudOutlined /> GCS Connections
            </div>
            {isBrowsing && <SyncOutlined spin className={styles.syncIcon} />}
          </div>
          <div className={styles.browsingLabel}>
            Browsing for {browsingForLabel}
          </div>
          {connectionsError && (
            <p className={styles.connectionsError}>
              {connectionsError} <Link to="/admin" className={styles.adminLink}>Sign in as admin</Link>
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
                className={`${styles.connBtn} ${isActive ? styles.connBtnActive : ''}`}
              >
                {isLoadingThis ? (
                  <SyncOutlined spin className={styles.syncIcon} />
                ) : (
                  <FolderOutlined />
                )}
                <div className={styles.connInfo}>
                  <div className={`${styles.connName} ${isActive ? styles.connNameActive : ''}`}>{conn.name}</div>
                  <div className={styles.connBucket}>
                    {conn.bucket?.trim() ? `gs://${conn.bucket}` : 'All accessible buckets'}
                  </div>
                  {(isSourceConn || isTargetConn) && (
                    <div className={styles.roleBadges}>
                      {isSourceConn && <span className={styles.roleBadge}>SRC</span>}
                      {isTargetConn && <span className={styles.roleBadge}>TGT</span>}
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        <div className={styles.mainPanel}>
          <div className={styles.panelHeader}>
            <div className={styles.breadcrumb}>
              <FolderOpenOutlined />
              <span title={breadcrumb.length > MAX_DISPLAY_NAME_LENGTH ? breadcrumb : undefined}>
                {truncateWithEllipsis(breadcrumb)}
              </span>
              {isBrowsing && <SyncOutlined spin className={styles.syncIcon} />}
              {parentPrefix != null && !isBrowsing && (
                <button type="button" onClick={() => { setActiveBrowse({ prefix: parentPrefix }); }} className={styles.navBtn}><ArrowUpOutlined /> Back</button>
              )}
              {isMultiBucketConnection && browse.bucket && !browse.prefix && parentPrefix == null && !isBrowsing && (
                <button type="button" onClick={() => { setActiveBrowse({ bucket: '' }); }} className={styles.navBtn}><ArrowUpOutlined /> Buckets</button>
              )}
            </div>
            <div className={styles.searchWrap}>
              <input
                type="text"
                placeholder="Search…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                disabled={isBrowsing}
                className={`${styles.searchInput} ${isBrowsing ? styles.searchInputDisabled : ''}`}
              />
              <SearchOutlined className={styles.searchIcon} />
            </div>
          </div>

          <div className={`custom-scrollbar ${styles.tableScroll}`}>
            {browseError && <p className={styles.browseError}>{browseError}</p>}
            <table className={styles.table}>
              <thead className={styles.thead}>
                <tr>
                  <th className={`${styles.th} ${styles.thIcon}`} />
                  <th onClick={() => handleSort('name')} className={`${styles.th} ${styles.thName} ${styles.thSortable}`}>
                    Name <SortIcon columnKey="name" />
                  </th>
                  <th onClick={() => handleSort('size')} className={`${styles.th} ${styles.thSortable}`}>
                    Size <SortIcon columnKey="size" />
                  </th>
                  <th onClick={() => handleSort('modifiedAt')} className={`${styles.th} ${styles.thSortable}`}>
                    Date Modified <SortIcon columnKey="modifiedAt" />
                  </th>
                  <th className={styles.th}>Created At</th>
                  <th className={styles.th}>Created By</th>
                  <th className={styles.th}>Owner</th>
                </tr>
              </thead>
              <tbody>
                {showBrowseSkeleton ? (
                  <BrowseSkeletonRows />
                ) : (
                  <>
                    {sortedAndFilteredFiles.map((file) => {
                      const isSource = sourceFile?.id === file.id && sourceFile?.connectionId === file.connectionId;
                      const isTarget = targetFile?.id === file.id && targetFile?.connectionId === file.connectionId;
                      const isSelected = isSource || isTarget;
                      const isDisabledFile = Boolean(sourceFile && targetFile && !isSelected && file.type === 'file');

                      return (
                        <tr
                          key={`${file.connectionId}-${file.id}`}
                          onClick={() => handleRowClick(file)}
                          className={`${styles.dataRow} ${isSelected ? styles.dataRowSelected : ''} ${isDisabledFile ? styles.dataRowDisabled : ''}`}
                        >
                          <td className={styles.td}>{file.type === 'file' && <input type="checkbox" readOnly checked={isSelected} disabled={isDisabledFile} />}</td>
                          <td className={`${styles.td} ${styles.tdOverflow}`}>
                            <div className={styles.fileCell}>
                              {file.type === 'folder' ? <FolderFilled className={styles.folderIcon} /> : <FileTextOutlined className={styles.fileIcon} />}
                              <TruncatableName text={file.name} className={styles.fileNameInherit} />
                              {isSource && <span className={styles.selectionTag}>SOURCE</span>}
                              {isTarget && <span className={styles.selectionTag}>TARGET</span>}
                            </div>
                          </td>
                          <td className={`${styles.td} ${styles.cellMono}`}>{file.size}</td>
                          <td className={`${styles.td} ${styles.cellText}`}>{file.modifiedAt}</td>
                          <td className={`${styles.td} ${styles.cellText}`}>{file.createdAt}</td>
                          <td className={`${styles.td} ${styles.cellText}`}>{file.createdBy}</td>
                          <td className={`${styles.td} ${styles.cellText}`}>{file.owner}</td>
                        </tr>
                      );
                    })}
                    {sortedAndFilteredFiles.length === 0 && !browseError && (
                      <tr>
                        <td colSpan={7} className={styles.emptyCell}>
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
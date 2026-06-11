import React, { useEffect } from 'react';
import {
  DatabaseOutlined, FileTextOutlined, ArrowRightOutlined,
  CheckCircleFilled, WarningFilled, ProfileOutlined,
  HddOutlined, TableOutlined, BarcodeOutlined
} from '@ant-design/icons';

import { Api, type CloudFileProfileResponse, type GoogleCloudStorageConfig } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';

const formatBytes = (bytes: number | null) => {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const formatCount = (value: number | null | undefined, loading: boolean) => {
  if (loading) return '…';
  if (value == null) return '—';
  return value.toLocaleString();
};

const gsPath = (bucket: string | null, objectName: string | null) =>
  bucket && objectName ? `gs://${bucket}/${objectName}` : '—';

const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string =>
  cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

type FileProfileState = {
  profile: CloudFileProfileResponse | null;
  loading: boolean;
  error: boolean;
};

const emptyProfileState: FileProfileState = { profile: null, loading: false, error: false };

export const MappingOverviewStep: React.FC = () => {
  const dispatch = useAppDispatch();
  const form = useAppSelector((s) => s.validation.validationForm);
  const cache = useAppSelector((s) => s.validation.overviewProfileCache);

  const sourceKey = cloudObjectKey(form.sourceCloud);
  const targetKey = cloudObjectKey(form.targetCloud);
  const cacheHit = cache?.sourceKey === sourceKey && cache?.targetKey === targetKey;

  const sourceProfile: FileProfileState = !form.sourceCloud
    ? emptyProfileState
    : cacheHit
      ? { profile: cache.source, loading: false, error: cache.sourceError }
      : { profile: null, loading: true, error: false };

  const targetProfile: FileProfileState = !form.targetCloud
    ? emptyProfileState
    : cacheHit
      ? { profile: cache.target, loading: false, error: cache.targetError }
      : { profile: null, loading: true, error: false };

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey || cacheHit) return;

    let cancelled = false;
    const nextCache = {
      sourceKey,
      targetKey,
      source: null as CloudFileProfileResponse | null,
      target: null as CloudFileProfileResponse | null,
      sourceError: false,
      targetError: false,
    };

    const commit = () => {
      if (!cancelled) dispatch(validationActions.setOverviewProfileCache({ ...nextCache }));
    };

    Promise.all([
      Api.profileCloudFile({ cloud: form.sourceCloud, delimiter: form.delimiter || 'auto' }),
      Api.profileCloudFile({ cloud: form.targetCloud, delimiter: form.delimiter || 'auto' }),
    ])
      .then(([sourceRes, targetRes]) => {
        nextCache.source = sourceRes.data;
        nextCache.target = targetRes.data;
        commit();
      })
      .catch(() => {
        nextCache.sourceError = true;
        nextCache.targetError = true;
        commit();
      });

    return () => { cancelled = true; };
  }, [form.sourceCloud, form.targetCloud, sourceKey, targetKey, cacheHit, dispatch, form.delimiter]);

  const sourceStats = {
    name: form.sourceFileName ?? '—',
    path: gsPath(form.bucket, form.sourceCloud?.object_name ?? null),
    format: sourceProfile.loading
      ? '…'
      : sourceProfile.error
        ? '—'
        : sourceProfile.profile?.file_format ?? '—',
    sizeBytes: sourceProfile.profile?.file_size_bytes ?? form.sourceFileSize,
    columnCount: sourceProfile.profile?.column_count ?? null,
    rowCount: sourceProfile.profile?.row_count ?? null,
    loading: sourceProfile.loading,
  };

  const targetStats = {
    name: form.targetFileName ?? '—',
    path: gsPath(form.bucket, form.targetCloud?.object_name ?? null),
    format: targetProfile.loading
      ? '…'
      : targetProfile.error
        ? '—'
        : targetProfile.profile?.file_format ?? '—',
    sizeBytes: targetProfile.profile?.file_size_bytes ?? form.targetFileSize,
    columnCount: targetProfile.profile?.column_count ?? null,
    rowCount: targetProfile.profile?.row_count ?? null,
    loading: targetProfile.loading,
  };

  const runComparison = () => {
    if (!form.sourceCloud || !form.targetCloud) {
      return {
        status: 'warning' as const,
        title: 'Files not selected',
        message: 'Select source and target GCS objects in step 1.',
        mismatches: { size: false, columns: false, rows: false },
      };
    }
    if (sourceProfile.loading || targetProfile.loading) {
      return {
        status: 'warning' as const,
        title: 'Analyzing files',
        message: 'Detecting format and counting rows/columns…',
        mismatches: { size: false, columns: false, rows: false },
      };
    }
    const sizeDiff =
      sourceStats.sizeBytes && targetStats.sizeBytes
        ? Math.abs(sourceStats.sizeBytes - targetStats.sizeBytes) / sourceStats.sizeBytes
        : 0;
    const columnMismatch =
      sourceStats.columnCount != null &&
      targetStats.columnCount != null &&
      sourceStats.columnCount !== targetStats.columnCount;
    const rowMismatch =
      sourceStats.rowCount != null &&
      targetStats.rowCount != null &&
      sourceStats.rowCount !== targetStats.rowCount;
    const mismatches = {
      size: sizeDiff > 0.2,
      columns: columnMismatch,
      rows: rowMismatch,
    };
    if (mismatches.columns) {
      return {
        status: 'warning' as const,
        title: 'Column count mismatch',
        message: `Source has ${sourceStats.columnCount?.toLocaleString()} columns; target has ${targetStats.columnCount?.toLocaleString()}.`,
        mismatches,
      };
    }
    if (mismatches.rows) {
      return {
        status: 'warning' as const,
        title: 'Row count mismatch',
        message: `Source has ${sourceStats.rowCount?.toLocaleString()} rows; target has ${targetStats.rowCount?.toLocaleString()}.`,
        mismatches,
      };
    }
    if (mismatches.size) {
      return {
        status: 'warning' as const,
        title: 'Size mismatch',
        message: 'Source and target object sizes differ by more than 20%.',
        mismatches,
      };
    }
    return {
      status: 'success' as const,
      title: 'Ready for mapping',
      message: 'GCS source and target objects are selected.',
      mismatches,
    };
  };

  const alert = runComparison();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px' }}>
        <FileCard label="Source" color="#1677ff" stats={sourceStats} warn={alert.mismatches} />
        <ArrowRightOutlined style={{ fontSize: '20px', color: '#727786' }} />
        <FileCard label="Target" color="#16a34a" icon={<DatabaseOutlined />} stats={targetStats} warn={alert.mismatches} />
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px 20px', borderRadius: '8px', backgroundColor: alert.status === 'success' ? '#f0fdf4' : '#fffbeb', border: `1px solid ${alert.status === 'success' ? '#bbf7d0' : '#fde68a'}` }}>
        {alert.status === 'success' ? (
          <CheckCircleFilled style={{ color: '#16a34a', fontSize: '20px' }} />
        ) : (
          <WarningFilled style={{ color: '#d97706', fontSize: '20px' }} />
        )}
        <div>
          <h5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700 }}>{alert.title}</h5>
          <p style={{ margin: 0, fontSize: '13px' }}>{alert.message}</p>
        </div>
      </div>
    </div>
  );
};

const FileCard: React.FC<{
  label: string;
  color: string;
  stats: {
    name: string;
    path: string;
    format: string;
    sizeBytes: number | null;
    columnCount: number | null;
    rowCount: number | null;
    loading: boolean;
  };
  warn: { size: boolean; columns: boolean; rows: boolean };
  icon?: React.ReactNode;
}> = ({ label, color, stats, warn, icon }) => (
  <div style={{ flex: 1, backgroundColor: '#fff', border: '1px solid #d9d9d9', borderRadius: '12px', padding: '24px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color }}>
      {icon ?? <FileTextOutlined />}
      <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase' }}>{label}</span>
    </div>
    <h4 style={{ margin: '0 0 4px 0', fontSize: '18px' }}>{stats.name}</h4>
    <p style={{ fontSize: '12px', color: '#727786', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{stats.path}</p>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
      <Row icon={<ProfileOutlined />} label="Format" value={stats.format} />
      <Row icon={<HddOutlined />} label="Size" value={formatBytes(stats.sizeBytes)} warn={warn.size} />
      <Row icon={<TableOutlined />} label="Columns" value={formatCount(stats.columnCount, stats.loading)} warn={warn.columns} />
      <Row icon={<BarcodeOutlined />} label="Rows" value={formatCount(stats.rowCount, stats.loading)} warn={warn.rows} />
    </div>
  </div>
);

const Row: React.FC<{ icon: React.ReactNode; label: string; value: string; warn?: boolean }> = ({ icon, label, value, warn }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
    <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}>{icon} {label}</span>
    <span style={{ fontSize: '13px', fontWeight: 600, color: warn ? '#ba1a1a' : '#1b1b1c' }}>{value}</span>
  </div>
);

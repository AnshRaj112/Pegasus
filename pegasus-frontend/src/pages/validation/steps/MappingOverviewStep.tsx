import React, { useCallback, useEffect, useState } from 'react';
import {
  DatabaseOutlined, FileTextOutlined, ArrowRightOutlined,
  CheckCircleFilled, WarningFilled, CloseCircleFilled, ProfileOutlined,
  HddOutlined, TableOutlined, BarcodeOutlined, BuildOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { CloudFileProfileResponse, FixedWidthColumnPreview, GoogleCloudStorageConfig } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { OverviewFilePreview } from './OverviewFilePreview';
import { OverviewJsonPreview } from './OverviewJsonPreview';
import { assessEmptyValidationFiles, isValidationFileEmpty } from '../validationEmptyFiles';
import { isFixedWidthFormat } from '../fixedWidthFormat';
import { isJsonFileName, profileLooksJson } from '../jsonFormat';
import { profileLooksArchive, resolveWizardArchiveMode, archiveKindFromProfile, archiveUsesTabularValidation } from '../archiveFormat';
import { FixedWidthLayoutPanel } from './FixedWidthLayoutPanel';
import { formatDetectionLabel, resolveArchiveFormatChain } from '../../../shared/formatDisplayLabel';
import { FormatDetectionChainLabel } from '../../../shared/FormatDetectionChainLabel';
import styles from './MappingOverviewStep.module.scss';

const formatBytes = (bytes: number | null) => {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const formatCount = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString();
const gsPath = (bucket: string | null, objectName: string | null) => bucket && objectName ? `gs://${bucket}/${objectName}` : '—';
const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string => cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

const formatBoolean = (val: boolean | null | undefined) => {
  if (val === true) return 'Yes';
  if (val === false) return 'No';
  return '—';
};

const resolveCloudFormatRaw = (
  profile: CloudFileProfileResponse | null,
  fileName: string | null,
  objectName: string | null | undefined,
  empty: boolean,
): string | null => {
  if (empty) return 'empty';
  const outer = archiveKindFromProfile(profile) ?? undefined;
  const fromArchive = resolveArchiveFormatChain({
    fileFormat: profile?.file_format,
    suggestedFormat: profile?.suggested_file_format,
    objectName: objectName ?? fileName,
    archiveEntriesSample: profile?.archive_entries_sample,
    outer,
  });
  if (fromArchive) return fromArchive;
  if (isJsonFileName(fileName)) return 'json';
  return null;
};

type FileProfileState = { profile: CloudFileProfileResponse | null; loading: boolean; error: boolean; };
const emptyProfileState: FileProfileState = { profile: null, loading: false, error: false };

type SkeletonSize = 'w36' | 'w48' | 'w60' | 'w90' | 'h16' | 'h24' | 'h32';

const skeletonSizeClass: Record<SkeletonSize, string> = {
  w36: styles.skeletonW36,
  w48: styles.skeletonW48,
  w60: styles.skeletonW60,
  w90: styles.skeletonW90,
  h16: styles.skeletonH16,
  h24: styles.skeletonH24,
  h32: styles.skeletonH32,
};

const SkeletonBlock: React.FC<{ sizes: SkeletonSize[] }> = ({ sizes }) => (
  <div className={`${styles.skeleton} ${sizes.map((size) => skeletonSizeClass[size]).join(' ')}`} />
);

const PreviewButton: React.FC<{ onClick: () => void; disabled?: boolean }> = ({ onClick, disabled }) => (
  <button
    type="button"
    disabled={disabled}
    onClick={onClick}
    className={styles.previewBtn}
  >
    <EyeOutlined className={styles.previewBtnIcon} />
  </button>
);

const FileCard: React.FC<{
  label: string;
  stats: {
    name: string;
    path: string;
    format: React.ReactNode;
    sizeBytes: number | null;
    columnCount: number | null;
    rowCount: number | null;
    header: string;
    footer: string;
    preview: React.ReactNode;
  };
  warn: { size: boolean; columns: boolean; rows: boolean };
  loading: boolean;
  icon?: React.ReactNode;
  isEmpty?: boolean;
}> = ({ label, stats, warn, loading, icon, isEmpty }) => (
  <div className={`${styles.fileCard} ${isEmpty ? styles.fileCardEmpty : ''}`}>
    <div className={styles.fileCardHeader}>
      {icon ?? <FileTextOutlined />}
      <span className={styles.fileCardLabel}>{label}</span>
    </div>

    <h4 className={`${styles.fileCardName} ${isEmpty ? styles.fileCardNameEmpty : ''}`}>
      {loading ? <SkeletonBlock sizes={['w60', 'h24']} /> : stats.name}
    </h4>
    <div className={styles.fileCardPath}>
      {loading ? <SkeletonBlock sizes={['w90', 'h16']} /> : stats.path}
    </div>

    <div className={styles.fileCardStats}>
      <Row icon={<ProfileOutlined />} label="Format" value={isEmpty ? 'Empty' : stats.format} loading={loading} warn={isEmpty} />
      <Row icon={<HddOutlined />} label="Size" value={formatBytes(stats.sizeBytes)} warn={warn.size || isEmpty} loading={loading} />
      <Row icon={<TableOutlined />} label="Columns" value={formatCount(stats.columnCount)} warn={warn.columns} loading={loading} />
      <Row icon={<BarcodeOutlined />} label="Rows" value={isEmpty ? '0 (empty)' : formatCount(stats.rowCount)} warn={warn.rows || isEmpty} loading={loading} />
      <Row icon={<BuildOutlined />} label="Header" value={stats.header} loading={loading} />
      <Row icon={<BuildOutlined />} label="Footer" value={stats.footer} loading={loading} />
      <Row icon={<EyeOutlined />} label="Preview" value={stats.preview} loading={loading} isNode />
    </div>
  </div>
);

const Row: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  warn?: boolean;
  loading: boolean;
  isNode?: boolean;
}> = ({ icon, label, value, warn, loading, isNode }) => (
  <div className={styles.statRow}>
    <span className={styles.statLabel}>{icon} {label}</span>
    <span className={`${styles.statValue} ${warn ? styles.statValueWarn : ''}`}>
      {loading && !isNode ? <SkeletonBlock sizes={['w48', 'h16']} /> : value}
    </span>
  </div>
);

export const MappingOverviewStep: React.FC = () => {
  const dispatch = useAppDispatch();
  const form = useAppSelector((s) => s.validation.validationForm);
  const cache = useAppSelector((s) => s.validation.overviewProfileCache);
  const previewColumnsState = useAppSelector((s) => s.validation.previewColumnsState);
  const previewFixedWidthState = useAppSelector((s) => s.validation.previewFixedWidthState);

  const [previewOpen, setPreviewOpen] = useState(false);

  const sourceKey = cloudObjectKey(form.sourceCloud);
  const targetKey = cloudObjectKey(form.targetCloud);
  const previewPairKey = `${sourceKey}|${targetKey}|${form.uidColumn || 'id'}|${form.delimiter || 'auto'}|${form.hasHeader}`;
  const fixedWidthPairKey = `${sourceKey}|${targetKey}|${form.uidColumn}|${form.delimiter || 'auto'}|${form.hasHeader}`;
  const previewLoading = previewColumnsState.pairKey === previewPairKey && previewColumnsState.isFetching;
  const previewError = previewColumnsState.pairKey === previewPairKey ? previewColumnsState.error : null;
  const previewData = previewColumnsState.pairKey === previewPairKey ? previewColumnsState.data : null;
  const fixedWidthLoading = previewFixedWidthState.pairKey === fixedWidthPairKey && previewFixedWidthState.isFetching;
  const fixedWidthError = previewFixedWidthState.pairKey === fixedWidthPairKey ? previewFixedWidthState.error : null;
  const cacheHit = cache?.sourceKey === sourceKey && cache?.targetKey === targetKey
    && !cache.sourceError && !cache.targetError;

  const sourceProfile: FileProfileState = !form.sourceCloud ? emptyProfileState : cacheHit ? { profile: cache.source, loading: false, error: cache.sourceError } : { profile: null, loading: true, error: false };
  const targetProfile: FileProfileState = !form.targetCloud ? emptyProfileState : cacheHit ? { profile: cache.target, loading: false, error: cache.targetError } : { profile: null, loading: true, error: false };
  const isFetching = sourceProfile.loading || targetProfile.loading;
  const sourceEmpty = isValidationFileEmpty(
    form.sourceFileSize,
    sourceProfile.profile,
    sourceProfile.error,
  );
  const targetEmpty = isValidationFileEmpty(
    form.targetFileSize,
    targetProfile.profile,
    targetProfile.error,
  );
  const isFixedWidth = !sourceEmpty && !targetEmpty && (
    isFixedWidthFormat(sourceProfile.profile?.suggested_file_format ?? sourceProfile.profile?.file_format)
    || isFixedWidthFormat(targetProfile.profile?.suggested_file_format ?? targetProfile.profile?.file_format)
  );
  const sourceLooksJson = profileLooksJson(sourceProfile.profile, form.sourceFileName);
  const targetLooksJson = profileLooksJson(targetProfile.profile, form.targetFileName);
  const isJson = !sourceEmpty && !targetEmpty && !isFixedWidth && sourceLooksJson && targetLooksJson;
  const isArchiveContainer = !sourceEmpty && !targetEmpty && !isFixedWidth && !isJson && (
    profileLooksArchive(sourceProfile.profile, form.sourceFileName)
    && profileLooksArchive(targetProfile.profile, form.targetFileName)
  );
  const isArchiveTabular = isArchiveContainer && archiveUsesTabularValidation({
    detectedFileFormat: form.detectedFileFormat,
    sourceFileName: form.sourceFileName,
    targetFileName: form.targetFileName,
    sourceProfile: sourceProfile.profile,
    targetProfile: targetProfile.profile,
  });
  const isArchive = isArchiveContainer && !isArchiveTabular;
  const isArchiveMetadataOnly = isArchive;

  const archiveTabularColumnCount = (
    side: 'source' | 'target',
    profile: CloudFileProfileResponse | null,
  ): number | null => {
    if (!isArchiveTabular) return null;
    const previewCols = side === 'source'
      ? previewData?.source_columns
      : previewData?.target_columns;
    return previewCols?.length ?? profile?.column_count ?? null;
  };

  const archiveTabularRowCount = (profile: CloudFileProfileResponse | null): number | null => {
    if (!isArchiveTabular) return null;
    return profile?.row_count ?? null;
  };

  useEffect(() => {
    if (!isArchive || isFetching) return;
    const kind = resolveWizardArchiveMode({
      detectedFileFormat: form.detectedFileFormat,
      sourceFileName: form.sourceFileName,
      targetFileName: form.targetFileName,
      sourceProfile: sourceProfile.profile,
      targetProfile: targetProfile.profile,
    });
    if (!kind) return;
    dispatch(validationActions.setValidationForm({
      detectedFileFormat: kind,
      columnMappings: [],
    }));
  }, [isArchive, isFetching, dispatch, form.detectedFileFormat, form.sourceFileName, form.targetFileName, sourceProfile.profile, targetProfile.profile]);

  useEffect(() => {
    if (!isJson || isFetching) return;
    dispatch(validationActions.setValidationForm({
      detectedFileFormat: 'json',
      uidColumn: form.uidColumn || 'document',
      columnMappings: [],
    }));
  }, [isJson, isFetching, dispatch, form.uidColumn]);

  useEffect(() => {
    if (!isFixedWidth || isFetching) return;
    dispatch(validationActions.setValidationForm({ detectedFileFormat: 'fixed-width' }));
  }, [isFixedWidth, isFetching, dispatch]);

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey || cacheHit) return;
    dispatch(validationActions.profileCloudFilesRequest({ sourceKey, targetKey }));
  }, [form.sourceCloud, form.targetCloud, sourceKey, targetKey, cacheHit, dispatch]);

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey || !isFixedWidth || form.fixedWidthColumns.length > 0) {
      return;
    }

    dispatch(validationActions.previewFixedWidthLayoutRequest(fixedWidthPairKey));
  }, [
    form.sourceCloud,
    form.targetCloud,
    form.uidColumn,
    form.delimiter,
    form.hasHeader,
    form.fixedWidthColumns.length,
    fixedWidthPairKey,
    isFixedWidth,
    sourceKey,
    targetKey,
    dispatch,
  ]);

  useEffect(() => {
    if (!isFixedWidth || previewFixedWidthState.pairKey !== fixedWidthPairKey || !previewFixedWidthState.data) return;
    const { columns, suggested_join_column: joinCol, line_width: lineWidth } = previewFixedWidthState.data;
    dispatch(validationActions.setValidationForm({
      fixedWidthColumns: columns,
      fixedWidthLineWidth: lineWidth,
      uidColumn: form.uidColumn || joinCol,
      detectedFileFormat: 'fixed-width',
    }));
  }, [previewFixedWidthState, fixedWidthPairKey, isFixedWidth, form.uidColumn, dispatch]);

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey || isFixedWidth || isJson || isArchive || isFetching) {
      return;
    }

    dispatch(validationActions.previewValidationColumnsRequest(previewPairKey));
  }, [form.sourceCloud, form.targetCloud, form.uidColumn, form.delimiter, form.hasHeader, previewPairKey, sourceKey, targetKey, isFixedWidth, isJson, isArchive, isFetching, dispatch]);

  const handleFixedWidthChange = (columns: FixedWidthColumnPreview[]) => {
    dispatch(validationActions.setValidationForm({ fixedWidthColumns: columns }));
  };

  const handleJoinColumnChange = (joinColumn: string) => {
    dispatch(validationActions.setValidationForm({ uidColumn: joinColumn }));
  };

  useEffect(() => {
    setPreviewOpen(false);
  }, [previewPairKey]);

  const openPreview = useCallback(() => {
    setPreviewOpen(true);
  }, []);

  const jsonPreviewReady = Boolean(
    sourceProfile.profile?.json_preview && targetProfile.profile?.json_preview,
  );

  const previewControl = isJson
    ? (jsonPreviewReady
      ? <PreviewButton onClick={openPreview} />
      : isFetching
        ? <SkeletonBlock sizes={['w36', 'h32']} />
        : '—')
    : previewData
      ? <PreviewButton onClick={openPreview} />
      : previewLoading
        ? <SkeletonBlock sizes={['w36', 'h32']} />
        : '—';

  const inferredColumnCount = isArchiveMetadataOnly
    ? (sourceProfile.profile?.column_count ?? null)
    : isArchiveTabular
      ? archiveTabularColumnCount('source', sourceProfile.profile)
      : isFixedWidth
        ? (form.fixedWidthColumns.length || sourceProfile.profile?.column_count || null)
        : isJson
          ? (sourceProfile.profile?.column_count ?? 1)
          : (sourceProfile.profile?.column_count ?? null);

  const inferredTargetColumnCount = isArchiveTabular
    ? archiveTabularColumnCount('target', targetProfile.profile)
    : isFixedWidth
      ? inferredColumnCount
      : isJson
        ? (targetProfile.profile?.column_count ?? 1)
        : (targetProfile.profile?.column_count ?? null);

  const inferredRowCount = (profile: CloudFileProfileResponse | null, empty: boolean) => {
    if (empty) return 0;
    if (isArchiveMetadataOnly) return profile?.archive_entry_count ?? profile?.row_count ?? null;
    if (isArchiveTabular) return archiveTabularRowCount(profile);
    if (isJson) return profile?.row_count ?? 1;
    return profile?.row_count ?? null;
  };

  const headerFooterLabel = (profile: CloudFileProfileResponse | null) =>
    isJson || isArchiveMetadataOnly
      ? 'N/A'
      : formatBoolean(profile?.has_header ?? previewData?.has_header);

  const sourceStats = {
    name: form.sourceFileName ?? '—',
    path: gsPath(form.sourceCloud?.bucket ?? null, form.sourceCloud?.object_name ?? null),
    format: (() => {
      const raw = resolveCloudFormatRaw(
        sourceProfile.profile,
        form.sourceFileName,
        form.sourceCloud?.object_name,
        sourceEmpty,
      );
      if (!raw) return '—';
      if (raw === 'empty') return formatDetectionLabel('empty');
      return <FormatDetectionChainLabel format={raw} />;
    })(),
    sizeBytes: sourceProfile.profile?.file_size_bytes ?? form.sourceFileSize,
    columnCount: sourceEmpty ? 0 : inferredColumnCount,
    rowCount: inferredRowCount(sourceProfile.profile, sourceEmpty),
    header: headerFooterLabel(sourceProfile.profile),
    footer: isJson || isArchiveMetadataOnly ? 'N/A' : formatBoolean((sourceProfile.profile as { has_footer?: boolean })?.has_footer),
    preview: previewControl,
  };

  const targetStats = {
    name: form.targetFileName ?? '—',
    path: gsPath(form.targetCloud?.bucket ?? null, form.targetCloud?.object_name ?? null),
    format: (() => {
      const raw = resolveCloudFormatRaw(
        targetProfile.profile,
        form.targetFileName,
        form.targetCloud?.object_name,
        targetEmpty,
      );
      if (!raw) return '—';
      if (raw === 'empty') return formatDetectionLabel('empty');
      return <FormatDetectionChainLabel format={raw} />;
    })(),
    sizeBytes: targetProfile.profile?.file_size_bytes ?? form.targetFileSize,
    columnCount: targetEmpty ? 0 : inferredTargetColumnCount,
    rowCount: inferredRowCount(targetProfile.profile, targetEmpty),
    header: headerFooterLabel(targetProfile.profile),
    footer: isJson || isArchiveMetadataOnly ? 'N/A' : formatBoolean((targetProfile.profile as { has_footer?: boolean })?.has_footer),
    preview: previewControl,
  };

  const emptyAssessment = assessEmptyValidationFiles({
    sourceSizeBytes: form.sourceFileSize,
    targetSizeBytes: form.targetFileSize,
    sourceProfile: sourceProfile.profile,
    targetProfile: targetProfile.profile,
    profilesLoading: isFetching,
    sourceProfileError: sourceProfile.error,
    targetProfileError: targetProfile.error,
  });

  const runComparison = () => {
    if (!form.sourceCloud || !form.targetCloud) {
      return {
        status: 'warning' as const,
        title: 'Files not selected',
        message: 'Select source and target GCS objects in step 1.',
        mismatches: { size: false, columns: false, rows: false },
        blocksMapping: true,
      };
    }
    if (isFetching) {
      return {
        status: 'warning' as const,
        title: 'Analyzing files',
        message: 'Detecting format and estimating file shape…',
        mismatches: { size: false, columns: false, rows: false },
        blocksMapping: false,
      };
    }
    if (emptyAssessment?.blocksMapping) {
      return {
        status: 'error' as const,
        title: emptyAssessment.title,
        message: emptyAssessment.message,
        mismatches: { size: false, columns: false, rows: false },
        blocksMapping: true,
      };
    }

    const sizeDiff = sourceStats.sizeBytes && targetStats.sizeBytes ? Math.abs(sourceStats.sizeBytes - targetStats.sizeBytes) / sourceStats.sizeBytes : 0;
    const columnMismatch = sourceStats.columnCount != null && targetStats.columnCount != null && sourceStats.columnCount !== targetStats.columnCount;
    const rowDiff = sourceStats.rowCount != null && targetStats.rowCount != null ? Math.abs(sourceStats.rowCount - targetStats.rowCount) / Math.max(sourceStats.rowCount, targetStats.rowCount) : 0;

    const rowMismatch = rowDiff > 0.05;
    const mismatches = { size: sizeDiff > 0.2, columns: columnMismatch, rows: rowMismatch };

    const issues = [];
    if (mismatches.columns) issues.push(`Columns (${sourceStats.columnCount?.toLocaleString()} vs ${targetStats.columnCount?.toLocaleString()})`);
    if (mismatches.rows) issues.push(`Rows (${sourceStats.rowCount?.toLocaleString()} vs ${targetStats.rowCount?.toLocaleString()})`);
    if (mismatches.size) issues.push(`Size (>20% diff)`);

    if (issues.length > 0) {
      return {
        status: 'warning' as const,
        title: issues.length > 1 ? 'Multiple Mismatches Detected' : 'Mismatch Detected',
        message: `Source and target differ in: ${issues.join(' | ')}.`,
        mismatches,
        blocksMapping: false,
      };
    }

    return {
      status: 'success' as const,
      title: 'Ready for mapping',
      message: 'GCS source and target objects are selected.',
      mismatches,
      blocksMapping: false,
    };
  };

  const alert = runComparison();

  const alertClass = alert.status === 'success'
    ? styles.alertSuccess
    : alert.status === 'error'
      ? styles.alertError
      : styles.alertWarning;

  const alertIcon = alert.status === 'success'
    ? <CheckCircleFilled className={styles.alertIconSuccess} />
    : alert.status === 'error'
      ? <CloseCircleFilled className={styles.alertIconError} />
      : <WarningFilled className={styles.alertIconWarning} />;

  return (
    <div className={styles.root}>
      <div className={styles.cardsRow}>
        <FileCard label="Source" stats={sourceStats} warn={alert.mismatches} loading={isFetching} isEmpty={sourceEmpty} />
        <ArrowRightOutlined className={styles.arrowIcon} />
        <FileCard label="Target" icon={<DatabaseOutlined />} stats={targetStats} warn={alert.mismatches} loading={isFetching} isEmpty={targetEmpty} />
      </div>

      <OverviewFilePreview
        open={previewOpen && !isJson}
        preview={previewData}
        sourceLabel={sourceStats.name}
        targetLabel={targetStats.name}
        loading={previewLoading}
        error={previewError}
        onClose={() => setPreviewOpen(false)}
      />

      <OverviewJsonPreview
        open={previewOpen && isJson}
        sourcePreview={sourceProfile.profile?.json_preview ?? null}
        targetPreview={targetProfile.profile?.json_preview ?? null}
        sourceLabel={sourceStats.name}
        targetLabel={targetStats.name}
        onClose={() => setPreviewOpen(false)}
      />

      {isFixedWidth && (
        <FixedWidthLayoutPanel
          columns={form.fixedWidthColumns}
          loading={fixedWidthLoading}
          error={fixedWidthError}
          joinColumn={form.uidColumn}
          lineWidth={form.fixedWidthLineWidth ?? undefined}
          onChange={handleFixedWidthChange}
          onJoinColumnChange={handleJoinColumnChange}
        />
      )}

      <div className={`${styles.alert} ${alertClass}`}>
        {alertIcon}
        <div>
          <h5 className={styles.alertTitle}>{alert.title}</h5>
          <p className={styles.alertMessage}>{alert.message}</p>
        </div>
      </div>
    </div>
  );
};

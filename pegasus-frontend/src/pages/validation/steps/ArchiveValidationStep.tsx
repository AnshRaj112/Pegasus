import React from 'react';
import { FileZipOutlined, SafetyOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useAppSelector } from '../../../redux/store';
import { formatDetectionLabel } from '../../../shared/formatDisplayLabel';
import { FormatDetectionChainLabel } from '../../../shared/FormatDetectionChainLabel';
import { archiveKindFromProfile, resolveWizardArchiveMode } from '../archiveFormat';
import styles from './ArchiveValidationStep.module.scss';

const formatBytes = (bytes: number | null | undefined) => {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

export const ArchiveValidationStep: React.FC = () => {
  const validationForm = useAppSelector((s) => s.validation.validationForm);
  const overviewCache = useAppSelector((s) => s.validation.overviewProfileCache);

  const archiveKind = resolveWizardArchiveMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  });

  const sourceProfile = overviewCache?.source;
  const targetProfile = overviewCache?.target;

  const entryCount = (profile: typeof sourceProfile) =>
    profile?.archive_entry_count ?? profile?.row_count ?? null;

  const manifestNote = (profile: typeof sourceProfile) => {
    if (profile?.archive_manifest_supported === false) {
      return 'Byte-identical comparison only (compressed wrapper)';
    }
    return 'Metadata manifest + streaming byte digest';
  };

  return (
    <div className={styles.root}>
      <div className={styles.infoBanner}>
        <SafetyOutlined className={styles.infoIcon} />
        <div>
          <div className={styles.infoTitle}>
            Archive validation (no decompression)
          </div>
          <div className={styles.infoBody}>
            Metadata manifest + streaming byte digest. Nested archives (e.g. csv inside zip
            inside tar) are expanded up to depth 3 using bounded member reads.
          </div>
        </div>
      </div>

      <div className={styles.cardGrid}>
        {[
          { label: 'Source', name: validationForm.sourceFileName, profile: sourceProfile },
          { label: 'Target', name: validationForm.targetFileName, profile: targetProfile },
        ].map(({ label, name, profile }) => (
          <div key={label} className={styles.card}>
            <div className={styles.cardHeader}>
              <FileZipOutlined />
              <span className={styles.cardLabel}>{label}</span>
            </div>
            <h4 className={styles.cardTitle}>{name ?? '—'}</h4>
            <div className={styles.cardDetails}>
              <div>
                <strong>Format:</strong>
                {' '}
                <FormatDetectionChainLabel format={profile?.file_format ?? archiveKind ?? 'zip'} />
              </div>
              <div><strong>Size:</strong> {formatBytes(profile?.file_size_bytes ?? null)}</div>
              <div><strong>Entries:</strong> {entryCount(profile) == null ? '—' : entryCount(profile)!.toLocaleString()}</div>
              <div><strong>Mode:</strong> {manifestNote(profile)}</div>
              {profile?.archive_entries_sample && profile.archive_entries_sample.length > 0 && (
                <div>
                  <strong>Sample paths:</strong>
                  <ul className={styles.sampleList}>
                    {profile.archive_entries_sample.slice(0, 5).map((entry) => (
                      <li key={entry}>{entry}</li>
                    ))}
                  </ul>
                </div>
              )}
              {profile?.archive_warnings?.map((warning) => (
                <div key={warning} className={styles.warningText}>{warning}</div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.readyBanner}>
        <CheckCircleOutlined />
        Ready to validate
        {' '}
        {archiveKind ? formatDetectionLabel(archiveKind) : 'archive'}
        {' '}
        pair —
        {archiveKindFromProfile(sourceProfile) === archiveKindFromProfile(targetProfile)
          ? ' no column mapping required.'
          : ' confirm both sides are the same archive type.'}
      </div>
    </div>
  );
};

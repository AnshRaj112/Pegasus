import type { CloudFileProfileResponse } from '../../shared/api/Api';

const ARCHIVE_KINDS = new Set(['zip', 'tar', '7z', 'rar']);
const CHAIN_SEP = /\s*->\s*/;

export const parseFormatChain = (format: string | null | undefined): string[] => {
  if (!format) return [];
  return format.split(CHAIN_SEP).map((s) => s.trim().toLowerCase()).filter(Boolean);
};

export const outerFormatKind = (format: string | null | undefined): string | null => {
  const chain = parseFormatChain(format);
  return chain[0] ?? null;
};

export const isArchiveKind = (kind: string | null | undefined): boolean =>
  Boolean(kind && ARCHIVE_KINDS.has(kind.toLowerCase().replace(/_/g, '-')));

/** True when format token or chain outer segment is a container archive. */
export const isArchiveFormat = (format: string | null | undefined): boolean => {
  if (!format) return false;
  const normalized = format.toLowerCase().replace(/_/g, '-');
  if (isArchiveKind(normalized)) return true;
  return isArchiveKind(outerFormatKind(format));
};

export const archiveKindFromProfile = (
  profile: Pick<CloudFileProfileResponse, 'suggested_file_format' | 'file_format' | 'dataset_model'> | null | undefined,
): 'zip' | 'tar' | null => {
  if (!profile) return null;
  if (profile.dataset_model === 'container') {
    const suggested = (profile.suggested_file_format ?? '').toLowerCase();
    if (suggested === 'zip' || suggested === 'tar') return suggested;
    const outer = outerFormatKind(profile.file_format);
    if (outer === 'zip' || outer === 'tar') return outer;
  }
  if (isArchiveFormat(profile.suggested_file_format)) {
    const kind = (profile.suggested_file_format ?? '').toLowerCase();
    if (kind === 'zip' || kind === 'tar') return kind;
  }
  return null;
};

export const archiveKindFromFileName = (fileName: string | null | undefined): 'zip' | 'tar' | null => {
  const name = (fileName ?? '').toLowerCase();
  if (name.endsWith('.zip')) return 'zip';
  if (/\.(tar|tgz|tar\.gz)$/.test(name)) return 'tar';
  return null;
};

export const profileLooksArchive = (
  profile: CloudFileProfileResponse | null | undefined,
  fileName?: string | null,
): boolean => {
  if (archiveKindFromProfile(profile)) return true;
  if (profile?.dataset_model === 'container') return true;
  const name = (fileName ?? profile?.object_name ?? '').toLowerCase();
  return /\.(zip|tar|tgz|tar\.gz)$/.test(name);
};

export const resolveWizardArchiveMode = (input: {
  detectedFileFormat: string | null | undefined;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  sourceProfile?: CloudFileProfileResponse | null;
  targetProfile?: CloudFileProfileResponse | null;
}): 'zip' | 'tar' | null => {
  if (input.detectedFileFormat === 'zip' || input.detectedFileFormat === 'tar') {
    return input.detectedFileFormat;
  }
  const src = archiveKindFromProfile(input.sourceProfile ?? null);
  const tgt = archiveKindFromProfile(input.targetProfile ?? null);
  if (src && tgt && src === tgt) return src;
  if (profileLooksArchive(input.sourceProfile, input.sourceFileName)
    && profileLooksArchive(input.targetProfile, input.targetFileName)) {
    return src ?? tgt ?? archiveKindFromFileName(input.sourceFileName) ?? archiveKindFromFileName(input.targetFileName);
  }
  return null;
};

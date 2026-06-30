import type { CloudFileProfileResponse } from '../../shared/api/Api';
import { isFixedWidthFormat } from './fixedWidthFormat';

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

const JSON_LEAF_SUFFIXES = /\.(json|ndjson)$/i;
const TABULAR_LEAF_SUFFIXES = /\.(csv|tsv|psv|txt|dat)$/i;

const formatChainHasJsonLeaf = (format: string | null | undefined): boolean => {
  const chain = parseFormatChain(format);
  return chain.some((segment) => {
    const normalized = segment.toLowerCase().replace(/_/g, '-');
    return normalized === 'json' || normalized === 'ndjson';
  });
};

const formatChainHasFixedWidthLeaf = (format: string | null | undefined): boolean =>
  isFixedWidthFormat(format);

const formatChainHasDelimitedTabularLeaf = (format: string | null | undefined): boolean => {
  if (formatChainHasJsonLeaf(format) || formatChainHasFixedWidthLeaf(format)) return false;
  const chain = parseFormatChain(format);
  return chain.some((segment) => {
    const normalized = segment.toLowerCase().replace(/_/g, '-');
    return ['csv', 'tsv', 'psv', 'delimited', 'dat', 'txt'].includes(normalized);
  });
};

export const archiveHasJsonLeaf = (
  profile: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format'> | null | undefined,
): boolean => {
  if (formatChainHasJsonLeaf(profile?.file_format)) return true;
  const sample = profile?.archive_entries_sample;
  if (!sample?.length) return false;
  return sample.some((path) => JSON_LEAF_SUFFIXES.test(path.split('/').pop() ?? ''));
};

export const archiveHasFixedWidthLeaf = (
  profile: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format'> | null | undefined,
): boolean => {
  if (formatChainHasFixedWidthLeaf(profile?.file_format)) return true;
  const sample = profile?.archive_entries_sample;
  if (!sample?.length) return false;
  return sample.some((path) => /\.fw$/i.test(path.split('/').pop() ?? ''));
};

export const archiveHasTabularLeaf = (
  profile: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format'> | null | undefined,
): boolean => {
  if (formatChainHasJsonLeaf(profile?.file_format) || formatChainHasFixedWidthLeaf(profile?.file_format)) {
    return false;
  }
  if (formatChainHasDelimitedTabularLeaf(profile?.file_format)) {
    return true;
  }
  const sample = profile?.archive_entries_sample;
  if (!sample?.length) return false;
  if (sample.some((path) => TABULAR_LEAF_SUFFIXES.test(path.split('/').pop() ?? ''))) {
    return true;
  }
  return false;
};

const archivePairHasInnerLeaf = (
  input: {
    sourceProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format'> | null;
    targetProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format'> | null;
  },
  predicate: (profile: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format'> | null | undefined) => boolean,
): boolean => predicate(input.sourceProfile) && predicate(input.targetProfile);

export const archiveUsesJsonValidation = (input: {
  sourceProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  targetProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  detectedFileFormat?: string | null | undefined;
}): boolean => {
  if (!resolveWizardArchiveMode(input)) return false;
  return archivePairHasInnerLeaf(input, archiveHasJsonLeaf);
};

export const archiveMayBeFixedWidth = (
  profile: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format'> | null | undefined,
): boolean => {
  if (archiveHasFixedWidthLeaf(profile)) return true;
  if (formatChainHasJsonLeaf(profile?.file_format)) return false;
  const sample = profile?.archive_entries_sample;
  if (!sample?.length) return false;
  return sample.some((path) => /\.(txt|dat|fw)$/i.test(path.split('/').pop() ?? ''));
};

export const archiveUsesFixedWidthValidation = (input: {
  sourceProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  targetProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  detectedFileFormat?: string | null | undefined;
}): boolean => {
  if (!resolveWizardArchiveMode(input)) return false;
  return archivePairHasInnerLeaf(input, archiveMayBeFixedWidth);
};

export const archiveUsesTabularValidation = (input: {
  sourceProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  targetProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  detectedFileFormat?: string | null | undefined;
}): boolean => {
  if (!resolveWizardArchiveMode(input)) return false;
  return archivePairHasInnerLeaf(input, archiveHasTabularLeaf);
};

export const archiveKindFromFileName = (fileName: string | null | undefined): 'zip' | 'tar' | null => {
  const name = (fileName ?? '').toLowerCase();
  if (name.endsWith('.zip')) return 'zip';
  if (/\.(tar|tgz|tar\.gz)$/.test(name)) return 'tar';
  return null;
};

export const profileLooksArchive = (
  profile: Pick<CloudFileProfileResponse, 'suggested_file_format' | 'file_format' | 'dataset_model' | 'object_name'> | null | undefined,
  fileName?: string | null,
): boolean => {
  if (archiveKindFromProfile(profile)) return true;
  if (profile?.dataset_model === 'container') return true;
  const name = (fileName ?? profile?.object_name ?? '').toLowerCase();
  return /\.(zip|tar|tgz|tar\.gz)$/.test(name);
};

export const resolveWizardArchiveMode = (input: {
  detectedFileFormat?: string | null | undefined;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  sourceProfile?: Pick<CloudFileProfileResponse, 'suggested_file_format' | 'file_format' | 'dataset_model' | 'object_name'> | null;
  targetProfile?: Pick<CloudFileProfileResponse, 'suggested_file_format' | 'file_format' | 'dataset_model' | 'object_name'> | null;
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

/** True when archive containers hold typed inner content (not metadata-only). */
export const archiveHasTypedInnerContent = (input: {
  sourceProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  targetProfile?: Pick<CloudFileProfileResponse, 'archive_entries_sample' | 'file_format' | 'suggested_file_format' | 'dataset_model' | 'object_name'> | null;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  detectedFileFormat?: string | null | undefined;
}): boolean =>
  archiveUsesJsonValidation(input)
  || archiveUsesFixedWidthValidation(input)
  || archiveUsesTabularValidation(input);

import type {
  CloudFileProfileResponse,
  FixedWidthLayoutPreviewResponse,
  GoogleCloudStorageConfig,
  LocalColumnPreviewResponse,
} from '../../shared/api/Api';
import type { OverviewProfileCache, PreviewRequestState, ValidationFormState } from './Validation.interface';
import { archiveUsesTabularValidation, archiveUsesJsonValidation, archiveUsesFixedWidthValidation, profileLooksArchive } from './archiveFormat';
import { isFixedWidthFormat } from './fixedWidthFormat';
import { profileLooksJson } from './jsonFormat';
import { isValidationFileEmpty } from './validationEmptyFiles';

export const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string =>
  cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

export const buildPreviewPairKey = (
  sourceKey: string,
  targetKey: string,
  form: Pick<ValidationFormState, 'uidColumn' | 'delimiter' | 'hasHeader'>,
): string =>
  `${sourceKey}|${targetKey}|${form.uidColumn || 'id'}|${form.delimiter || 'auto'}|${form.hasHeader}`;

export const buildFixedWidthPreviewPairKey = (
  sourceKey: string,
  targetKey: string,
  form: Pick<ValidationFormState, 'uidColumn' | 'delimiter' | 'hasHeader'>,
): string =>
  `${sourceKey}|${targetKey}|${form.uidColumn}|${form.delimiter || 'auto'}|${form.hasHeader}`;

export type OverviewPreviewKind = 'tabular' | 'json' | 'fixed-width' | 'archive' | 'skipped';

export type OverviewPreviewStatus = {
  kind: OverviewPreviewKind;
  loading: boolean;
  ready: boolean;
  error: string | null;
  sessionKey: string;
};

const profileFormatFlags = (
  form: ValidationFormState,
  sourceProfile: CloudFileProfileResponse | null,
  targetProfile: CloudFileProfileResponse | null,
) => {
  const sourceEmpty = isValidationFileEmpty(form.sourceFileSize, sourceProfile, false);
  const targetEmpty = isValidationFileEmpty(form.targetFileSize, targetProfile, false);
  const isFixedWidth = !sourceEmpty && !targetEmpty && (
    isFixedWidthFormat(sourceProfile?.suggested_file_format ?? sourceProfile?.file_format)
    || isFixedWidthFormat(targetProfile?.suggested_file_format ?? targetProfile?.file_format)
    || archiveUsesFixedWidthValidation({
      detectedFileFormat: form.detectedFileFormat,
      sourceFileName: form.sourceFileName,
      targetFileName: form.targetFileName,
      sourceProfile,
      targetProfile,
    })
  );
  const isJson = !sourceEmpty && !targetEmpty && !isFixedWidth
    && profileLooksJson(sourceProfile, form.sourceFileName)
    && profileLooksJson(targetProfile, form.targetFileName);
  const isArchiveContainer = !sourceEmpty && !targetEmpty && !isFixedWidth && !isJson
    && profileLooksArchive(sourceProfile, form.sourceFileName)
    && profileLooksArchive(targetProfile, form.targetFileName);
  const profileArchiveInput = {
    detectedFileFormat: form.detectedFileFormat,
    sourceFileName: form.sourceFileName,
    targetFileName: form.targetFileName,
    sourceProfile,
    targetProfile,
  };
  const isArchiveTabular = isArchiveContainer && archiveUsesTabularValidation(profileArchiveInput);
  const isArchiveJson = isArchiveContainer && archiveUsesJsonValidation(profileArchiveInput);
  const isArchiveFixedWidth = isArchiveContainer && archiveUsesFixedWidthValidation(profileArchiveInput);
  return {
    sourceEmpty,
    targetEmpty,
    isFixedWidth,
    isJson: isJson || isArchiveJson,
    isArchiveMetadataOnly: isArchiveContainer && !isArchiveTabular && !isArchiveJson && !isArchiveFixedWidth,
  };
};

export function resolveOverviewPreviewStatus(input: {
  form: ValidationFormState;
  cache: OverviewProfileCache | null;
  previewColumnsState: PreviewRequestState<LocalColumnPreviewResponse>;
  previewFixedWidthState: PreviewRequestState<FixedWidthLayoutPreviewResponse>;
}): OverviewPreviewStatus {
  const sourceKey = cloudObjectKey(input.form.sourceCloud);
  const targetKey = cloudObjectKey(input.form.targetCloud);
  const sessionKey = `${sourceKey}|${targetKey}`;
  const previewPairKey = buildPreviewPairKey(sourceKey, targetKey, input.form);
  const fixedWidthPairKey = buildFixedWidthPreviewPairKey(sourceKey, targetKey, input.form);

  if (!input.form.sourceCloud || !input.form.targetCloud || !sourceKey || !targetKey) {
    return { kind: 'tabular', loading: true, ready: false, error: null, sessionKey };
  }

  const cache = input.cache;
  const keysMatch = cache?.sourceKey === sourceKey && cache?.targetKey === targetKey;

  if (keysMatch && (cache?.sourceError || cache?.targetError)) {
    const parts: string[] = [];
    if (cache?.sourceError) parts.push('source');
    if (cache?.targetError) parts.push('target');
    return {
      kind: 'tabular',
      loading: false,
      ready: false,
      error: `Could not profile ${parts.join(' and ')} file(s). Check GCS connection and retry.`,
      sessionKey,
    };
  }

  const cacheHit = keysMatch && !cache?.sourceError && !cache?.targetError;

  if (!cache || !cacheHit) {
    return { kind: 'tabular', loading: true, ready: false, error: null, sessionKey };
  }

  const sourceProfile = cache.source;
  const targetProfile = cache.target;
  const flags = profileFormatFlags(input.form, sourceProfile, targetProfile);

  if (flags.sourceEmpty || flags.targetEmpty) {
    return { kind: 'skipped', loading: false, ready: true, error: null, sessionKey };
  }

  if (flags.isJson) {
    const ready = Boolean(sourceProfile?.json_preview && targetProfile?.json_preview);
    return {
      kind: 'json',
      loading: false,
      ready,
      error: ready ? null : 'JSON preview is not available for these files',
      sessionKey,
    };
  }

  if (flags.isArchiveMetadataOnly) {
    return {
      kind: 'archive',
      loading: false,
      ready: Boolean(sourceProfile && targetProfile),
      error: null,
      sessionKey,
    };
  }

  if (flags.isFixedWidth) {
    const state = input.previewFixedWidthState;
    const matches = state.pairKey === fixedWidthPairKey;
    return {
      kind: 'fixed-width',
      loading: !matches || state.isFetching,
      ready: matches && Boolean(state.data),
      error: matches ? state.error : null,
      sessionKey,
    };
  }

  const state = input.previewColumnsState;
  const matches = state.pairKey === previewPairKey;
  return {
    kind: 'tabular',
    loading: !matches || state.isFetching,
    ready: matches && Boolean(state.data),
    error: matches ? state.error : null,
    sessionKey,
  };
}

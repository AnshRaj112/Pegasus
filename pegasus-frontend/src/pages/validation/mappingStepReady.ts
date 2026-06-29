import type {
  FixedWidthLayoutPreviewResponse,
  LocalColumnPreviewResponse,
} from '../../shared/api/Api';
import type {
  OverviewProfileCache,
  PreviewRequestState,
  ValidationFormState,
} from './Validation.interface';
import {
  buildFixedWidthPreviewPairKey,
  buildPreviewPairKey,
  cloudObjectKey,
} from './overviewPreview';
import { overviewProfileCacheHit } from './overviewRequestGuards';

export type MappingStepReadyStatus = {
  loading: boolean;
  ready: boolean;
};

export function resolveMappingStepReady(input: {
  form: ValidationFormState;
  cache: OverviewProfileCache | null;
  previewColumnsState: PreviewRequestState<LocalColumnPreviewResponse>;
  previewFixedWidthState: PreviewRequestState<FixedWidthLayoutPreviewResponse>;
  isJson: boolean;
  isArchiveMetadataOnly: boolean;
  isFixedWidth: boolean;
}): MappingStepReadyStatus {
  const { form } = input;
  if (!form.sourceCloud || !form.targetCloud) {
    return { loading: false, ready: false };
  }

  const sourceKey = cloudObjectKey(form.sourceCloud);
  const targetKey = cloudObjectKey(form.targetCloud);
  if (!sourceKey || !targetKey) {
    return { loading: false, ready: false };
  }

  if (input.isArchiveMetadataOnly) {
    const profilesReady = overviewProfileCacheHit(input.cache, sourceKey, targetKey);
    return { loading: !profilesReady, ready: profilesReady };
  }

  if (input.isJson) {
    const ready = (form.columnMappings?.length ?? 0) > 0;
    return { loading: !ready, ready };
  }

  if (input.isFixedWidth) {
    const pairKey = buildFixedWidthPreviewPairKey(sourceKey, targetKey, form);
    const state = input.previewFixedWidthState;
    const matches = state.pairKey === pairKey;
    const ready = form.fixedWidthColumns.length > 0;
    if (ready) return { loading: false, ready: true };
    if (matches && state.error) return { loading: false, ready: false };
    return { loading: !matches || state.isFetching, ready: false };
  }

  const pairKey = buildPreviewPairKey(sourceKey, targetKey, form);
  const state = input.previewColumnsState;
  const matches = state.pairKey === pairKey;
  const hasMappings = (form.columnMappings?.length ?? 0) > 0;

  if (hasMappings) {
    return { loading: false, ready: true };
  }

  if (matches && state.error) {
    return { loading: false, ready: false };
  }

  return { loading: true, ready: false };
}

import { GoogleCloudStorageConfig } from '../../shared/api/Api';
import { PreviewRequestState, ValidationFormState } from './Validation.interface';

export const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string =>
  cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

/** Stable key for column / fixed-width preview requests across wizard steps. */
export const buildPreviewPairKey = (form: Pick<ValidationFormState, 'uidColumn' | 'delimiter' | 'hasHeader'>, sourceKey: string, targetKey: string): string =>
  `${sourceKey}|${targetKey}|${form.uidColumn || 'id'}|${form.delimiter || 'auto'}|${form.hasHeader}`;

export const isPreviewStateCached = <T>(
  state: PreviewRequestState<T>,
  pairKey: string,
): boolean =>
  state.pairKey === pairKey && state.data != null && !state.isFetching && !state.error;

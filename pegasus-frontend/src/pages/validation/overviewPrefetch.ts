import type { AppDispatch } from '../../redux/store';
import type { OverviewProfileCache, OverviewProfileFetchState, ValidationFormState } from './Validation.interface';
import { validationActions } from './Validation.reducer';
import { cloudObjectKey } from './overviewPreview';
import { shouldRequestOverviewProfiles } from './overviewRequestGuards';

/** Start GCS profile fetch only — previews are requested from overview after profiles load. */
export const dispatchOverviewProfileFetch = (
  dispatch: AppDispatch,
  form: ValidationFormState,
  cache: OverviewProfileCache | null,
  profileFetchState: OverviewProfileFetchState,
): void => {
  const sourceKey = cloudObjectKey(form.sourceCloud);
  const targetKey = cloudObjectKey(form.targetCloud);
  if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey) return;

  if (!shouldRequestOverviewProfiles(cache, profileFetchState, sourceKey, targetKey)) return;

  dispatch(validationActions.profileCloudFilesRequest({ sourceKey, targetKey }));
};

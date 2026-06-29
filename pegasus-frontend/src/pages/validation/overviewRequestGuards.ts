import type { OverviewProfileCache, PreviewRequestState } from './Validation.interface';

export interface OverviewProfileFetchState {
  sourceKey: string | null;
  targetKey: string | null;
  isFetching: boolean;
}

export const overviewProfileCacheHit = (
  cache: OverviewProfileCache | null,
  sourceKey: string,
  targetKey: string,
): boolean =>
  cache?.sourceKey === sourceKey && cache?.targetKey === targetKey
  && !cache.sourceError && !cache.targetError;

export const shouldRequestOverviewProfiles = (
  cache: OverviewProfileCache | null,
  fetchState: OverviewProfileFetchState,
  sourceKey: string,
  targetKey: string,
): boolean => {
  if (overviewProfileCacheHit(cache, sourceKey, targetKey)) return false;
  if (
    fetchState.isFetching
    && fetchState.sourceKey === sourceKey
    && fetchState.targetKey === targetKey
  ) return false;
  return true;
};

export const shouldRequestPreview = <T>(
  state: PreviewRequestState<T>,
  pairKey: string,
): boolean => {
  if (state.pairKey === pairKey && state.isFetching) return false;
  if (state.pairKey === pairKey && state.data) return false;
  return true;
};

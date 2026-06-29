import { describe, expect, it } from 'vitest';

import { initialState } from '../Validation.reducer';
import {
  overviewProfileCacheHit,
  shouldRequestOverviewProfiles,
  shouldRequestPreview,
} from '../overviewRequestGuards';

describe('overviewRequestGuards', () => {
  it('detects a valid overview profile cache hit', () => {
    expect(overviewProfileCacheHit({
      sourceKey: 'a',
      targetKey: 'b',
      source: null,
      target: null,
      sourceError: false,
      targetError: false,
    }, 'a', 'b')).toBe(true);
  });

  it('skips profile fetch when cache is warm or a matching request is in flight', () => {
    const cache = {
      sourceKey: 'a',
      targetKey: 'b',
      source: null,
      target: null,
      sourceError: false,
      targetError: false,
    };

    expect(shouldRequestOverviewProfiles(cache, initialState.overviewProfileFetchState, 'a', 'b')).toBe(false);
    expect(shouldRequestOverviewProfiles(null, {
      sourceKey: 'a',
      targetKey: 'b',
      isFetching: true,
    }, 'a', 'b')).toBe(false);
    expect(shouldRequestOverviewProfiles(null, initialState.overviewProfileFetchState, 'a', 'b')).toBe(true);
  });

  it('skips preview fetch when the same pair is loading or already loaded', () => {
    const previewState = initialState.previewColumnsState;

    expect(shouldRequestPreview({
      ...previewState,
      pairKey: 'pair',
      isFetching: true,
    }, 'pair')).toBe(false);

    expect(shouldRequestPreview({
      ...previewState,
      pairKey: 'pair',
      data: { source_columns: [], target_columns: [] } as never,
      isFetching: false,
    }, 'pair')).toBe(false);

    expect(shouldRequestPreview(previewState, 'pair')).toBe(true);
  });
});

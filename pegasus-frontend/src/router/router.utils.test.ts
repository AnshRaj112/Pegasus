import { describe, expect, it } from 'vitest';

import { isValidAppPathname } from './router.utils';

describe('isValidAppPathname', () => {
  it('accepts root pathname variants', () => {
    expect(isValidAppPathname('/')).toBe(true);
    expect(isValidAppPathname('')).toBe(true);
    expect(isValidAppPathname('//')).toBe(true);
  });

  it('rejects any non-root pathname', () => {
    expect(isValidAppPathname('/login')).toBe(false);
    expect(isValidAppPathname('/sdfghj')).toBe(false);
    expect(isValidAppPathname('/validations')).toBe(false);
    expect(isValidAppPathname('/index.html')).toBe(false);
  });
});

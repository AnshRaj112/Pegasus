import { describe, expect, it } from 'vitest';

import {
  archiveHasJsonLeaf,
  archiveHasTabularLeaf,
  archiveMayBeFixedWidth,
  archiveUsesJsonValidation,
  archiveUsesFixedWidthValidation,
  archiveUsesTabularValidation,
} from '../archiveFormat';

describe('archiveFormat helpers', () => {
  const archiveZipProfile = {
    suggested_file_format: 'zip',
    file_format: 'zip',
    dataset_model: 'container' as const,
    object_name: 'bundle.zip',
    archive_entries_sample: ['data.csv'],
  };

  const archiveJsonProfile = {
    ...archiveZipProfile,
    file_format: 'zip -> json',
    archive_entries_sample: ['data.json'],
  };

  const archiveFixedWidthProfile = {
    ...archiveZipProfile,
    file_format: 'zip -> fixed-width',
    archive_entries_sample: ['data.txt'],
  };

  it('detects tabular CSV leaves inside archives', () => {
    expect(archiveHasTabularLeaf(archiveZipProfile)).toBe(true);
    expect(archiveUsesTabularValidation({
      sourceProfile: archiveZipProfile,
      targetProfile: archiveZipProfile,
      sourceFileName: 'bundle.zip',
      targetFileName: 'bundle.zip',
    })).toBe(true);
  });

  it('detects JSON leaves inside archives', () => {
    expect(archiveHasJsonLeaf(archiveJsonProfile)).toBe(true);
    expect(archiveHasTabularLeaf(archiveJsonProfile)).toBe(false);
    expect(archiveUsesJsonValidation({
      sourceProfile: archiveJsonProfile,
      targetProfile: archiveJsonProfile,
      sourceFileName: 'bundle.zip',
      targetFileName: 'bundle.zip',
    })).toBe(true);
  });

  it('detects fixed-width leaves and excludes them from tabular CSV mode', () => {
    expect(archiveMayBeFixedWidth(archiveFixedWidthProfile)).toBe(true);
    expect(archiveHasTabularLeaf(archiveFixedWidthProfile)).toBe(false);
    expect(archiveUsesFixedWidthValidation({
      sourceProfile: archiveFixedWidthProfile,
      targetProfile: archiveFixedWidthProfile,
      sourceFileName: 'bundle.zip',
      targetFileName: 'bundle.zip',
    })).toBe(true);
  });
});

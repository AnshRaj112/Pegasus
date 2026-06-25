/** True when a profile or detection label refers to JSON document validation. */
export const isJsonFormat = (format: string | null | undefined): boolean => {
  if (!format) return false;
  const normalized = format.toLowerCase().replace(/_/g, '-');
  if (normalized === 'json' || normalized === 'ndjson') return true;
  if (normalized.includes('json') && !normalized.includes('fixed')) return true;
  return false;
};

/** True when a GCS/local object name looks like a JSON document. */
export const isJsonFileName = (name: string | null | undefined): boolean =>
  Boolean(name && /\.json$/i.test(name.trim()));

export const profileLooksJson = (
  profile: { suggested_file_format?: string | null; file_format?: string | null } | null | undefined,
  fileName: string | null | undefined,
): boolean =>
  isJsonFormat(profile?.suggested_file_format ?? profile?.file_format) || isJsonFileName(fileName);

/** Resolve whether the wizard should use the JSON mapping flow. */
export const resolveWizardJsonMode = (input: {
  detectedFileFormat: string | null | undefined;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  sourceProfile?: { suggested_file_format?: string | null; file_format?: string | null } | null;
  targetProfile?: { suggested_file_format?: string | null; file_format?: string | null } | null;
}): boolean => {
  if (isJsonFormat(input.detectedFileFormat)) return true;
  const sourceLooksJson = profileLooksJson(input.sourceProfile ?? null, input.sourceFileName ?? null);
  const targetLooksJson = profileLooksJson(input.targetProfile ?? null, input.targetFileName ?? null);
  return sourceLooksJson && targetLooksJson;
};

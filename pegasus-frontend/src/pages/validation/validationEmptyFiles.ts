import type { CloudFileProfileResponse } from '../../shared/api/Api';

export interface EmptyFileAssessment {
  sourceEmpty: boolean;
  targetEmpty: boolean;
  bothEmpty: boolean;
  blocksMapping: boolean;
  title: string;
  message: string;
}

/** True when the object has no usable tabular content (0 bytes or whitespace-only). */
export function isValidationFileEmpty(
  formSizeBytes: number | null | undefined,
  profile: CloudFileProfileResponse | null,
  profileError: boolean,
): boolean {
  if (formSizeBytes === 0) return true;
  if (profile?.file_size_bytes === 0) return true;
  if (profile && profile.row_count === 0 && profile.column_count === 0) return true;
  if (profileError && formSizeBytes === 0) return true;
  return false;
}

export function assessEmptyValidationFiles(input: {
  sourceSizeBytes: number | null | undefined;
  targetSizeBytes: number | null | undefined;
  sourceProfile: CloudFileProfileResponse | null;
  targetProfile: CloudFileProfileResponse | null;
  profilesLoading: boolean;
  sourceProfileError: boolean;
  targetProfileError: boolean;
}): EmptyFileAssessment | null {
  if (input.profilesLoading) return null;

  const sourceEmpty = isValidationFileEmpty(
    input.sourceSizeBytes,
    input.sourceProfile,
    input.sourceProfileError,
  );
  const targetEmpty = isValidationFileEmpty(
    input.targetSizeBytes,
    input.targetProfile,
    input.targetProfileError,
  );

  if (!sourceEmpty && !targetEmpty) return null;

  const bothEmpty = sourceEmpty && targetEmpty;
  let title: string;
  let message: string;

  if (bothEmpty) {
    title = 'Both files are empty';
    message = 'Source and target contain no data. Choose files with at least one data row before mapping.';
  } else if (sourceEmpty) {
    title = 'Source file is empty';
    message = 'The source file has no data rows. Replace it or choose a different source before mapping.';
  } else {
    title = 'Target file is empty';
    message = 'The target file has no data rows. Replace it or choose a different target before mapping.';
  }

  return {
    sourceEmpty,
    targetEmpty,
    bothEmpty,
    blocksMapping: true,
    title,
    message,
  };
}

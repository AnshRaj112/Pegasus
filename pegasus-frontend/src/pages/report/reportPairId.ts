import type { GoogleCloudStorageConfig } from '../../shared/api/Api';

const PAIR_SEP = '__PAIR__';

export const gcsUri = (cloud: GoogleCloudStorageConfig): string =>
  `gs://${cloud.bucket?.trim()}/${cloud.object_name?.trim().replace(/^\//, '')}`;

export const encodeReportPairId = (sourcePath: string, targetPath: string): string =>
  `${encodeURIComponent(sourcePath)}${PAIR_SEP}${encodeURIComponent(targetPath)}`;

/** Encode pair id for a single URL path segment (avoids broken routes when paths contain /). */
export const pairIdToPathSegment = (pairId: string): string => encodeURIComponent(pairId);

export const pairIdFromPathSegment = (segment: string): string => decodeURIComponent(segment);

export const decodeReportPairId = (pairId: string): { sourcePath: string; targetPath: string } => {
  const idx = pairId.indexOf(PAIR_SEP);
  if (idx < 0) throw new Error('Invalid report pair id');
  return {
    sourcePath: decodeURIComponent(pairId.slice(0, idx)),
    targetPath: decodeURIComponent(pairId.slice(idx + PAIR_SEP.length)),
  };
};

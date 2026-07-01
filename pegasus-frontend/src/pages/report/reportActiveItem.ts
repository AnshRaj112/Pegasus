import React from 'react';
import { SyncOutlined } from '@ant-design/icons';

import { GoogleCloudStorageConfig } from '../../shared/api/Api';

import { ReportItem } from './Report.interface';
import { encodeReportPairId, pairIdToPathSegment } from './reportPairId';

export const fileDisplayName = (
  fileName: string | null | undefined,
  cloud: GoogleCloudStorageConfig | null | undefined,
  path: string,
): string => {
  if (fileName?.trim()) return fileName.trim();
  if (cloud?.object_name?.trim()) {
    const seg = cloud.object_name.replace(/^\//, '').split('/').filter(Boolean).pop();
    if (seg) return seg;
  }
  if (path) {
    const seg = path.replace(/\\/g, '/').split('/').filter(Boolean).pop();
    if (seg) return seg;
  }
  return '—';
};

export const buildActiveReportItem = (params: {
  jobId: string;
  sourcePath: string;
  targetPath: string;
  sourceTitle: string;
  targetTitle: string;
  status?: 'queued' | 'running';
}): ReportItem => {
  const status = params.status ?? 'running';
  const mappingId = pairIdToPathSegment(encodeReportPairId(params.sourcePath, params.targetPath));
  return {
    id: mappingId,
    sourcePath: params.sourcePath,
    targetPath: params.targetPath,
    sourceTitle: params.sourceTitle,
    sourceSubtitle: params.sourcePath,
    jobTitle: params.targetTitle,
    jobSubtitle: status === 'queued' ? 'Queued…' : 'Validating…',
    badges: [
      { type: 'icon', content: React.createElement(SyncOutlined, { spin: true, style: { fontSize: '12px' } }) },
      { type: 'text', content: status === 'queued' ? 'Queued' : 'Running' },
    ],
    latestRunId: params.jobId,
    latestIsMatch: null,
    jobId: params.jobId,
  };
};

import React from 'react';
import { ClockCircleOutlined } from '@ant-design/icons';
import { Api, ValidationHistorySummary } from '../../shared/api/Api';
import { ReportItem } from './Report.interface';
import { decodeReportPairId, encodeReportPairId, pairIdFromPathSegment, pairIdToPathSegment } from './reportPairId';
import { buildActiveReportItem } from './reportActiveItem';
import { getActiveSessions } from '../validation/validationSessionStorage';

const pairKey = (item: ValidationHistorySummary) =>
  `${item.source_path ?? item.source_filename ?? ''}\0${item.target_path ?? item.target_filename ?? ''}`;

const runTs = (item: ValidationHistorySummary): number => {
  const ts = new Date(item.completed_at ?? item.created_at ?? '').getTime();
  return Number.isNaN(ts) ? 0 : ts;
};

const latestRunTs = (runs: ValidationHistorySummary[]): number => runTs(runs[0]);

const formatWhen = (iso: string | null | undefined) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { month: 'short', day: 'numeric', year: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const basename = (path: string | null | undefined, fallback: string | null) => {
  if (path) {
    const seg = path.replace(/\\/g, '/').split('/').filter(Boolean).pop();
    if (seg) return seg;
  }
  return fallback ?? '—';
};

const sessionSourceTitle = (session: ReturnType<typeof getActiveSessions>[number] | undefined, sourcePath: string) => {
  if (session?.sourceFileName?.trim()) return session.sourceFileName.trim();
  return basename(session?.formSnapshot?.sourceCloud?.object_name ?? sourcePath, null);
};

const sessionTargetTitle = (session: ReturnType<typeof getActiveSessions>[number] | undefined, targetPath: string) => {
  if (session?.targetFileName?.trim()) return session.targetFileName.trim();
  return basename(session?.formSnapshot?.targetCloud?.object_name ?? targetPath, null);
};

const groupByPair = (items: ValidationHistorySummary[]) => {
  const map = new Map<string, ValidationHistorySummary[]>();
  for (const item of items) {
    const key = pairKey(item);
    const list = map.get(key) ?? [];
    list.push(item);
    map.set(key, list);
  }
  for (const list of map.values()) {
    list.sort((a, b) => {
      const ta = new Date(a.completed_at ?? a.created_at).getTime();
      const tb = new Date(b.completed_at ?? b.created_at).getTime();
      return tb - ta;
    });
  }
  return map;
};

const passFailLabel = (isMatch: boolean | null | undefined): string =>
  isMatch === true ? 'P' : isMatch === false ? 'F' : '?';

const toReportItem = (runs: ValidationHistorySummary[], mappingId: string): ReportItem => {
  const latest = runs[0];
  const sourcePath = latest.source_path ?? latest.source_filename ?? '';
  const targetPath = latest.target_path ?? latest.target_filename ?? '';
  const recentResults = runs.slice(0, 3).map((run) => passFailLabel(run.is_match));
  return {
    id: mappingId,
    sourcePath,
    targetPath,
    sourceTitle: basename(latest.source_path, latest.source_filename),
    sourceSubtitle: sourcePath,
    jobTitle: basename(latest.target_path, latest.target_filename),
    jobSubtitle: `Latest: ${formatWhen(latest.completed_at ?? latest.created_at)}`,
    latestRunId: latest.run_id,
    latestIsMatch: latest.is_match,
    badges: [
      { type: 'text', content: formatWhen(latest.completed_at ?? latest.created_at) },
      { type: 'icon', content: React.createElement(ClockCircleOutlined, { style: { fontSize: '12px' } }) },
      ...recentResults.map((result) => ({ type: 'box' as const, content: result })),
    ],
  };
};

const fetchAllHistory = async (kind?: 'validation' | 'mapping') => {
  const limit = 200;
  let offset = 0;
  const all: ValidationHistorySummary[] = [];
  for (;;) {
    const { data } = await Api.listValidationHistory({ limit, offset, kind });
    all.push(...data.items);
    if (all.length >= data.total || data.items.length < limit) break;
    offset += limit;
  }
  return all;
};

const getValidationPairGroups = async () => {
  const items = await fetchAllHistory('validation');
  return [...groupByPair(items).values()].sort((a, b) => latestRunTs(b) - latestRunTs(a));
};

const idMapForGroups = (groups: ValidationHistorySummary[][]) => {
  const map = new Map<string, string>();
  groups.forEach((runs, idx) => map.set(pairKey(runs[0]), String(idx + 1)));
  return map;
};

export const ReportService = {
  getValidationPairGroups,

  resolvePairByMappingId: async (mappingId: string): Promise<{ sourcePath: string; targetPath: string }> => {
    const numeric = Number(mappingId);
    if (Number.isInteger(numeric) && numeric >= 1) {
      const groups = await getValidationPairGroups();
      const runs = groups[numeric - 1];
      if (runs) {
        return {
          sourcePath: runs[0].source_path ?? runs[0].source_filename ?? '',
          targetPath: runs[0].target_path ?? runs[0].target_filename ?? '',
        };
      }
    }
    const { sourcePath, targetPath } = decodeReportPairId(pairIdFromPathSegment(mappingId));
    return { sourcePath, targetPath };
  },

  getMappingIdForPaths: async (sourcePath: string, targetPath: string): Promise<string> => {
    const groups = await getValidationPairGroups();
    const map = idMapForGroups(groups);
    const hit = map.get(`${sourcePath}\0${targetPath}`);
    if (hit) return hit;
    return pairIdToPathSegment(encodeReportPairId(sourcePath, targetPath));
  },

  fetchActive: async (): Promise<ReportItem[]> => {
    const sessions = getActiveSessions();
    const queueByJobId = new Map<string, import('../../shared/api/Api').QueueJobSnapshot>();
    try {
      const { data: queue } = await Api.getValidationQueue();
      for (const job of queue.jobs) {
        if (job.state === 'queued' || job.state === 'running') {
          queueByJobId.set(job.job_id, job);
        }
      }
    } catch {
      // Fall back to browser session entries when the queue API is unavailable.
    }

    return sessions.map((session) => {
      const queueJob = queueByJobId.get(session.jobId);
      const sourceTitle = sessionSourceTitle(session, session.sourcePath);
      const targetTitle = sessionTargetTitle(session, session.targetPath);
      const status = queueJob?.state === 'queued' ? 'queued' : 'running';
      return buildActiveReportItem({
        jobId: session.jobId,
        sourcePath: session.sourcePath,
        targetPath: session.targetPath,
        sourceTitle,
        targetTitle,
        status,
      });
    });
  },

  fetchCompleted: async (): Promise<ReportItem[]> => {
    const groups = await getValidationPairGroups();
    const idMap = idMapForGroups(groups);
    return groups
      .filter((runs) => {
        const st = runs[0].status;
        return st === 'completed' || st === 'failed' || runs[0].completed_at != null;
      })
      .map((runs) => toReportItem(runs, idMap.get(pairKey(runs[0]))!));
  },

  fetchSaved: async (): Promise<ReportItem[]> => {
    const items = await fetchAllHistory('mapping');
    const groups = [...groupByPair(items).values()]
      .filter((runs) => runs[0].status === 'pending')
      .sort((a, b) => latestRunTs(b) - latestRunTs(a));
    return groups.map((runs) => {
      const latest = runs[0];
      const sourcePath = latest.source_path ?? latest.source_filename ?? '';
      const targetPath = latest.target_path ?? latest.target_filename ?? '';
      const pairId = pairIdToPathSegment(encodeReportPairId(sourcePath, targetPath));
      return {
        ...toReportItem(runs, pairId),
        id: pairId,
        draftRunId: latest.run_id,
        jobSubtitle: formatWhen(latest.created_at),
        badges: [
          { type: 'icon', content: React.createElement(ClockCircleOutlined, { style: { fontSize: '12px' } }) },
        ],
      };
    });
  },

  fetchRunsForPair: async (sourcePath: string, targetPath: string): Promise<ValidationHistorySummary[]> => {
    const { data } = await Api.listValidationHistory({
      limit: 200,
      offset: 0,
      kind: 'validation',
      source_path: sourcePath,
      target_path: targetPath,
    });
    return [...data.items].sort((a, b) => runTs(b) - runTs(a));
  },

  fetchHistoryRun: async (runId: string) => {
    const { data } = await Api.getValidationHistoryRun(runId);
    return data;
  },

  fetchMismatchesPage: async (
    runId: string,
    params: { limit: number; offset: number },
  ) => {
    const { data } = await Api.getValidationMismatches(runId, params);
    return data;
  },
};

import { AxiosResponse } from 'axios';

import {
  Api,
 DailyStatRow,
 EntityInsight,
 QueueJobSnapshot,
 QueueStatusResponse,
} from '../../shared/api/Api';

import { DashboardDataResponse, TaskItem } from './Dashboard.interface';

const mapJobState = (state: string): TaskItem['status'] => {
  if (state === 'running') return 'Running';
  if (state === 'queued') return 'Scheduled';
  if (state === 'failed') return 'Failed';
  return 'Completed';
};

const formatJobTime = (job: QueueJobSnapshot): string => {
  const ts = job.finished_at ?? job.started_at ?? job.enqueued_at;
  if (!ts) return '—';
  const diffSec = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} mins ago`;
  return `${Math.floor(diffSec / 3600)} hours ago`;
};

const mapQueue = (queue: QueueStatusResponse): Pick<DashboardDataResponse, 'tasks' | 'runningTasksCount'> => ({
  runningTasksCount: queue.running,
  tasks: queue.jobs.map((job) => ({
    id: job.job_id,
    name: `Validation ${job.job_id.slice(0, 8)}`,
    time: formatJobTime(job),
    status: mapJobState(job.state),
    progress: job.state === 'completed' ? 100 : job.state === 'running' ? 50 : 0,
  })),
});

export const DashboardServiceApi = {
  fetchDashboardData: async (): Promise<AxiosResponse<DashboardDataResponse>> => {
    const [queueRes, statsRes, entitiesRes] = await Promise.allSettled([
      Api.getValidationQueue(),
      Api.getDailyStats(7),
      Api.getEntityInsights(20),
    ]);

    if (queueRes.status === 'rejected') throw queueRes.reason;

    const queue = mapQueue(queueRes.value.data);
    let dailyStats: DailyStatRow[] = [];
    let totals = { passed: 0, failed: 0, total: 0 };
    let entities: EntityInsight[] = [];

    if (statsRes.status === 'fulfilled') {
      dailyStats = statsRes.value.data.items.map((row) => ({
        ...row,
        date: typeof row.date === 'string' ? row.date : String(row.date),
      }));
      totals = statsRes.value.data.totals;
    }
    if (entitiesRes.status === 'fulfilled') {
      entities = entitiesRes.value.data.entities;
    }

    return {
      ...queueRes.value,
      data: { ...queue, dailyStats, totals, entities },
    } as AxiosResponse<DashboardDataResponse>;
  },
};

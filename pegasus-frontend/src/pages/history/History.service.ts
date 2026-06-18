import {
  Api,
  type ValidationHistorySummary,
} from '../../shared/api/Api';

import { type ValidationLogItem, type MappingLogItem } from './History.interface';

const formatDuration = (seconds: number | null | undefined): string => {
  if (seconds == null || seconds <= 0) return '—';
  const total = Math.round(seconds);
  if (total < 60) return `${total}s`;
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
};

const mapValidationStatus = (run: ValidationHistorySummary): ValidationLogItem['status'] => {
  if (run.status === 'failed') return 'Fail';
  if (run.status === 'completed') return run.is_match ? 'Pass' : 'Fail';
  return 'Success';
};

const mapMappingStatus = (run: ValidationHistorySummary): MappingLogItem['status'] => {
  if (run.status === 'pending' || run.status === 'running') return 'Draft';
  if (run.status === 'completed') return 'Active';
  return 'Archived';
};

const toValidationLog = (run: ValidationHistorySummary): ValidationLogItem => ({
  id: run.run_id,
  sourceFile: run.source_filename ?? '—',
  sourceUri: run.source_path ?? '—',
  targetTable: run.target_filename ?? '—',
  targetUri: run.target_path ?? '—',
  rowCount: `${run.mapping_count} mapping${run.mapping_count === 1 ? '' : 's'}`,
  duration: formatDuration(run.durations?.total_seconds ?? run.durations?.validation_seconds),
  status: mapValidationStatus(run),
});

const toMappingLog = (run: ValidationHistorySummary): MappingLogItem => ({
  id: run.run_id,
  sourceSchema: run.source_filename ?? '—',
  sourcePath: run.source_path ?? '—',
  targetSchema: run.target_filename ?? '—',
  targetPath: run.target_path ?? '—',
  status: mapMappingStatus(run),
});

class HistoryService {
  async fetchValidationLogs(limit = 50, offset = 0): Promise<{ items: ValidationLogItem[]; total: number }> {
    const { data } = await Api.listValidationHistory({ kind: 'validation', limit, offset });
    return { items: data.items.map(toValidationLog), total: data.total };
  }

  async fetchMappingLogs(limit = 50, offset = 0): Promise<{ items: MappingLogItem[]; total: number }> {
    const { data } = await Api.listValidationHistory({ kind: 'mapping', limit, offset });
    return { items: data.items.map(toMappingLog), total: data.total };
  }

  async deleteLogRecord(id: string): Promise<void> {
    await Api.deleteValidationHistoryRun(id);
  }
}

export const historyService = new HistoryService();

import { ColumnMapping, GoogleCloudStorageConfig } from '../../shared/api/Api';

const STORAGE_KEY = 'pegasus_active_validation_sessions';

export interface ActiveValidationSession {
  jobId: string;
  sourcePath: string;
  targetPath: string;
  sourceFileName?: string | null;
  targetFileName?: string | null;
  startedAt: number;
  formSnapshot?: {
    sourceCloud: GoogleCloudStorageConfig | null;
    targetCloud: GoogleCloudStorageConfig | null;
    uidColumn: string;
    delimiter: string;
    hasHeader: boolean;
    columnMappings: ColumnMapping[];
  };
}

const readAll = (): ActiveValidationSession[] => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ActiveValidationSession[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const writeAll = (sessions: ActiveValidationSession[]) => {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
};

export const getActiveSessions = (): ActiveValidationSession[] => readAll();

export const setActiveSessions = (sessions: ActiveValidationSession[]) => {
  writeAll(sessions);
};

export const upsertActiveSession = (session: ActiveValidationSession) => {
  const sessions = readAll().filter((s) => s.jobId !== session.jobId);
  sessions.unshift(session);
  writeAll(sessions);
};

export const removeActiveSession = (jobId: string) => {
  writeAll(readAll().filter((s) => s.jobId !== jobId));
};

export const getActiveSession = (jobId: string): ActiveValidationSession | undefined =>
  readAll().find((s) => s.jobId === jobId);

export const replaceActiveSessionJobId = (pendingJobId: string, jobId: string): void => {
  const sessions = readAll();
  const pending = sessions.find((s) => s.jobId === pendingJobId);
  if (!pending) return;
  const withoutDuplicate = sessions.filter((s) => s.jobId !== jobId);
  writeAll(
    withoutDuplicate.map((s) => (s.jobId === pendingJobId ? { ...s, jobId } : s)),
  );
};

export const clearAllActiveSessions = () => {
  sessionStorage.removeItem(STORAGE_KEY);
};
